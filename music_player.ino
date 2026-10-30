/*
 * music_player
 * Refrigerator vinyl/NFC music player
 *
 * Hardware baseline is intentionally frozen to the approved BOM.
 *
 * Core rule:
 *   One physical disc = one NTAG215 UID = one SD folder.
 *   The ESP8266 stores the UID-to-folder association in EEPROM.
 *   Previous/Next are handled by the ESP8266 using currentFolder/currentTrack,
 *   so they never cross into another album.
 */

#include <Arduino.h>
#include <SPI.h>
#include <MFRC522.h>
#include <SoftwareSerial.h>
#include <DFRobotDFPlayerMini.h>
#include <Adafruit_NeoPixel.h>
#include <EEPROM.h>

#define RFID_SS_PIN      D8
#define RFID_RST_PIN     MFRC522::UNUSED_PIN

#define DF_RX_PIN        3       // NodeMCU RX / GPIO3, receives DFPlayer TX
#define DF_TX_PIN        D2      // NodeMCU D2 / GPIO4, sends to DFPlayer RX

#define ENCODER_A_PIN    D1      // GPIO5
#define ENCODER_B_PIN    D3      // GPIO0
#define ENCODER_SW_PIN   D4      // GPIO2

#define MOTOR_PIN        D0      // GPIO16 -> HW-532/LR7843 input/gate
#define LED_DATA_PIN     1       // GPIO1 / TX -> WS2812 DATA
#define BUTTON_ADC_PIN   A0

#define LED_COUNT        8
#define DEFAULT_VOLUME   18
#define MAX_VOLUME       30
#define MIN_VOLUME       0
#define MAX_TRACKS       255
#define MAX_TAGS         20
#define NFC_POLL_MS      120
#define NFC_MISSING_MS   900
#define BUTTON_DEBOUNCE  35
#define ENCODER_STEP_MS  2
#define EEPROM_MAGIC     0x4D505231UL
#define EEPROM_SIZE      512

SoftwareSerial dfSerial(DF_RX_PIN, DF_TX_PIN);
DFRobotDFPlayerMini dfPlayer;
MFRC522 rfid(RFID_SS_PIN, RFID_RST_PIN);
Adafruit_NeoPixel ring(LED_COUNT, LED_DATA_PIN, NEO_GRB + NEO_KHZ800);

struct TagRecord {
  uint8_t folder;
  uint8_t uidSize;
  uint8_t uid[10];
};

struct TagDatabase {
  uint32_t magic;
  uint8_t count;
  TagRecord records[MAX_TAGS];
};

TagDatabase tagDb;

uint8_t currentFolder = 0;
uint16_t currentTrack = 0;
uint16_t currentTrackCount = 0;
uint8_t volumeLevel = DEFAULT_VOLUME;
bool albumActive = false;
bool paused = false;

uint8_t activeUid[10];
uint8_t activeUidSize = 0;
unsigned long lastTagSeenMs = 0;
unsigned long lastNfcPollMs = 0;

uint8_t encoderLastAB = 0;
unsigned long lastEncoderMs = 0;
bool encoderButtonLast = HIGH;
unsigned long encoderButtonChangedMs = 0;
bool encoderButtonHandled = false;

enum AnalogButton : uint8_t {
  BTN_NONE,
  BTN_PREVIOUS,
  BTN_NEXT,
  BTN_BOTH
};
AnalogButton analogButtonLast = BTN_NONE;
unsigned long analogButtonChangedMs = 0;
bool analogButtonHandled = false;

void saveTagDatabase() {
  EEPROM.put(0, tagDb);
  EEPROM.commit();
}

void loadTagDatabase() {
  EEPROM.begin(EEPROM_SIZE);
  EEPROM.get(0, tagDb);

  if (tagDb.magic != EEPROM_MAGIC || tagDb.count > MAX_TAGS) {
    memset(&tagDb, 0, sizeof(tagDb));
    tagDb.magic = EEPROM_MAGIC;
    tagDb.count = 0;
    saveTagDatabase();
  }
}

bool uidEquals(const uint8_t *a, uint8_t aSize, const uint8_t *b, uint8_t bSize) {
  if (aSize != bSize) return false;
  for (uint8_t i = 0; i < aSize; i++) {
    if (a[i] != b[i]) return false;
  }
  return true;
}

int findFolderForUid(const uint8_t *uid, uint8_t uidSize) {
  for (uint8_t i = 0; i < tagDb.count; i++) {
    if (uidEquals(uid, uidSize, tagDb.records[i].uid, tagDb.records[i].uidSize)) {
      return tagDb.records[i].folder;
    }
  }
  return -1;
}

int registerUid(const uint8_t *uid, uint8_t uidSize) {
  if (uidSize > 10 || tagDb.count >= MAX_TAGS) return -1;

  uint8_t folder = tagDb.count + 1;
  TagRecord &record = tagDb.records[tagDb.count];
  record.folder = folder;
  record.uidSize = uidSize;
  memset(record.uid, 0, sizeof(record.uid));
  memcpy(record.uid, uid, uidSize);
  tagDb.count++;
  saveTagDatabase();
  return folder;
}

void ledsOff() {
  ring.clear();
  ring.show();
}

void ledsOnForAlbum(uint8_t folder) {
  uint8_t level = 18 + (folder % 5) * 10;
  for (uint8_t i = 0; i < LED_COUNT; i++) {
    ring.setPixelColor(i, ring.Color(level, level / 2, 0));
  }
  ring.show();
}

void motorStart() {
  digitalWrite(MOTOR_PIN, HIGH);
}

void motorStop() {
  digitalWrite(MOTOR_PIN, LOW);
}

void startHardwareForAlbum(uint8_t folder) {
  motorStart();
  ledsOnForAlbum(folder);
}

void stopHardware() {
  motorStop();
  ledsOff();
}

void playCurrentTrack() {
  if (!albumActive || currentFolder == 0 || currentTrack == 0) return;
  dfPlayer.playFolder(currentFolder, currentTrack);
  paused = false;
}

bool updateTrackCount() {
  if (!albumActive || currentFolder == 0) return false;

  int count = dfPlayer.readFileCountsInFolder(currentFolder);
  if (count > 0 && count <= MAX_TRACKS) {
    currentTrackCount = (uint16_t)count;
    return true;
  }

  // Safe fallback for unusual clones / slow SD initialization.
  currentTrackCount = 15;
  return false;
}

void stopAlbum() {
  if (albumActive) {
    dfPlayer.stop();
  }
  albumActive = false;
  paused = false;
  currentFolder = 0;
  currentTrack = 0;
  currentTrackCount = 0;
  stopHardware();
}

void activateAlbum(const uint8_t *uid, uint8_t uidSize) {
  int folder = findFolderForUid(uid, uidSize);

  if (folder < 0) {
    folder = registerUid(uid, uidSize);
    if (folder < 0) {
      stopAlbum();
      return;
    }
  }

  memcpy(activeUid, uid, uidSize);
  activeUidSize = uidSize;

  currentFolder = (uint8_t)folder;
  currentTrack = 1;
  currentTrackCount = 15;
  albumActive = true;
  paused = false;

  delay(80);
  updateTrackCount();
  if (currentTrackCount == 0) {
    stopAlbum();
    return;
  }

  startHardwareForAlbum(currentFolder);
  playCurrentTrack();
}

void nextTrack() {
  if (!albumActive || currentTrackCount == 0) return;
  currentTrack++;
  if (currentTrack > currentTrackCount) currentTrack = 1;
  playCurrentTrack();
}

void previousTrack() {
  if (!albumActive || currentTrackCount == 0) return;
  if (currentTrack <= 1) currentTrack = currentTrackCount;
  else currentTrack--;
  playCurrentTrack();
}

void togglePause() {
  if (!albumActive) return;
  if (paused) {
    dfPlayer.start();
    paused = false;
  } else {
    dfPlayer.pause();
    paused = true;
  }
}

bool readUidNow(uint8_t *uidOut, uint8_t &uidSizeOut) {
  byte atqa[2];
  byte atqaSize = sizeof(atqa);

  if (rfid.PICC_WakeupA(atqa, &atqaSize) != MFRC522::STATUS_OK) {
    return false;
  }

  if (!rfid.PICC_ReadCardSerial()) {
    return false;
  }

  uidSizeOut = rfid.uid.size;
  if (uidSizeOut > 10) return false;
  memcpy(uidOut, rfid.uid.uidByte, uidSizeOut);

  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
  return true;
}

void pollNfc() {
  if (millis() - lastNfcPollMs < NFC_POLL_MS) return;
  lastNfcPollMs = millis();

  uint8_t uid[10];
  uint8_t uidSize = 0;

  if (readUidNow(uid, uidSize)) {
    lastTagSeenMs = millis();

    bool sameTag = albumActive && uidEquals(uid, uidSize, activeUid, activeUidSize);
    if (!sameTag) {
      stopAlbum();
      activateAlbum(uid, uidSize);
    }
    return;
  }

  if (albumActive && millis() - lastTagSeenMs > NFC_MISSING_MS) {
    stopAlbum();
  }
}

int8_t readEncoderDirection() {
  uint8_t a = digitalRead(ENCODER_A_PIN);
  uint8_t b = digitalRead(ENCODER_B_PIN);
  uint8_t ab = (a << 1) | b;

  if (ab == encoderLastAB) return 0;
  if (millis() - lastEncoderMs < ENCODER_STEP_MS) {
    encoderLastAB = ab;
    return 0;
  }

  int8_t direction = 0;
  if ((encoderLastAB == 0 && ab == 1) ||
      (encoderLastAB == 1 && ab == 3) ||
      (encoderLastAB == 3 && ab == 2) ||
      (encoderLastAB == 2 && ab == 0)) {
    direction = +1;
  } else if ((encoderLastAB == 0 && ab == 2) ||
             (encoderLastAB == 2 && ab == 3) ||
             (encoderLastAB == 3 && ab == 1) ||
             (encoderLastAB == 1 && ab == 0)) {
    direction = -1;
  }

  encoderLastAB = ab;
  lastEncoderMs = millis();
  return direction;
}

void handleEncoder() {
  int8_t direction = readEncoderDirection();
  if (direction != 0 && albumActive) {
    if (direction > 0 && volumeLevel < MAX_VOLUME) volumeLevel++;
    if (direction < 0 && volumeLevel > MIN_VOLUME) volumeLevel--;
    dfPlayer.volume(volumeLevel);
  }

  bool buttonNow = digitalRead(ENCODER_SW_PIN);
  if (buttonNow != encoderButtonLast) {
    encoderButtonChangedMs = millis();
    encoderButtonLast = buttonNow;
  }

  if (buttonNow == LOW && millis() - encoderButtonChangedMs > BUTTON_DEBOUNCE) {
    if (!encoderButtonHandled) {
      togglePause();
      encoderButtonHandled = true;
    }
  }

  if (buttonNow == HIGH) {
    encoderButtonHandled = false;
  }
}

AnalogButton readAnalogButton() {
  int raw = analogRead(BUTTON_ADC_PIN);

  // 3.3V -> 1k -> A0
  // PREV -> 330R -> GND  ~= 0.82V
  // NEXT -> 1k  -> GND  ~= 1.65V
  // No press          ~= 3.3V
  if (raw < 220) return BTN_BOTH;
  if (raw >= 220 && raw < 390) return BTN_PREVIOUS;
  if (raw >= 440 && raw < 650) return BTN_NEXT;
  return BTN_NONE;
}

void handleAnalogButtons() {
  AnalogButton now = readAnalogButton();

  if (now != analogButtonLast) {
    analogButtonChangedMs = millis();
    analogButtonLast = now;
  }

  if (now != BTN_NONE && now != BTN_BOTH &&
      millis() - analogButtonChangedMs > BUTTON_DEBOUNCE) {
    if (!analogButtonHandled) {
      if (now == BTN_PREVIOUS) previousTrack();
      if (now == BTN_NEXT) nextTrack();
      analogButtonHandled = true;
    }
  } else if (now == BTN_NONE) {
    analogButtonHandled = false;
  }
}

void setup() {
  pinMode(MOTOR_PIN, OUTPUT);
  digitalWrite(MOTOR_PIN, LOW);

  pinMode(ENCODER_A_PIN, INPUT_PULLUP);
  pinMode(ENCODER_B_PIN, INPUT_PULLUP);
  pinMode(ENCODER_SW_PIN, INPUT_PULLUP);

  ring.begin();
  ring.setBrightness(32);
  ledsOff();

  loadTagDatabase();

  SPI.begin();
  rfid.PCD_Init();
  delay(50);

  // Two-way software UART: RX=GPIO3, TX=D2/GPIO4.
  // GPIO3 is shared with the NodeMCU USB-UART converter. For normal
  // standalone operation disconnect USB after flashing. If the DFPlayer TX
  // wire is installed, temporarily unplug that wire during firmware upload.
  dfSerial.begin(9600);
  delay(1800);

  dfPlayer.begin(dfSerial, true, true);
  dfPlayer.outputDevice(DFPLAYER_DEVICE_SD);
  dfPlayer.volume(volumeLevel);
  dfPlayer.EQ(DFPLAYER_EQ_NORMAL);
}

void loop() {
  pollNfc();
  handleEncoder();
  handleAnalogButtons();

  while (dfPlayer.available()) {
    dfPlayer.readType();
    dfPlayer.read();
  }

  delay(1);
}
