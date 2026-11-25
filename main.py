"""Launcher. Keeps working even if player.py is replaced by a broken version.

Reset with NO button held   -> player
Reset with PREVIOUS held    -> USB service mode (REPL stays on USB)
Reset with NEXT held        -> Wi-Fi update mode (WebREPL, see wifi_mode.py)
Player fails to start       -> Wi-Fi update mode automatically
"""
import gc
import network
import uos
from machine import ADC
from time import sleep_ms

from config import *

# The ESP8266 starts an open-looking default access point: switch Wi-Fi off now.
try:
    network.WLAN(network.AP_IF).active(False)
    network.WLAN(network.STA_IF).active(False)
except Exception:
    pass


def _mode():
    raw = ADC(BUTTON_ADC_PIN).read()
    if raw < ADC_PREV_MAX:
        return "usb"
    if ADC_NEXT_MIN <= raw <= ADC_NEXT_MAX:
        return "wifi"
    return "play"


def _restore_repl():
    # player.py detaches the USB REPL; give it back when we fall into recovery.
    try:
        from machine import UART
        uos.dupterm(UART(0, 115200), 1)
    except Exception:
        pass


sleep_ms(REPL_WINDOW_MS)   # time to hold a button after reset
mode = _mode()

if mode == "usb":
    print("service mode: player not started")
elif mode == "wifi":
    import wifi_mode
    wifi_mode.run("button")
else:
    try:
        gc.collect()
        import player
        player.main()
    except Exception as e:
        # Broken update or hardware fault: stay reachable instead of going silent.
        from util import log_error
        log_error(e)
        _restore_repl()
        try:
            import wifi_mode
            wifi_mode.run("player failed")
        except Exception as e2:
            log_error(e2)
