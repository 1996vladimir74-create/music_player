"""Upload the MicroPython music_player files to a NodeMCU ESP8266.

Usage:
    python deploy.py COM3
"""
import shutil
import subprocess
import sys
from pathlib import Path

FILES = ["config.py", "mfrc522.py", "dfplayer.py", "main.py"]


def run(*args):
    print("+", " ".join(args))
    subprocess.run(args, check=True)


def main():
    if len(sys.argv) != 2:
        print("Usage: python deploy.py COM3")
        return 2

    port = sys.argv[1]
    if shutil.which("mpremote") is None:
        print("mpremote is not installed. Install it on the PC with: python -m pip install mpremote")
        return 1

    root = Path(__file__).resolve().parent
    for name in FILES:
        local = root / name
        if not local.exists():
            print("Missing:", local)
            return 1
        run("mpremote", "connect", port, "fs", "cp", str(local), ":" + name)

    print("All MicroPython files uploaded.")
    print("Reset the board manually after verifying wiring, or run:")
    print(f"mpremote connect {port} reset")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
