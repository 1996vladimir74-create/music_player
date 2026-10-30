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

# EC11 encoder
ENCODER_A_PIN = 5      # D1 / GPIO5
ENCODER_B_PIN = 0      # D3 / GPIO0
ENCODER_SW_PIN = 4     # D2 / GPIO4
ENCODER_DIRECTION = 1

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
DEFAULT_TRACK_COUNT = 15
MAX_TAGS = 20
NFC_POLL_MS = 120
NFC_MISSING_MS = 900
BUTTON_DEBOUNCE_MS = 35
TAG_DB_FILE = "tagmap.json"

# DFPlayer event code for track-finished feedback
DFPLAYER_PLAY_FINISHED = 3
