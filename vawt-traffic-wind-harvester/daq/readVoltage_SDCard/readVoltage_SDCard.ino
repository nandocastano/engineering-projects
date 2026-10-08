// readVoltage_SDCard.ino
// Change-triggered voltage logger for the VAWT test rig (Arduino Uno + SD module).
// Logging behaviour:
//   - 10 k / 2 k divider on A0 scales up to ~29 V into the 5 V ADC range
//   - a sample is written only when the voltage moves by more than THRESHOLD_V
//   - a zero "heartbeat" row is written every 10 min so a flat line can be told
//     apart from a dead logger
//   - a new voltN.csv is created at every power-up
//   - no RTC: timestamps are elapsed time (hh:mm:ss) since power-up
// Wiring: SD module CS on D10 (SPI on D11/D12/D13), divider midpoint on A0.

#include <SPI.h>
#include <SD.h>

const uint8_t  CS_PIN     = 10;
const uint8_t  ANALOG_PIN = A0;
const float    R1 = 10000.0f;          // upper divider resistor (ohm)
const float    R2 = 2000.0f;           // lower divider resistor (ohm)
const float    ADC_REF_V = 4.9f;       // measured 5 V rail of the rig; adjust per board
const float    THRESHOLD_V = 0.0005f;  // minimum change to log
const unsigned long HEARTBEAT_MS = 600000UL;

char filename[16];
float prevVoltage = 0.0f;
unsigned long lastLogMs = 0;

float readVoltage() {
  const int raw = analogRead(ANALOG_PIN);
  return raw * (ADC_REF_V / 1023.0f) * ((R1 + R2) / R2);
}

void formatElapsed(unsigned long ms, char *out, size_t n) {
  const unsigned long s = ms / 1000UL;
  snprintf(out, n, "%02lu:%02lu:%02lu", s / 3600UL, (s / 60UL) % 60UL, s % 60UL);
}

bool appendRow(const char *line) {
  File f = SD.open(filename, FILE_WRITE);
  if (!f) { Serial.println(F("SD open failed")); return false; }
  f.println(line);
  f.close();
  Serial.println(line);
  return true;
}

void logRow(unsigned long now, float v) {
  char t[12], row[40], num[12];
  formatElapsed(now, t, sizeof t);
  dtostrf(v, 1, 3, num);
  snprintf(row, sizeof row, "%s,%s", t, num);
  if (appendRow(row)) lastLogMs = now;
}

void setup() {
  Serial.begin(9600);
  pinMode(CS_PIN, OUTPUT);
  if (!SD.begin(CS_PIN)) { Serial.println(F("SD init failed")); while (true) {} }
  for (int i = 1; i < 10000; i++) {
    snprintf(filename, sizeof filename, "volt%d.csv", i);   // 8.3 names: SD library limit
    if (!SD.exists(filename)) break;
  }
  appendRow("Elapsed(hh:mm:ss),Voltage(V)");
}

void loop() {
  const unsigned long now = millis();
  const float v = readVoltage();
  if (fabsf(v - prevVoltage) > THRESHOLD_V) {
    logRow(now, v);
    prevVoltage = v;
  } else if (now - lastLogMs >= HEARTBEAT_MS) {
    logRow(now, 0.0f);
  }
}
