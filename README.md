# music_player

Compact refrigerator-mounted vinyl/NFC music player.

## Frozen project rule

**One physical vinyl disc = one NTAG215 UID = one digital album folder.**

- The RC522 reads the NTAG215 UID.
- The ESP8266 stores the UID-to-folder association in EEPROM.
- The first unknown tag is assigned to folder `01`, the second to `02`, etc.
- Once assigned, a tag always activates the same folder.
- `Previous` and `Next` are controlled by the ESP8266 using `currentFolder` + `currentTrack`, so they cannot jump to another album.
- EC11 rotation changes DFPlayer volume 0..30.
- EC11 push is Play/Pause.
- Removing the disc for a stable interval stops music, motor and LEDs.
- No Hall sensor is used.

## Approved hardware only

- NodeMCU V3 LoLin ESP8266
- RC522 / MFRC522
- NTAG215
- DFPlayer Mini / MP3-TF-16P
- microSD 16/32 GB FAT32
- GA12-N20 3-6 V ~70 RPM motor
- HW-532 / LR7843 logic MOSFET module
- WS2812B 8 LED ring
- 4 Ohm 3 W passive speaker
- IP5306 USB-C charger/boost module
- 3.7 V 2000 mAh ZLPBEES battery
- 1N5819 flyback diode
- 470-1000 uF rail capacitor
- 100 uF capacitor(s)
- 0.1 uF ceramic capacitors
- 1 kOhm resistor
- 330-470 Ohm resistor
- EC11 encoder with push button
- two approved large tactile buttons
- Dupont/wiring, belt, pulleys, axle/bearing and magnets

No IRF520N is used.

## Firmware

Arduino IDE + ESP8266 board package.

Libraries:

1. `MFRC522`
2. `DFRobotDFPlayerMini`
3. `Adafruit NeoPixel`
4. `SoftwareSerial` supplied by the ESP8266 Arduino core

The main sketch is `music_player.ino`.

## SD card

Use FAT32. Numbered folders:

```text
SD/
├── 01/
│   ├── 001.mp3
│   ├── 002.mp3
│   └── ...
├── 02/
│   ├── 001.mp3
│   ├── 002.mp3
│   └── ...
└── 03/
    ├── 001.mp3
    ├── 002.mp3
    └── ...
```

The firmware asks DFPlayer for the number of files in the active folder. The intended album size is about 10-15 tracks.

## Final pin map

| Function | NodeMCU | ESP8266 GPIO | Module |
|---|---:|---:|---|
| RC522 SCK | D5 | GPIO14 | RC522 SCK |
| RC522 MISO | D6 | GPIO12 | RC522 MISO |
| RC522 MOSI | D7 | GPIO13 | RC522 MOSI |
| RC522 SDA/SS | D8 | GPIO15 | RC522 SDA/SS |
| RC522 RST | 3.3V | — | RC522 RST |
| DFPlayer RX | D2 | GPIO4 | DFPlayer RX through 1k |
| DFPlayer TX | RX | GPIO3 | DFPlayer TX |
| Encoder A | D1 | GPIO5 | EC11 A |
| Encoder B | D3 | GPIO0 | EC11 B |
| Encoder SW | D4 | GPIO2 | EC11 push |
| Motor control | D0 | GPIO16 | HW-532/LR7843 input |
| WS2812 DATA | TX | GPIO1 | Ring DATA |
| Track buttons | A0 | ADC | analog resistor ladder |

### Important boot/upload note

D3/GPIO0 and D4/GPIO2 are ESP8266 boot-strapping pins. Keep the EC11 released during power-up/reset. Do not press the encoder during flashing.

The NodeMCU `RX` pin is shared with the USB-UART converter. For normal standalone operation, disconnect USB after flashing. If the DFPlayer TX wire is already installed, temporarily disconnect that one wire during firmware upload to avoid contention with the USB-UART TX line.

## Power

```text
USB-C
  |
  v
IP5306
  |---- B+ / B- ---- 3.7 V battery
  |
  +---- 5 V BUS --------------------+
                                    |
          +-------------------------+------------------+
          |                         |                  |
       NodeMCU VIN             DFPlayer VCC       WS2812 5V
          |                         |                  |
       3.3V rail                 speaker           ring
          |
        RC522 VCC

5V BUS -> motor -> motor MOSFET -> GND
All GNDs common.
```

RC522 is powered from NodeMCU 3.3 V, never 5 V.

DFPlayer speaker is connected directly between `SPK1` and `SPK2`. Neither speaker wire goes to GND.

## First startup behavior

1. Flash firmware.
2. Prepare SD card.
3. Put the first finished vinyl/tag on the RC522 area.
4. Its UID is automatically stored as folder `01`.
5. The next unknown tag becomes folder `02`, etc.
6. Do not move tags between physical discs after assignment unless the EEPROM mapping is intentionally reset in firmware.
