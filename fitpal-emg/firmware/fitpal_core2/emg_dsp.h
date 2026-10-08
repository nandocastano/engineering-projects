// emg_dsp.h: hardware-independent EMG signal chain for FitPal.
// Header-only, no dynamic allocation, no Arduino dependencies, so the exact code that
// runs on the M5Core2 is also compiled and tested on a PC (see tests/).
//
// Chain:  raw mV -> notch (mains) -> high-pass (motion/DC) -> low-pass (noise)
//         -> moving RMS envelope -> %MVC normalisation -> hysteresis repetition detector
#pragma once
#include <math.h>
#include <stdint.h>

namespace fitpal {

// ---------- biquad (RBJ cookbook, transposed direct form II) ----------
struct Biquad {
  float b0 = 1, b1 = 0, b2 = 0, a1 = 0, a2 = 0, z1 = 0, z2 = 0;
  float process(float x) {
    float y = b0 * x + z1;
    z1 = b1 * x - a1 * y + z2;
    z2 = b2 * x - a2 * y;
    return y;
  }
  void reset() { z1 = z2 = 0; }
  static Biquad make(float b0, float b1, float b2, float a0, float a1, float a2) {
    Biquad q; q.b0 = b0 / a0; q.b1 = b1 / a0; q.b2 = b2 / a0; q.a1 = a1 / a0; q.a2 = a2 / a0; return q;
  }
  static Biquad notch(float fs, float f0, float Q) {
    const float w = 2.0f * (float)M_PI * f0 / fs, c = cosf(w), al = sinf(w) / (2.0f * Q);
    return make(1, -2 * c, 1, 1 + al, -2 * c, 1 - al);
  }
  static Biquad highpass(float fs, float f0, float Q = 0.70710678f) {
    const float w = 2.0f * (float)M_PI * f0 / fs, c = cosf(w), al = sinf(w) / (2.0f * Q);
    return make((1 + c) / 2, -(1 + c), (1 + c) / 2, 1 + al, -2 * c, 1 - al);
  }
  static Biquad lowpass(float fs, float f0, float Q = 0.70710678f) {
    const float w = 2.0f * (float)M_PI * f0 / fs, c = cosf(w), al = sinf(w) / (2.0f * Q);
    return make((1 - c) / 2, 1 - c, (1 - c) / 2, 1 + al, -2 * c, 1 - al);
  }
};

// ---------- moving RMS over a fixed window ----------
template <int N>
struct MovingRms {
  float buf[N] = {0};
  double sum = 0;       // double: no drift over hours at 1 kHz
  int idx = 0, filled = 0;
  float push(float x) {
    const float s = x * x;
    sum += s - buf[idx];
    buf[idx] = s;
    idx = (idx + 1) % N;
    if (filled < N) filled++;
    if (sum < 0) sum = 0;
    return sqrtf((float)(sum / filled));
  }
  void reset() { for (int i = 0; i < N; i++) buf[i] = 0; sum = 0; idx = filled = 0; }
};

// ---------- repetition detector ----------
struct Rep {
  uint32_t start_ms, dur_ms;
  float peak;       // peak activation, fraction of MVC
  float mean;       // mean activation during the rep
  bool effective;   // peak >= target
};

struct RepConfig {
  float on_thr = 0.30f;      // enter ACTIVE above this fraction of MVC
  float off_thr = 0.15f;     // leave ACTIVE below this (hysteresis)
  float target = 0.50f;      // peak needed to count as an "effective" rep
  uint32_t min_dur_ms = 200; // shorter bursts are artefacts
  uint32_t max_dur_ms = 8000;
  uint32_t refractory_ms = 300;
};

struct RepDetector {
  RepConfig cfg;
  bool active = false;
  uint32_t t_start = 0, t_last_end = 0;
  bool have_end = false;
  float peak = 0, sum = 0; uint32_t n = 0;
  // returns true and fills `out` when a rep completes
  bool update(uint32_t t_ms, float a, Rep &out) {
    if (!active) {
      if (a >= cfg.on_thr && (!have_end || t_ms - t_last_end >= cfg.refractory_ms)) {
        active = true; t_start = t_ms; peak = a; sum = a; n = 1;
      }
      return false;
    }
    if (a > peak) peak = a;
    sum += a; n++;
    const uint32_t dur = t_ms - t_start;
    if (a < cfg.off_thr || dur > cfg.max_dur_ms) {
      active = false; t_last_end = t_ms; have_end = true;
      if (dur >= cfg.min_dur_ms) {
        out.start_ms = t_start; out.dur_ms = dur; out.peak = peak; out.mean = sum / n;
        out.effective = peak >= cfg.target;
        return true;
      }
    }
    return false;
  }
  void reset() { active = false; have_end = false; }
};

// ---------- full pipeline ----------
struct PipelineConfig {
  float fs = 1000.0f;
  float mains_hz = 50.0f;   // 50 Hz in the UAE, 60 Hz in Colombia/US: set to your grid frequency
  float hp_hz = 20.0f;
  float lp_hz = 350.0f;
};

class Pipeline {
 public:
  enum Mode { RUN, CAL_REST, CAL_MVC };
  PipelineConfig pc;
  RepDetector det;
  float env = 0;        // RMS envelope, mV
  float act = 0;        // normalised activation, 0..1+ (fraction of MVC)
  float rest = 0;       // envelope at rest (noise floor), mV
  float mvc = 0;        // envelope at maximal contraction, mV
  bool calibrated = false;
  Mode mode = RUN;

  void begin(const PipelineConfig &c = PipelineConfig()) {
    pc = c;
    notch_ = Biquad::notch(pc.fs, pc.mains_hz, 30.0f);
    hp_ = Biquad::highpass(pc.fs, pc.hp_hz);
    lp_ = Biquad::lowpass(pc.fs, pc.lp_hz);
    rms_.reset(); det.reset(); warm_ = 0;
  }
  void startRestCapture() { mode = CAL_REST; acc_ = 0; cnt_ = 0; }
  void startMvcCapture() { mode = CAL_MVC; maxenv_ = 0; }
  // returns false if the captured data are not plausible (user did not contract / sensor off)
  bool finishCapture() {
    bool ok = true;
    if (mode == CAL_REST) { rest = cnt_ ? (float)(acc_ / cnt_) : 0; }
    if (mode == CAL_MVC) { mvc = maxenv_; ok = (mvc > 2.0f * rest + 1.0f); calibrated = ok; }
    mode = RUN;
    return ok;
  }
  void setCalibration(float rest_mv, float mvc_mv) { rest = rest_mv; mvc = mvc_mv; calibrated = mvc > rest; }

  // feed one sample (millivolts) at fs. Returns true if a rep completed (written to `out`).
  bool push(uint32_t t_ms, float mv, Rep &out) {
    float x = notch_.process(mv);
    x = hp_.process(x);
    x = lp_.process(x);
    // Warm-up: the high-pass sees the sensor's DC offset as a step. Let it settle before the
    // envelope starts, otherwise the first calibration capture is contaminated.
    if (warm_ < WARMUP_SAMPLES) { warm_++; return false; }
    env = rms_.push(x);
    if (mode == CAL_REST) { acc_ += env; cnt_++; }
    if (mode == CAL_MVC && env > maxenv_) maxenv_ = env;
    if (calibrated && mvc > rest) {
      act = (env - rest) / (mvc - rest);
      if (act < 0) act = 0;
      if (mode == RUN) return det.update(t_ms, act, out);
    }
    return false;
  }

 private:
  Biquad notch_, hp_, lp_;
  MovingRms<100> rms_;     // 100 ms at 1 kHz
  static const uint32_t WARMUP_SAMPLES = 500;
  uint32_t warm_ = 0;
  double acc_ = 0; uint32_t cnt_ = 0; float maxenv_ = 0;
};

}  // namespace fitpal
