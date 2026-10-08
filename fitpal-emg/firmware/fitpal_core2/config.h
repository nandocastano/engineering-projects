#pragma once
// FitPal configuration. Edit values here rather than in the sketch.
#define EMG_PIN            35      // Grove EMG VOUT -> G35
#define FS_HZ              1000    // sampling rate
#define OVERSAMPLE         4       // ADC reads averaged per sample (ESP32 ADC is noisy)
#define MAINS_HZ           50.0f   // grid frequency: 50 Hz (UAE), 60 Hz (Colombia, US)
#define SESSION_WINDOW_MS  100     // RMS window is fixed at 100 samples (see emg_dsp.h)
#define CLOUD_PERIOD_MS    500     // publish at 2 Hz instead of every loop
#define CALIB_REST_MS      3000
#define CALIB_MVC_MS       3000

struct ExerciseProfile { const char *name; float target; float on_thr; float off_thr; };
// target: fraction of the user's own MVC that a repetition must reach to count as effective.
// on_thr / off_thr: hysteresis band of the repetition detector.
// The defaults (0.60 for curls, 0.54 for squats) are working values, not physiological
// constants; set them from a coach's guidance or from recorded data.
static const ExerciseProfile PROFILES[] = {
  {"BICEP CURL", 0.60f, 0.30f, 0.15f},
  {"SQUAT",      0.54f, 0.28f, 0.14f},
};
static const int N_PROFILES = sizeof(PROFILES) / sizeof(PROFILES[0]);
