"""Upload the MicroPython music_player files to a NodeMCU ESP8266 over USB.

Usage:
    python deploy.py COM3            # code only
    python deploy.py COM3 --wifi     # also create wifi.json on the board (asks for the values)

If the board does not respond: hold PREVIOUS and press RST (USB service mode).
Wi-Fi updates afterwards: see deploy_wifi.py.
"""
import getpass
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

FILES = ["config.py", "util.py", "mfrc522.py", "dfplayer.py",
         "player.py", "wifi_mode.py", "main.py"]


def run(*args):
    print("+", " ".join(args))
    subprocess.run(args, check=True)


def make_wifi_json(root, port):
    ssid = input("Wi-Fi name (SSID): ").strip()
    password = getpass.getpass("Wi-Fi password: ")
    web = getpass.getpass("WebREPL password (4-9 characters): ")
    if not (4 <= len(web) <= 9):
        print("WebREPL password must be 4-9 characters.")
        return False
    cfg = {"ssid": ssid, "password": password, "webrepl_password": web}
    ip = input("Fixed IP (optional, empty = DHCP; needs mask/gateway next): ").strip()
    if ip:
        mask = input("  mask [255.255.255.0]: ").strip() or "255.255.255.0"
        gw = input("  gateway: ").strip()
        cfg["ip"] = [ip, mask, gw, gw]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "wifi.json"
        path.write_text(json.dumps(cfg))
        run("mpremote", "connect", port, "fs", "cp", str(path), ":wifi.json")
    return True


def main():
    if len(sys.argv) not in (2, 3) or (len(sys.argv) == 3 and sys.argv[2] != "--wifi"):
        print(__doc__)
        return 2

    port = sys.argv[1]
    if shutil.which("mpremote") is None:
        print("mpremote is not installed. Install it on the PC with: python -m pip install mpremote")
        return 1

    print("If the board does not respond: hold PREVIOUS and press RST (service mode), then run again.")
    root = Path(__file__).resolve().parent
    for name in FILES:
        local = root / name
        if not local.exists():
            print("Missing:", local)
            return 1
        run("mpremote", "connect", port, "fs", "cp", str(local), ":" + name)

    if len(sys.argv) == 3 and not make_wifi_json(root, port):
        return 1

    print("All MicroPython files uploaded.")
    print("Reset the board manually after verifying wiring, or run:")
    print(f"mpremote connect {port} reset")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
