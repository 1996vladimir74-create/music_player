from machine import Pin, SPI, UART, ADC
from time import ticks_ms, ticks_diff, sleep_ms
import ujson
import uos
import gc
import network
import neopixel

from config import *
from mfrc522 import MFRC522
from dfplayer import DFPlayer


def now_ms():
    return ticks_ms()


def elapsed(start, period):
    return ticks_diff(now_ms(), start) >= period


class TagDatabase:
    def __init__(self, path):
        self.path = path
        self.records = []
        self.load()

    def load(self):
        try:
            with open(self.path, "r") as f:
                data = ujson.load(f)
            if isinstance(data, list):
                self.records = data[:MAX_TAGS]
            else:
                self.records = []
        except Exception:
            self.records = []

    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            ujson.dump(self.records, f)
        try:
            uos.remove(self.path)
        except OSError:
            pass
        uos.rename(tmp, self.path)

    def find_folder(self, uid):
        key = bytes(uid).hex()
        for item in self.records:
            if item.get("uid") == key:
                return int(item.get("folder", 0))
        return 0

    def register(self, uid):
        if len(self.records) >= MAX_TAGS:
            return 0
        folder = len(self.records) + 1
        self.records.append({"uid": bytes(uid).hex(), "folder": folder})
        self.save()
        return folder


class Encoder:
    # GPIO0 is a boot strap pin. The internal pull-up keeps it HIGH at boot.
    SEQ = {
        0: {1: 1, 2: -1},
        1: {3: 1, 0: -1},
        3: {2: 1, 1: -1},
        2: {0: 1, 3: -1},
    }

    def __init__(self, pin_a, pin_b, pin_sw):
        self.a = Pin(pin_a, Pin.IN, Pin.PULL_UP)
        self.b = Pin(pin_b, Pin.IN, Pin.PULL_UP)
        self.sw = Pin(pin_sw, Pin.IN, Pin.PULL_UP)
        self.last = (self.a.value() << 1) | self.b.value()
        self.last_button = 1
        self.button_time = now_ms()
        self.button_latched = False

    def read_step(self):
        state = (self.a.value() << 1) | self.b.value()
        if state == self.last:
            return 0
        direction = self.SEQ.get(self.last, {}).get(state, 0)
        self.last = state
        if direction:
            return direction * ENCODER_DIRECTION
        return 0

    def pressed(self):
        state = self.sw.value()
        if state != self.last_button:
            self.last_button = state
            self.button_time = now_ms()
        if state == 0 and elapsed(self.button_time, BUTTON_DEBOUNCE_MS):
            if not self.button_latched:
                self.button_latched = True
                return True
        elif state == 1:
            self.button_latched = False
        return False


class AnalogButtons:
    def __init__(self, adc_pin):
        self.adc = ADC(adc_pin)
        self.last = BTN_NONE
        self.changed = now_ms()
        self.latched = False

    def read(self):
        raw = self.adc.read()
        if raw < ADC_PREV_MAX:
            return BTN_PREVIOUS
        if ADC_NEXT_MIN <= raw <= ADC_NEXT_MAX:
            return BTN_NEXT
        return BTN_NONE

    def event(self):
        current = self.read()
        if current != self.last:
            self.last = current
            self.changed = now_ms()
        if current != BTN_NONE and elapsed(self.changed, BUTTON_DEBOUNCE_MS):
            if not self.latched:
                self.latched = True
                return current
        elif current == BTN_NONE:
            self.latched = False
        return BTN_NONE


class Player:
    def __init__(self):
        try:
            network.WLAN(network.STA_IF).active(False)
            network.WLAN(network.AP_IF).active(False)
        except Exception:
            pass

        self.motor = Pin(MOTOR_PIN, Pin.OUT, value=0)
        self.ring = neopixel.NeoPixel(Pin(LED_DATA_PIN, Pin.OUT), LED_COUNT)
        self.encoder = Encoder(ENCODER_A_PIN, ENCODER_B_PIN, ENCODER_SW_PIN)
        self.buttons = AnalogButtons(BUTTON_ADC_PIN)

        self.spi = SPI(1, baudrate=SPI_BAUDRATE, polarity=0, phase=0)
        self.rfid = MFRC522(self.spi, Pin(RFID_SS_PIN, Pin.OUT, value=1), None)

        # UART0 is normally the MicroPython REPL. We need its RX for DFPlayer
        # feedback, so detach the REPL before creating the UART object.
        try:
            uos.dupterm(None, 1)
        except Exception:
            pass

        # UART1 TX GPIO2 -> DFPlayer RX through 1 kOhm.
        # UART0 RX GPIO3 <- DFPlayer TX.
        # UART0 TX GPIO1 is never written by this program and remains WS2812 DATA.
        self.df_tx_uart = UART(1, baudrate=DFPLAYER_BAUD, bits=8, parity=None, stop=1)
        try:
            self.df_rx_uart = UART(0, baudrate=DFPLAYER_BAUD, bits=8, parity=None,
                                   stop=1, rx=Pin(DFPLAYER_TX_PIN), tx=Pin(1))
        except TypeError:
            self.df_rx_uart = UART(0, baudrate=DFPLAYER_BAUD)
        self.df = DFPlayer(self.df_tx_uart, self.df_rx_uart)

        self.tags = TagDatabase(TAG_DB_FILE)
        self.current_folder = 0
        self.current_track = 0
        self.track_count = 0
        self.volume = DEFAULT_VOLUME
        self.paused = False
        self.active_uid = b""
        self.last_tag = now_ms()
        self.last_nfc = now_ms()
        self.ready = False

    def leds_off(self):
        for i in range(LED_COUNT):
            self.ring[i] = (0, 0, 0)
        self.ring.write()

    def leds_on(self, folder):
        level = 25 + ((folder - 1) % 5) * 8
        for i in range(LED_COUNT):
            self.ring[i] = (level, level // 2, 0)
        self.ring.write()

    def motor_on(self):
        self.motor.value(1)

    def motor_off(self):
        self.motor.value(0)

    def stop_album(self):
        if self.current_folder:
            self.df.stop()
        self.current_folder = 0
        self.current_track = 0
        self.track_count = 0
        self.paused = False
        self.active_uid = b""
        self.motor_off()
        self.leds_off()

    def activate_album(self, uid):
        folder = self.tags.find_folder(uid)
        if folder == 0:
            folder = self.tags.register(uid)
        if folder == 0:
            self.stop_album()
            return

        self.current_folder = folder
        self.current_track = 1
        self.paused = False
        self.active_uid = bytes(uid)

        # DFPlayer command 0x4E returns the file count for the selected folder.
        count = self.df.files_in_folder(folder)
        if count <= 0 or count > MAX_TRACKS:
            count = DEFAULT_TRACK_COUNT
        self.track_count = count

        self.motor_on()
        self.leds_on(folder)
        self.df.volume(self.volume)
        self.df.play_folder(folder, self.current_track)

    def next_track(self):
        if not self.current_folder or not self.track_count:
            return
        self.current_track += 1
        if self.current_track > self.track_count:
            self.current_track = 1
        self.df.play_folder(self.current_folder, self.current_track)
        self.paused = False

    def previous_track(self):
        if not self.current_folder or not self.track_count:
            return
        if self.current_track <= 1:
            self.current_track = self.track_count
        else:
            self.current_track -= 1
        self.df.play_folder(self.current_folder, self.current_track)
        self.paused = False

    def toggle_pause(self):
        if not self.current_folder:
            return
        if self.paused:
            self.df.resume()
            self.paused = False
        else:
            self.df.pause()
            self.paused = True

    def set_volume(self, value):
        value = max(MIN_VOLUME, min(MAX_VOLUME, value))
        if value != self.volume:
            self.volume = value
            self.df.volume(value)

    def poll_nfc(self):
        if not elapsed(self.last_nfc, NFC_POLL_MS):
            return
        self.last_nfc = now_ms()
        uid = self.rfid.read_uid()
        if uid:
            self.last_tag = now_ms()
            if not self.active_uid or uid != self.active_uid:
                self.stop_album()
                self.activate_album(uid)
        elif self.current_folder and elapsed(self.last_tag, NFC_MISSING_MS):
            self.stop_album()

    def poll_controls(self):
        step = self.encoder.read_step()
        if step and self.current_folder:
            self.set_volume(self.volume + step)
        if self.encoder.pressed():
            self.toggle_pause()

        button = self.buttons.event()
        if button == BTN_PREVIOUS:
            self.previous_track()
        elif button == BTN_NEXT:
            self.next_track()

    def poll_dfplayer(self):
        event = self.df.poll_event()
        if event == DFPLAYER_PLAY_FINISHED and self.current_folder:
            self.next_track()

    def startup(self):
        self.leds_off()
        self.motor_off()
        sleep_ms(200)
        self.df.begin()
        self.df.volume(self.volume)
        self.ready = True

    def run(self):
        self.startup()
        while True:
            try:
                self.poll_nfc()
                self.poll_controls()
                self.poll_dfplayer()
                sleep_ms(2)
            except Exception:
                self.motor_off()
                self.leds_off()
                sleep_ms(1000)
                gc.collect()


player = Player()
player.run()
