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
from util import hexs, log_error, log_frame


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
        key = hexs(uid)
        for item in self.records:
            if item.get("uid") == key:
                return int(item.get("folder", 0))
        return 0

    def next_folder(self):
        # Folder that the next unknown disc would get (0 = table is full).
        if len(self.records) >= MAX_TAGS:
            return 0
        return len(self.records) + 1

    def register(self, uid):
        folder = self.next_folder()
        if folder == 0:
            return 0
        self.records.append({"uid": hexs(uid), "folder": folder})
        self.save()
        return folder


class Encoder:
    # GPIO0 is used only by the encoder push button (SW), not by channel B.
    # Its internal pull-up keeps it HIGH; do not press the encoder at power-on/reset.
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
        self.acc = 0
        self.last_button = 1
        self.button_time = now_ms()
        self.button_latched = False

    def read_step(self):
        # Returns +1 / -1 once per detent (ENCODER_STEPS_PER_DETENT transitions).
        state = (self.a.value() << 1) | self.b.value()
        if state != self.last:
            direction = self.SEQ.get(self.last, {}).get(state, 0)
            self.last = state
            self.acc += direction * ENCODER_DIRECTION
        if self.acc >= ENCODER_STEPS_PER_DETENT:
            self.acc -= ENCODER_STEPS_PER_DETENT
            return 1
        if self.acc <= -ENCODER_STEPS_PER_DETENT:
            self.acc += ENCODER_STEPS_PER_DETENT
            return -1
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

        # UART0 is normally the MicroPython REPL. We need it for the DFPlayer
        # full duplex link, so detach the REPL before creating the UART object.
        try:
            uos.dupterm(None, 1)
        except Exception:
            pass

        # GPIO1/TX -> DFPlayer RX through 1 kOhm.
        # GPIO3/RX <- DFPlayer TX.
        self.df_uart = UART(0, baudrate=DFPLAYER_BAUD, bits=8, parity=None,
                            stop=1, tx=Pin(DFPLAYER_TX_PIN), rx=Pin(DFPLAYER_RX_PIN))
        self.df = DFPlayer(self.df_uart)
        if DF_DEBUG:
            self.df.log = log_frame

        self.tags = TagDatabase(TAG_DB_FILE)
        self.current_folder = 0
        self.current_track = 0
        self.track_count = 0
        self.last_dir = 1
        self.volume = DEFAULT_VOLUME
        self.paused = False
        self.active_uid = b""          # disc on the reader (also while in error)
        self.error_mode = ERR_NONE
        self.blink_on = False
        self.blink_t = now_ms()
        self.last_tag = now_ms()
        self.last_nfc = now_ms()
        self.ready = False

    # ---- ring and motor ---------------------------------------------------

    def fill(self, color):
        for i in range(LED_COUNT):
            self.ring[i] = color
        self.ring.write()

    def leds_off(self):
        self.fill((0, 0, 0))

    def leds_on(self, folder):
        level = 25 + ((folder - 1) % 5) * 8
        self.fill((level, level // 2, 0))

    def motor_on(self):
        self.motor.value(1)

    def motor_off(self):
        self.motor.value(0)

    # ---- error indication (only while a disc is on the reader) ------------

    def show_error(self, mode):
        self.error_mode = mode
        self.motor_off()
        self.blink_on = True
        self.blink_t = now_ms()
        self.paint_error()

    def paint_error(self):
        if self.error_mode == ERR_NO_SD:
            self.fill((0, 0, ERROR_LEVEL))                    # steady blue
        elif self.error_mode == ERR_UNKNOWN_DISC:
            if self.blink_on:
                self.fill((ERROR_LEVEL, 0, 0))                # blinking red
            else:
                self.fill((0, 0, 0))

    def poll_error_blink(self):
        if self.error_mode == ERR_UNKNOWN_DISC and elapsed(self.blink_t, BLINK_MS):
            self.blink_t = now_ms()
            self.blink_on = not self.blink_on
            self.paint_error()

    # ---- disc lifecycle ---------------------------------------------------

    def stop_playback(self):
        if self.current_folder:
            self.df.stop()
        self.current_folder = 0
        self.current_track = 0
        self.track_count = 0
        self.paused = False
        self.motor_off()

    def remove_disc(self):
        self.stop_playback()
        self.error_mode = ERR_NONE
        self.active_uid = b""
        self.leds_off()

    def place_disc(self, uid):
        self.active_uid = bytes(uid)
        self.error_mode = ERR_NONE

        # No SD card: steady blue, no motor, no sound.
        if SD_CHECK and not self.df.sd_ok:
            self.df.sd_ok = self.df.probe()   # an insert event may have been missed
        if SD_CHECK and not self.df.sd_ok:
            self.show_error(ERR_NO_SD)
            return

        folder = self.tags.find_folder(uid)
        if folder:
            count = self.df.files_in_folder(folder)
            if count == 0:                    # answered: folder is empty/missing
                self.show_error(ERR_UNKNOWN_DISC)
                return
        else:
            folder = self.tags.next_folder()
            if folder == 0:                   # tag table is full
                self.show_error(ERR_UNKNOWN_DISC)
                return
            count = self.df.files_in_folder(folder)
            if count == 0:                    # no such album folder on the SD
                self.show_error(ERR_UNKNOWN_DISC)
                return
            self.tags.register(uid)

        # count == -1: the module did not answer command 0x4E -> fallback value.
        if count < 0 or count > MAX_TRACKS:
            count = DEFAULT_TRACK_COUNT

        self.current_folder = folder
        self.current_track = 1
        self.track_count = count
        self.last_dir = 1
        self.paused = False
        self.motor_on()
        self.leds_on(folder)
        self.df.volume(self.volume)
        self.df.play_folder(folder, self.current_track)

    # ---- track control ----------------------------------------------------

    def next_track(self):
        if not self.current_folder or not self.track_count:
            return
        self.last_dir = 1
        self.current_track += 1
        if self.current_track > self.track_count:
            self.current_track = 1
        self.df.play_folder(self.current_folder, self.current_track)
        self.paused = False

    def previous_track(self):
        if not self.current_folder or not self.track_count:
            return
        self.last_dir = -1
        if self.current_track <= 1:
            self.current_track = self.track_count
        else:
            self.current_track -= 1
        self.df.play_folder(self.current_folder, self.current_track)
        self.paused = False

    def track_missing(self):
        # The module reported "file not found" for the track we asked for.
        # That tells us where the real end of the folder is.
        if self.current_track <= 1:
            self.stop_playback()
            self.show_error(ERR_UNKNOWN_DISC)
        elif self.last_dir < 0:
            self.current_track -= 1
            self.track_count = self.current_track
            self.df.play_folder(self.current_folder, self.current_track)
        else:
            self.track_count = self.current_track - 1
            self.current_track = 1
            self.df.play_folder(self.current_folder, 1)

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

    # ---- polling ----------------------------------------------------------

    def poll_nfc(self):
        if not elapsed(self.last_nfc, NFC_POLL_MS):
            return
        self.last_nfc = now_ms()
        uid = self.rfid.read_uid()
        if uid:
            uid = bytes(uid)
            self.last_tag = now_ms()
            if uid != self.active_uid:
                self.remove_disc()
                self.place_disc(uid)
        elif self.active_uid and elapsed(self.last_tag, NFC_MISSING_MS):
            self.remove_disc()

    def poll_controls(self):
        step = self.encoder.read_step()
        if step:
            self.set_volume(self.volume + step)
        if self.encoder.pressed():
            self.toggle_pause()

        button = self.buttons.event()
        if button == BTN_PREVIOUS:
            self.previous_track()
        elif button == BTN_NEXT:
            self.next_track()

    def poll_dfplayer(self):
        for event, param in self.df.poll_events():
            if not self.current_folder:
                continue
            if event == DFPlayer.EVENT_FINISHED:
                self.next_track()
                break
            if event == DFPlayer.EVENT_ERROR and param in DFPlayer.ERR_NOT_FOUND:
                self.track_missing()
                break
        # Card pulled out while a disc is playing.
        if self.current_folder and SD_CHECK and not self.df.sd_ok:
            self.stop_playback()
            self.show_error(ERR_NO_SD)

    def startup(self):
        self.leds_off()
        self.motor_off()
        sleep_ms(200)
        self.df.begin(DFPLAYER_SOURCE, DF_INIT_TIMEOUT_MS, SD_CHECK)
        self.df.volume(self.volume)
        self.ready = True

    def run(self):
        self.startup()
        while True:
            try:
                self.poll_nfc()
                self.poll_controls()
                self.poll_dfplayer()
                self.poll_error_blink()
                sleep_ms(2)
            except Exception as e:
                log_error(e)
                try:
                    self.remove_disc()
                except Exception:
                    pass
                sleep_ms(1000)
                gc.collect()


def main():
    Player().run()
