"""Upload the music_player files to the board over Wi-Fi (WebREPL).

1. Put the board into update mode: hold NEXT, press and release RST, keep
   holding NEXT about 2 s. The ring breathes blue (connecting), then green (ready).
2. Download webrepl_cli.py from https://github.com/micropython/webrepl and put it
   next to this script (or pass --cli PATH).
3. Run:
       python deploy_wifi.py 192.168.1.50
   The script asks for the WebREPL password, uploads the files, then uploads
   reboot.flag; the board sees it and resets into the player by itself.

Note: WebREPL file transfer is documented by MicroPython as experimental, and the
upload is not atomic. If a transfer breaks, repeat it; USB (deploy.py) always works.
"""
import getpass
import subprocess
import sys
import tempfile
from pathlib import Path

FILES = ["config.py", "util.py", "mfrc522.py", "dfplayer.py",
         "player.py", "wifi_mode.py", "main.py"]


def main():
    args = sys.argv[1:]
    cli = None
    if "--cli" in args:
        i = args.index("--cli")
        cli = Path(args[i + 1])
        del args[i:i + 2]
    if len(args) != 1:
        print(__doc__)
        return 2
    host = args[0]

    root = Path(__file__).resolve().parent
    if cli is None:
        cli = root / "webrepl_cli.py"
    if not cli.exists():
        print("webrepl_cli.py not found:", cli)
        print("Get it from https://github.com/micropython/webrepl or pass --cli PATH.")
        return 1

    password = getpass.getpass("WebREPL password: ")

    def put(local, remote):
        cmd = [sys.executable, str(cli), "-p", password, str(local), f"{host}:{remote}"]
        print("+ put", remote)
        subprocess.run(cmd, check=True)

    for name in FILES:
        local = root / name
        if not local.exists():
            print("Missing:", local)
            return 1
        put(local, name)

    with tempfile.TemporaryDirectory() as tmp:
        flag = Path(tmp) / "reboot.flag"
        flag.write_text("1")
        put(flag, "reboot.flag")

    print("Done. The board resets into the player by itself.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
