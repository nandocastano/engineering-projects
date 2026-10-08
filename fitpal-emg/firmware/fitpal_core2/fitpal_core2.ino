/*
  FitPal: repetition-level muscle-activation feedback on an M5Stack Core2 with a Grove EMG sensor.

  Wiring: sensor VOUT -> G35, VCC -> 5 V, GND -> GND.

  Structure
  - A 1 kHz sampler runs in its own FreeRTOS task on core 0, so drawing on the display can
    never delay a sample. Each sample is the mean of four ADC reads, converted to millivolts
    with analogReadMilliVolts().
  - The signal chain (notch, band limits, RMS envelope, %MVC normalisation, repetition
    detector) lives in emg_dsp.h. It has no Arduino dependency and is compiled and tested on a
    PC against a Python reference (see tests/ and analysis/).
  - A repetition is counted once, when it ends, and judged on its own peak.
  - Cloud publishing (optional, FITPAL_CLOUD) is limited to 2 Hz; credentials are read from
    secrets.h, which is not committed.

  Buttons: A = calibrate (3 s rest, then 3 s maximal contraction), B = start / stop a set,
           C = change exercise.
  Build:   Arduino IDE, board "M5Core2", library M5Core2 (plus ArduinoIoTCloud when
           FITPAL_CLOUD is defined).
  Status:  the DSP header is verified on a PC. The sketch compiles for the M5Stack Core2 with
           ESP32 Arduino core 2.0.17 and the M5Core2 library 0.2.0, without FITPAL_CLOUD. It has
           not been run on the board or on recorded EMG.
*/
#include <M5Core2.h>
#include "config.h"
#include "emg_dsp.h"
// #define FITPAL_CLOUD            // enable once secrets.h and your Arduino Cloud Thing exist
#ifdef FITPAL_CLOUD
#include "thingProperties.h"
#endif

enum Cmd : uint8_t { CMD_NONE, CMD_REST, CMD_MVC, CMD_FINISH, CMD_RUN, CMD_STOP };
static fitpal::Pipeline chain;
static QueueHandle_t repQ;
static volatile Cmd g_cmd = CMD_NONE;
static volatile float g_env = 0, g_act = 0;
static volatile int g_calOk = -1;               // -1 pending, 0 failed, 1 ok

// ---------------- sampler: 1 kHz, core 0 ----------------
static void samplerTask(void *) {
  TickType_t last = xTaskGetTickCount();
  const uint32_t t0 = millis();
  for (;;) {
    vTaskDelayUntil(&last, 1);                  // 1 tick = 1 ms on ESP32 Arduino
    switch (g_cmd) {
      case CMD_REST:   chain.startRestCapture(); break;
      case CMD_MVC:    chain.startMvcCapture(); break;
      case CMD_FINISH: g_calOk = chain.finishCapture() ? 1 : 0; break;
      case CMD_RUN:    chain.det.reset(); break;
      default: break;
    }
    g_cmd = CMD_NONE;
    float mv = 0;
    for (int i = 0; i < OVERSAMPLE; i++) mv += analogReadMilliVolts(EMG_PIN);
    mv /= OVERSAMPLE;
    fitpal::Rep r;
    if (chain.push(millis() - t0, mv, r)) xQueueSend(repQ, &r, 0);
    g_env = chain.env; g_act = chain.act;
  }
}

// ---------------- UI state ----------------
enum UiState { UI_HOME, UI_CAL_REST, UI_CAL_MVC, UI_SET };
static UiState ui = UI_HOME;
static int profile = 0, reps = 0, effReps = 0;
static float lastPeak = 0, peaks[64]; static int nPeaks = 0;
static uint32_t tState = 0, tVib = 0, tCloud = 0, tBar = 0;
static bool calibrated = false;

static void drawHome() {
  M5.Lcd.fillScreen(BLACK); M5.Lcd.setTextColor(WHITE, BLACK);
  M5.Lcd.setTextSize(3); M5.Lcd.drawString("FITPAL", 100, 20);
  M5.Lcd.setTextSize(2); M5.Lcd.drawString(PROFILES[profile].name, 20, 80);
  M5.Lcd.drawString(calibrated ? "calibrated" : "A: calibrate first", 20, 110);
  M5.Lcd.drawString("B: start set   C: exercise", 20, 190);
  M5.Lcd.setTextSize(1); M5.Lcd.drawString("A calibrate | B start/stop | C exercise", 40, 225);
}
static void drawSetFrame() {
  M5.Lcd.fillScreen(BLACK); M5.Lcd.setTextColor(WHITE, BLACK); M5.Lcd.setTextSize(2);
  M5.Lcd.drawString(PROFILES[profile].name, 10, 8);
  M5.Lcd.drawRect(10, 200, 300, 24, WHITE);
}
static void drawCounters(bool good) {
  M5.Lcd.fillRect(0, 40, 320, 150, good ? DARKGREEN : MAROON);
  M5.Lcd.setTextColor(WHITE, good ? DARKGREEN : MAROON);
  M5.Lcd.setTextSize(2); M5.Lcd.drawString(good ? "EFFECTIVE" : "BELOW TARGET", 10, 50);
  M5.Lcd.setTextSize(5); M5.Lcd.drawNumber(effReps, 10, 90);
  M5.Lcd.setTextSize(2); M5.Lcd.drawString("effective of", 100, 100); M5.Lcd.drawNumber(reps, 250, 100);
  M5.Lcd.drawString("last peak", 10, 160); M5.Lcd.drawNumber((int)(lastPeak * 100), 150, 160); M5.Lcd.drawString("% MVC", 190, 160);
}
static void drawBar(float a) {
  int w = (int)(298 * constrain(a, 0.0f, 1.0f));
  M5.Lcd.fillRect(11, 201, w, 22, GREEN);
  M5.Lcd.fillRect(11 + w, 201, 298 - w, 22, BLACK);
  // target marker
  int tx = 11 + (int)(298 * PROFILES[profile].target);
  M5.Lcd.drawFastVLine(tx, 196, 32, YELLOW);
}
static void vibrate(uint32_t ms) { M5.Axp.SetLDOEnable(3, true); tVib = millis() + ms; }

// least-squares slope of peak vs rep index, in percentage points per rep
static float peakTrend() {
  if (nPeaks < 3) return 0;
  float sx = 0, sy = 0, sxx = 0, sxy = 0;
  for (int i = 0; i < nPeaks; i++) { sx += i; sy += peaks[i]; sxx += i * i; sxy += i * peaks[i]; }
  const float d = nPeaks * sxx - sx * sx;
  return d != 0 ? 100.0f * (nPeaks * sxy - sx * sy) / d : 0;
}
static void showSummary() {
  M5.Lcd.fillScreen(BLACK); M5.Lcd.setTextColor(WHITE, BLACK); M5.Lcd.setTextSize(2);
  M5.Lcd.drawString("SET SUMMARY", 10, 10);
  M5.Lcd.drawString("reps", 10, 60);      M5.Lcd.drawNumber(reps, 200, 60);
  M5.Lcd.drawString("effective", 10, 90); M5.Lcd.drawNumber(effReps, 200, 90);
  float mean = 0; for (int i = 0; i < nPeaks; i++) mean += peaks[i]; if (nPeaks) mean /= nPeaks;
  M5.Lcd.drawString("mean peak %MVC", 10, 120); M5.Lcd.drawNumber((int)(mean * 100), 250, 120);
  M5.Lcd.drawString("peak trend /rep", 10, 150); M5.Lcd.drawFloat(peakTrend(), 1, 250, 150);
  M5.Lcd.setTextSize(1); M5.Lcd.drawString("a falling trend suggests fatigue", 10, 190);
  M5.Lcd.drawString("press B", 10, 215);
}

void setup() {
  M5.begin();
  Serial.begin(115200);
  analogSetPinAttenuation(EMG_PIN, ADC_11db);
  fitpal::PipelineConfig pc; pc.fs = FS_HZ; pc.mains_hz = MAINS_HZ;
  chain.begin(pc);
  repQ = xQueueCreate(16, sizeof(fitpal::Rep));
  xTaskCreatePinnedToCore(samplerTask, "emg", 4096, nullptr, 3, nullptr, 0);
#ifdef FITPAL_CLOUD
  initProperties();
  ArduinoCloud.begin(ArduinoIoTPreferredConnection);
#endif
  drawHome();
}

void loop() {
  M5.update();
#ifdef FITPAL_CLOUD
  ArduinoCloud.update();
#endif
  const uint32_t now = millis();
  if (tVib && now >= tVib) { M5.Axp.SetLDOEnable(3, false); tVib = 0; }

  switch (ui) {
    case UI_HOME:
      if (M5.BtnC.wasPressed()) { profile = (profile + 1) % N_PROFILES; drawHome(); }
      if (M5.BtnA.wasPressed()) {
        g_cmd = CMD_REST; ui = UI_CAL_REST; tState = now;
        M5.Lcd.fillScreen(BLACK); M5.Lcd.setTextSize(3); M5.Lcd.drawString("RELAX...", 60, 100);
      }
      if (M5.BtnB.wasPressed() && calibrated) {
        chain.det.cfg.target = PROFILES[profile].target;
        chain.det.cfg.on_thr = PROFILES[profile].on_thr; chain.det.cfg.off_thr = PROFILES[profile].off_thr;
        reps = effReps = nPeaks = 0; lastPeak = 0; g_cmd = CMD_RUN; ui = UI_SET;
        drawSetFrame(); drawCounters(true);
      }
      break;
    case UI_CAL_REST:
      if (now - tState >= CALIB_REST_MS) {
        g_cmd = CMD_FINISH; delay(5);
        while (g_cmd != CMD_NONE) delay(1);
        g_cmd = CMD_MVC; ui = UI_CAL_MVC; tState = now;
        M5.Lcd.fillScreen(BLACK); M5.Lcd.setTextSize(3); M5.Lcd.drawString("SQUEEZE HARD", 20, 100);
      }
      break;
    case UI_CAL_MVC:
      if (now - tState >= CALIB_MVC_MS) {
        g_calOk = -1; g_cmd = CMD_FINISH;
        while (g_calOk < 0) delay(1);
        calibrated = (g_calOk == 1); ui = UI_HOME; drawHome();
        if (!calibrated) { M5.Lcd.setTextColor(RED, BLACK); M5.Lcd.drawString("failed: check electrodes", 20, 140); }
      }
      break;
    case UI_SET: {
      fitpal::Rep r;
      while (xQueueReceive(repQ, &r, 0) == pdTRUE) {
        reps++; if (r.effective) effReps++;
        lastPeak = r.peak; if (nPeaks < 64) peaks[nPeaks++] = r.peak;
        drawCounters(r.effective); if (r.effective) vibrate(150);
#ifdef FITPAL_CLOUD
        effectivereps = effReps; effectiveornot = r.effective;
#endif
      }
      if (now - tBar >= 50) { tBar = now; drawBar(g_act); }
#ifdef FITPAL_CLOUD
      if (now - tCloud >= CLOUD_PERIOD_MS) { tCloud = now; mvwifi = g_act * 100.0f; }
#endif
      if (M5.BtnB.wasPressed()) { g_cmd = CMD_STOP; showSummary(); ui = UI_HOME; while (!M5.BtnB.wasPressed()) { M5.update(); delay(10); } drawHome(); }
      break;
    }
  }
}
