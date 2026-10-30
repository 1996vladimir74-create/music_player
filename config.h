#pragma once

#define PROJECT_NAME "music_player"
#define CONTROLLER "NodeMCU V3 LoLin ESP8266"
#define NFC_TAG "NTAG215"
#define RFID_READER "RC522 / MFRC522"
#define AUDIO_MODULE "DFPlayer Mini / MP3-TF-16P"
#define MOTOR "GA12-N20 3-6V ~70RPM @5V"
#define MOTOR_DRIVER "HW-532 / LR7843"
#define LED_RING "WS2812B 8x5050"
#define BATTERY "3.7V 2000mAh ZLPBEES"
#define POWER_MODULE "IP5306 USB-C charger/boost"
#define SPEAKER "4 Ohm 3W"

// Approved passive parts already in the BOM.
#define DFPLAYER_RX_SERIES_RESISTOR_OHM 1000
#define WS2812_DATA_RESISTOR_OHM 330
#define BUTTON_LADDER_LOW_OHM 330
#define BUTTON_LADDER_HIGH_OHM 1000
#define RAIL_CAPACITOR_UF 470
#define LOCAL_CAPACITOR_UF 100
#define MOTOR_DIODE "1N5819"

// Mechanical target from the approved GA12-N20 motor:
// 10 mm motor pulley -> 25 mm platter pulley ~= 28 RPM from ~70 RPM motor speed.
