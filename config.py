# Frozen hardware configuration for music_player.
# MicroPython / NodeMCU V3 LoLin ESP8266.

# RC522 / MFRC522
RFID_SS_PIN = 15       # D8
RFID_RST_PIN = None    # RC522 RST is physically tied to 3.3 V
SPI_BAUDRATE = 1000000

# DFPlayer Mini / UART0
DFPLAYER_RX_PIN = 3    # RX / GPIO3 <- DFPlayer TX
DFPLAYER_TX_PIN = 1    # TX / GPIO1 -> DFPlayer RX through approved 1 kOhm
DFPLAYER_BAUD = 9600
# Argument of command 0x09 (select playback source). Sources disagree on the
# value for the TF card (1 or 2): if there is no sound after the first start,
# try the other value.
DFPLAYER_SOURCE = 2
DF_INIT_TIMEOUT_MS = 3000   # how long to wait for the "module online" frame

# EC11 encoder
# A/B are quadrature outputs; SW is the push button.
# GPIO0 is a boot-strap pin: do not press the encoder during power-on/reset.
ENCODER_A_PIN = 5      # D1 / GPIO5
ENCODER_B_PIN = 4      # D2 / GPIO4
ENCODER_SW_PIN = 0     # D3 / GPIO0, button contact switches to GND
ENCODER_DIRECTION = 1
# Valid quadrature transitions per detent (click). Typical EC11: 4 (some: 2).
ENCODER_STEPS_PER_DETENT = 4

# Motor / LEDs
MOTOR_PIN = 16         # D0 / GPIO16 -> HW-532 / LR7843 control input
LED_DATA_PIN = 2       # D4 / GPIO2 -> WS2812 DATA
LED_COUNT = 8

# Two large buttons through the approved analog ladder
BUTTON_ADC_PIN = 0     # A0 / ADC0
BTN_NONE = 0
BTN_PREVIOUS = 1
BTN_NEXT = 2
ADC_PREV_MAX = 100
ADC_NEXT_MIN = 180
ADC_NEXT_MAX = 390

# Player behavior
DEFAULT_VOLUME = 18
MIN_VOLUME = 0
MAX_VOLUME = 30
MAX_TRACKS = 255
DEFAULT_TRACK_COUNT = 15   # used only if the module does not answer command 0x4E
MAX_TAGS = 20
NFC_POLL_MS = 120
NFC_MISSING_MS = 900
BUTTON_DEBOUNCE_MS = 35
TAG_DB_FILE = "tagmap.json"

# Error indication. The ring is OFF until a disc is placed. Errors are shown
# only while a disc is on the reader:
#   disc not matching any album on the SD -> ring blinks RED, no sound, no motor
#   no SD card                            -> ring lit BLUE (steady), no motor
ERR_NONE = 0
ERR_UNKNOWN_DISC = 1
ERR_NO_SD = 2
ERROR_LEVEL = 40       # 0..255 brightness of the error colour
BLINK_MS = 400

# SD card detection. Set to False if your DFPlayer clone confuses the check
# (then the "no SD" indication is disabled and playback is always attempted).
SD_CHECK = True

# Service mode: hold PREVIOUS while resetting the board. The REPL then stays
# on USB and the player does not start (needed to upload new code).
REPL_WINDOW_MS = 1500

# Logs on the NodeMCU flash (the file is deleted when it exceeds the limit).
ERROR_LOG = "error.log"
DF_LOG = "df.log"
LOG_MAX_BYTES = 4096
DF_DEBUG = True        # log raw DFPlayer frames to df.log; set False after bring-up

# ---- Wi-Fi update mode (WebREPL) ------------------------------------------
# Wi-Fi is OFF during normal playback. Hold NEXT while resetting the board to
# enter update mode. Credentials live only on the board, in wifi.json
# (see wifi.json.example); they are not part of the repository.
WIFI_CFG_FILE = "wifi.json"
WIFI_CONNECT_TIMEOUT_MS = 20000
WIFI_MODE_TIMEOUT_MS = 15 * 60 * 1000   # leave update mode (reset) after this time
REBOOT_FLAG = "reboot.flag"             # uploading this file makes the board reset
WIFI_LEVEL = 30                         # ring brightness in update mode
