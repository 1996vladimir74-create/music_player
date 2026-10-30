# music_player — MicroPython

Полностью Python-прошивка для холодильного мини-проигрывателя с физическими виниловыми дисками/NFC.

## Зафиксированное правило проекта

**1 физический диск = 1 NTAG215 UID = 1 цифровой альбом = 1 папка на microSD.**

- RC522 читает UID NTAG215.
- ESP8266 сохраняет соответствие UID → папка в `tagmap.json` во внутренней файловой системе MicroPython.
- Первый неизвестный тег получает папку `01`, следующий `02` и т.д.
- После сохранения один и тот же UID всегда открывает ту же папку.
- `Previous` и `Next` работают только через `current_folder + current_track`.
- Команды глобального `next()`/`previous()` DFPlayer для переключения альбомов не используются.
- EC11: вращение = громкость 0–30, нажатие = Play/Pause.
- При устойчивом отсутствии NFC-тега останавливаются музыка, мотор и WS2812.
- Hall sensor не используется.

## Язык и платформа

- **Язык:** Python / MicroPython.
- **Плата:** NodeMCU V3 LoLin ESP8266.
- **Среда выполнения:** MicroPython ESP8266.
- Никаких Arduino `.ino`, C/C++ библиотек и установки внешних Python-пакетов на плату не требуется.
- В репозитории находятся собственные минимальные драйверы `mfrc522.py` и `dfplayer.py`.
- `neopixel` берётся из стандартной поставки MicroPython.

## Утверждённое железо — без добавления новых компонентов

- NodeMCU V3 LoLin ESP8266
- RC522 / MFRC522
- NTAG215
- DFPlayer Mini / MP3-TF-16P
- microSD 16/32 GB FAT32
- GA12-N20 3–6 V, около 70 RPM
- HW-532 / LR7843 logic-level MOSFET module
- WS2812B 8 LED ring
- 4 Ω 3 W passive speaker
- IP5306 USB-C charger/boost module
- 3.7 V 2000 mAh ZLPBEES battery
- 1N5819 flyback diode
- 470–1000 µF capacitor on 5 V rail
- 100 µF capacitor(s)
- 0.1 µF ceramic capacitors
- 1 kΩ resistor
- 330–470 Ω resistor
- EC11 encoder with push button
- two approved large tactile buttons
- Dupont wires, belt, pulleys, axle/bearing, magnets

**IRF520N не используется.**

## Файлы проекта

```text
music_player/
├── main.py          # основной цикл проигрывателя
├── config.py        # фиксированная распайка и параметры
├── mfrc522.py       # собственный MicroPython-драйвер RC522
├── dfplayer.py      # собственный MicroPython-драйвер DFPlayer
├── deploy.py        # Python-скрипт загрузки файлов с ПК
├── README.md
├── WIRING.md
├── SD_STRUCTURE.md
└── SELF_TEST.md
```

На NodeMCU загружаются четыре файла: `main.py`, `config.py`, `mfrc522.py`, `dfplayer.py`. `main.py` запускается MicroPython автоматически после перезагрузки.

## Финальная распайка

| Функция | NodeMCU | GPIO |
|---|---:|---:|
| RC522 SCK | D5 | GPIO14 |
| RC522 MISO | D6 | GPIO12 |
| RC522 MOSI | D7 | GPIO13 |
| RC522 SDA/SS | D8 | GPIO15 |
| RC522 RST | 3.3V | — |
| DFPlayer RX | TX | GPIO1 через 1 kΩ |
| DFPlayer TX | RX | GPIO3 |
| EC11 A | D1 | GPIO5 |
| EC11 B | D3 | GPIO0 |
| EC11 SW | D2 | GPIO4 |
| Motor control | D0 | GPIO16 |
| WS2812 DATA | D4 | GPIO2 |
| Previous/Next | A0 | ADC0 |

DFPlayer использует UART0 полностью: GPIO1/TX → DFPlayer RX и GPIO3/RX ← DFPlayer TX. Поэтому REPL UART0 отключается программой после старта.

WS2812 DATA перенесён на D4/GPIO2. GPIO2 является boot strap pin и должен оставаться HIGH во время запуска; вход DATA кольца не должен быть притянут к GND.

## SD-карта

FAT32:

```text
SD/
├── 01/
│   ├── 001.mp3
│   ├── 002.mp3
│   ├── 003.mp3
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

DFPlayer использует `playFolder(folder, file)`. Для определения числа треков активного альбома прошивка использует команду `0x4E`; если конкретный клон DFPlayer не отвечает, применяется резервный лимит 15 треков.

## Логика работы

```text
NTAG215 на диске
      ↓
RC522 → UID
      ↓
UID → tagmap.json
      ↓
folder 01/02/03...
      ↓
track = 001
      ↓
DFPlayer
      ├── Previous → предыдущий трек этой папки
      ├── Next     → следующий трек этой папки
      └── конец трека → следующий трек этой папки
```

При замене диска старый альбом останавливается, новый UID становится активным, выбирается его папка и начинается первый трек.

## Загрузка

### Вариант 1 — готовый Python-скрипт

На ПК установить `mpremote`, затем из папки репозитория:

```text
python deploy.py COM3
```

Если порт другой, подставить его вместо `COM3`.

### Вариант 2 — вручную

Скопировать на файловую систему NodeMCU:

```text
main.py
config.py
mfrc522.py
dfplayer.py
```

## Установка MicroPython

На новую NodeMCU сначала один раз устанавливается стандартная прошивка `ESP8266_GENERIC` подходящей версии MicroPython. После этого проект работает как обычные `.py` файлы.

## Важное по boot-пинам

GPIO0 используется EC11 B и является boot strap pin. На EC11 используется внутренний pull-up, поэтому **при включении/сбросе не нажимать EC11**.

GPIO2 используется DATA кольца WS2812 и должен оставаться HIGH во время запуска ESP8266. Не подключать DATA кольца к GND.

GPIO15 используется RC522 SS и должен оставаться LOW при старте; NodeMCU обеспечивает требуемое состояние для нормальной загрузки.

## Сброс привязок NFC

Файл `tagmap.json` хранит UID → папка. Если нужно начать нумерацию альбомов заново, удалить `tagmap.json` с файловой системы NodeMCU. После следующего запуска первый неизвестный тег снова получит `01`.
