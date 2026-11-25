"""Wi-Fi update mode: connects to Wi-Fi and starts WebREPL (file upload).

Ring colours (only in this mode):
  blue breathing  - connecting
  green breathing - ready, waiting for uploads
  red blinking    - error (missing/invalid wifi.json, no connection)
Leaves the mode (machine.reset) when the file REBOOT_FLAG appears, or after
WIFI_MODE_TIMEOUT_MS.
"""
import gc
import ujson
import uos
import network
import neopixel
from machine import Pin, reset
from time import ticks_ms, ticks_diff, sleep_ms

from config import *
from util import log_text


class Ring:
    def __init__(self):
        self.np = neopixel.NeoPixel(Pin(LED_DATA_PIN, Pin.OUT), LED_COUNT)

    def fill(self, color):
        for i in range(LED_COUNT):
            self.np[i] = color
        self.np.write()

    def breathe(self, t, channel):
        # triangle wave 0..WIFI_LEVEL..0 with a period of about 2 s
        phase = (t // 33) % 60
        level = phase if phase < 30 else 60 - phase
        level = level * WIFI_LEVEL // 30
        color = [0, 0, 0]
        color[channel] = level
        self.fill(tuple(color))


def _load_config():
    """Return (config dict, None) or (None, error text)."""
    try:
        with open(WIFI_CFG_FILE, "r") as f:
            cfg = ujson.load(f)
    except OSError:
        return None, "wifi.json missing"
    except ValueError:
        return None, "wifi.json is not valid JSON"
    pw = cfg.get("webrepl_password", "")
    if not isinstance(pw, str) or not (4 <= len(pw) <= 9):
        return None, "webrepl_password must be 4-9 characters"
    if not cfg.get("ssid") and not cfg.get("ap_password"):
        return None, "need ssid or ap_password"
    ap = cfg.get("ap_password")
    if ap is not None and (not isinstance(ap, str) or len(ap) < 8):
        return None, "ap_password must be at least 8 characters"
    return cfg, None


def _fail(ring, text, seconds=5):
    print("wifi mode:", text)
    log_text("wifi mode: " + text)
    t0 = ticks_ms()
    on = False
    while ticks_diff(ticks_ms(), t0) < seconds * 1000:
        on = not on
        ring.fill((WIFI_LEVEL, 0, 0) if on else (0, 0, 0))
        sleep_ms(250)
    ring.fill((0, 0, 0))


def _connect_sta(cfg, ring):
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    ip = cfg.get("ip")
    if ip and len(ip) == 4:
        sta.ifconfig(tuple(ip))
    sta.connect(cfg["ssid"], cfg.get("password", ""))
    t0 = ticks_ms()
    while ticks_diff(ticks_ms(), t0) < WIFI_CONNECT_TIMEOUT_MS:
        if sta.isconnected():
            return sta.ifconfig()[0]
        ring.breathe(ticks_ms(), 2)
        sleep_ms(50)
    sta.active(False)
    return None


def _start_ap(cfg):
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid="MusicPlayer", authmode=network.AUTH_WPA_WPA2_PSK,
              password=cfg["ap_password"])
    return "192.168.4.1"


def run(reason="button"):
    # reason "button": a failure resets the board back to the player.
    # Any other reason (player failed): stay in the REPL so USB access works.
    # The default access point of the ESP8266 must never stay open.
    network.WLAN(network.AP_IF).active(False)
    ring = Ring()
    ring.fill((0, 0, 0))

    cfg, error = _load_config()
    if error:
        _fail(ring, error)
        if reason == "button":
            reset()
        return

    ip = None
    if cfg.get("ssid"):
        ip = _connect_sta(cfg, ring)
    if ip is None and cfg.get("ap_password"):
        ip = _start_ap(cfg)
    if ip is None:
        _fail(ring, "cannot connect to Wi-Fi")
        if reason == "button":
            reset()
        return

    # WebREPL reads its password from webrepl_cfg.py (same file webrepl_setup writes).
    with open("webrepl_cfg.py", "w") as f:
        f.write("PASS = %r\n" % cfg["webrepl_password"])
    import webrepl
    webrepl.start()
    gc.collect()
    print("update mode (%s): WebREPL on ws://%s:8266" % (reason, ip))

    t0 = ticks_ms()
    while ticks_diff(ticks_ms(), t0) < WIFI_MODE_TIMEOUT_MS:
        ring.breathe(ticks_ms(), 1)
        try:
            if REBOOT_FLAG in uos.listdir():
                uos.remove(REBOOT_FLAG)
                ring.fill((WIFI_LEVEL, WIFI_LEVEL, WIFI_LEVEL))
                sleep_ms(300)
                reset()
        except OSError:
            pass
        sleep_ms(50)
    ring.fill((0, 0, 0))
    reset()
