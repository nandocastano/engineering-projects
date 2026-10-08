#!/usr/bin/env python3
"""Synthetic-EMG evaluation of the FitPal signal chain.

The script generates surface-EMG-like sessions that contain the artefacts the chain has to
survive (mains hum, baseline wander, motion spikes, differences in subject gain, fatigue) and
runs three things over them:

  1. a reference Python implementation of the chain,
  2. the C++ header that runs on the device (emg_dsp.h, compiled with g++),
  3. a fixed-threshold detector, as the simplest alternative to compare against.

Parity between (1) and (2) is checked on one session; detection scores of (1) and (3) are
computed over 60 sessions. The signal model is ours, so none of this replaces recordings from
the physical sensor.

Run from the repository root:  python3 analysis/simulate_and_evaluate.py
Needs numpy, scipy, matplotlib and g++.
"""
import json
import os
import subprocess

import numpy as np
from scipy.signal import lfilter

FS = 1000
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "analysis", "output")
FIG = os.path.join(ROOT, "report", "figures")
IMG = os.path.join(ROOT, "images")
for d in (OUT, FIG, IMG):
    os.makedirs(d, exist_ok=True)

BLUE, RED, GREEN, GREY = "#1F4E9E", "#B03A2E", "#2E7D32", "#475569"


# ---- biquads (RBJ cookbook), same formulas as emg_dsp.h -------------------------------------
def _norm(b, a):
    b = np.array(b, float)
    a = np.array(a, float)
    return b / a[0], a / a[0]


def notch(fs, f0, q):
    w = 2 * np.pi * f0 / fs
    c, al = np.cos(w), np.sin(w) / (2 * q)
    return _norm([1, -2 * c, 1], [1 + al, -2 * c, 1 - al])


def highpass(fs, f0, q=0.70710678):
    w = 2 * np.pi * f0 / fs
    c, al = np.cos(w), np.sin(w) / (2 * q)
    return _norm([(1 + c) / 2, -(1 + c), (1 + c) / 2], [1 + al, -2 * c, 1 - al])


def lowpass(fs, f0, q=0.70710678):
    w = 2 * np.pi * f0 / fs
    c, al = np.cos(w), np.sin(w) / (2 * q)
    return _norm([(1 - c) / 2, 1 - c, (1 - c) / 2], [1 + al, -2 * c, 1 - al])


def moving_rms(x, n=100):
    s = np.cumsum(np.r_[0, x * x])
    out = np.empty_like(x)
    for i in range(len(x)):
        lo = max(0, i - n + 1)
        out[i] = np.sqrt((s[i + 1] - s[lo]) / (i + 1 - lo))
    return out


def reps_from_activation(t_ms, a, on=0.30, off=0.15, target=0.5, min_dur=200, max_dur=8000, refr=300):
    reps = []
    active = False
    last_end = None
    for t, v in zip(t_ms, a):
        if not active:
            if v >= on and (last_end is None or t - last_end >= refr):
                active, t0, pk, sm, n = True, t, v, v, 1
        else:
            pk = max(pk, v)
            sm += v
            n += 1
            d = t - t0
            if v < off or d > max_dur:
                active = False
                last_end = t
                if d >= min_dur:
                    reps.append(dict(start=int(t0), dur=int(d), peak=float(pk),
                                     mean=float(sm / n), eff=bool(pk >= target)))
    return reps


# ---- synthetic sessions ---------------------------------------------------------------------
def make_session(seed, gain=1.0, mains_rel=0.5, n_reps=10, artefacts=3, mvc_rms=250.0):
    """One session: 3 s rest, two maximal contractions, then n_reps repetitions.

    Repetitions 4 and 8 are deliberately weak and must not be scored as effective. Peak
    activation of the others decays slowly over the set to mimic fatigue.
    """
    rng = np.random.default_rng(seed)
    t_rest, t_mvc = 3000, 3000
    starts, amps = [], []
    t = t_rest + t_mvc + 2500
    for k in range(n_reps):
        a = 0.95 - 0.025 * k + rng.normal(0, 0.04)
        if k in (3, 7):
            a = rng.uniform(0.2, 0.38)
        starts.append(t)
        amps.append(float(np.clip(a, 0.15, 1.1)))
        t += int(1200 + rng.uniform(1800, 2800))
    total = t + 2000
    n = int(total * FS / 1000)
    tt = np.arange(n) * 1000 / FS
    env = np.zeros(n)

    def burst(t0, dur, amp):
        m = (tt >= t0) & (tt < t0 + dur)
        ph = (tt[m] - t0) / dur
        env[m] = np.maximum(env[m], amp * np.sin(np.pi * ph) ** 0.6)

    burst(t_rest + 200, 1000, 1.0)
    burst(t_rest + 1700, 1000, 1.0)
    for s0, a in zip(starts, amps):
        burst(s0, 1200, a)

    # band-limited noise carrier (20-450 Hz) shaped by the activation envelope
    w = rng.normal(0, 1, n)
    b, aa = highpass(FS, 20)
    w = lfilter(b, aa, w)
    b, aa = lowpass(FS, 450)
    w = lfilter(b, aa, w)
    w /= w.std()
    emg = w * env * mvc_rms * gain
    mains = mains_rel * mvc_rms * gain * np.sin(2 * np.pi * 50 * tt / 1000 + rng.uniform(0, 6.28))
    wander = 90 * np.sin(2 * np.pi * 0.7 * tt / 1000) + 40 * np.sin(2 * np.pi * 0.23 * tt / 1000 + 1)
    adc_noise = rng.normal(0, 6, n)
    sig = emg + mains + wander + adc_noise
    for _ in range(artefacts):  # motion spikes, only in the exercise window
        i0 = int(rng.uniform((t_rest + t_mvc + 500) * FS / 1000, n - 500))
        length = 80
        sig[i0:i0 + length] += rng.choice([-1, 1]) * 700 * np.exp(-np.arange(length) / 25)
    mv = np.clip(1650 + sig, 0, 3300)  # millivolts at the ADC pin, 1.65 V mid-rail offset
    truth = [dict(start=s, peak=a, eff=bool(a >= 0.5)) for s, a in zip(starts, amps)]
    cal = dict(rest=(0, t_rest), mvc=(t_rest, t_rest + t_mvc), t_ex=t_rest + t_mvc)
    return tt, mv, truth, cal


# ---- detectors ------------------------------------------------------------------------------
def fitpal_chain(tt, mv, cal, target=0.5):
    bn, an = notch(FS, 50, 30)
    bh, ah = highpass(FS, 20)
    bl, al = lowpass(FS, 350)
    x = lfilter(bn, an, mv)
    x = lfilter(bh, ah, x)
    x = lfilter(bl, al, x)
    warm = 500  # same warm-up as emg_dsp.h
    env = np.zeros_like(x)
    env[warm:] = moving_rms(x[warm:], 100)
    r0, r1 = cal["rest"]
    m0, m1 = cal["mvc"]
    rest = env[max(r0, warm):r1].mean()
    mvc = env[m0:m1].max()
    act = np.clip((env - rest) / (mvc - rest), 0, None)
    i0 = cal["t_ex"]
    return env, act, reps_from_activation(tt[i0:].astype(int), act[i0:], target=target)


def fixed_threshold_detector(tt, mv, thr, lockout_ms=600):
    """Count a repetition whenever one raw sample exceeds a fixed level, then ignore 600 ms."""
    hits = []
    t_lock = -1
    for t, v in zip(tt, mv):
        if t >= t_lock and v > thr:
            hits.append(int(t))
            t_lock = t + lockout_ms
    return hits


def run_cpp(tt, mv, cal, target):
    src = os.path.join(ROOT, "tests", "test_pipeline.cpp")
    exe = os.path.join(OUT, "test_pipeline")
    subprocess.check_call(["g++", "-O2", "-std=c++14", "-o", exe, src])
    csv = os.path.join(OUT, "in.csv")
    with open(csv, "w") as f:
        f.write("t_ms,mv\n")
        for t, v in zip(tt, mv):
            f.write(f"{int(t)},{v:.3f}\n")
    envcsv = os.path.join(OUT, "env_cpp.csv")
    r = subprocess.check_output([exe, csv, envcsv, str(cal["rest"][0]), str(cal["rest"][1]),
                                 str(cal["mvc"][0]), str(cal["mvc"][1]), str(target)]).decode()
    reps = []
    for ln in r.splitlines():
        if ln.startswith("REP"):
            _, s, d, pk, mn, e = ln.split(",")
            reps.append(dict(start=int(s), dur=int(d), peak=float(pk), mean=float(mn), eff=bool(int(e))))
    return reps, np.genfromtxt(envcsv, delimiter=",", skip_header=1)


def score(det_times, truth, tol=1200, only_eff=True):
    gt = [g["start"] for g in truth if (g["eff"] or not only_eff)]
    used = set()
    tp = 0
    for d in det_times:
        for j, g in enumerate(gt):
            if j not in used and -300 <= d - g <= tol:
                used.add(j)
                tp += 1
                break
    fp = len(det_times) - tp
    fn = len(gt) - tp
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return tp, fp, fn, p, r


if __name__ == "__main__":
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 8, "axes.spines.top": False, "axes.spines.right": False,
                         "font.family": "serif", "axes.grid": True, "grid.alpha": 0.25})

    # 1. parity between the C++ header and the Python reference on one session
    tt, mv, truth, cal = make_session(seed=7)
    env_py, act_py, reps_py = fitpal_chain(tt, mv, cal)
    reps_cpp, env_cpp = run_cpp(tt, mv, cal, 0.5)
    i5 = np.searchsorted(tt, env_cpp[:, 0])
    d = np.abs(env_cpp[:, 1] - env_py[i5.clip(0, len(env_py) - 1)])
    parity = dict(max_abs_env_diff_mV=float(d.max()), py_reps=len(reps_py), cpp_reps=len(reps_cpp),
                  same_effective_flags=[r["eff"] for r in reps_py] == [r["eff"] for r in reps_cpp])
    print("PARITY", parity)

    # 2. detection over 60 sessions, FitPal chain against the fixed-threshold detector
    rows = []
    thr_nominal = 1650 + 0.9 * 250 * 3.2  # tuned by hand for a nominal subject (gain 1.0)
    for seed in range(60):
        rng = np.random.default_rng(1000 + seed)
        gain = float(np.exp(rng.normal(0, 0.35)))  # subject / electrode-placement spread
        mains = float(rng.uniform(0.2, 1.0))
        tt2, mv2, tr2, cal2 = make_session(seed, gain, mains)
        ex = tt2 >= cal2["t_ex"]
        _, _, reps_new = fitpal_chain(tt2, mv2, cal2)
        found = [r["start"] for r in reps_new if r["eff"]]
        base = fixed_threshold_detector(tt2[ex], mv2[ex], thr_nominal)
        a = score(found, tr2)
        b = score(base, tr2)
        rows.append(dict(seed=seed, gain=gain, mains=mains, fp_tp=a[0], fp_fp=a[1], fp_fn=a[2],
                         ft_tp=b[0], ft_fp=b[1], ft_fn=b[2]))

    def agg(k):
        tp = sum(r[k + "_tp"] for r in rows)
        fp = sum(r[k + "_fp"] for r in rows)
        fn = sum(r[k + "_fn"] for r in rows)
        p = tp / (tp + fp) if tp + fp else 0
        rc = tp / (tp + fn) if tp + fn else 0
        f1 = 2 * p * rc / (p + rc) if p + rc else 0
        return dict(tp=tp, fp=fp, fn=fn, precision=round(p, 3), recall=round(rc, 3), f1=round(f1, 3))

    summary = dict(parity=parity, fitpal=agg("fp"), fixed_threshold=agg("ft"), sessions=len(rows))
    with open(os.path.join(OUT, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))

    # figures
    t_s = tt / 1000
    fig, ax = plt.subplots(4, 1, figsize=(7.2, 7.2), sharex=True)
    ax[0].plot(t_s, mv, lw=0.4, color=GREY)
    ax[0].set_ylabel("raw (mV)")
    ax[0].set_title("Simulated session: raw sensor voltage with hum, wander and motion spikes", loc="left")
    b, a_ = highpass(FS, 20)
    bn, an = notch(FS, 50, 30)
    bl, al = lowpass(FS, 350)
    xf = lfilter(bl, al, lfilter(b, a_, lfilter(bn, an, mv)))
    ax[1].plot(t_s, xf, lw=0.4, color=BLUE)
    ax[1].set_ylabel("filtered (mV)")
    ax[2].plot(t_s, env_py, color=BLUE, lw=1)
    ax[2].set_ylabel("RMS envelope (mV)")
    ax[3].plot(t_s, act_py, color=RED, lw=1)
    ax[3].axhline(0.30, ls=":", color="#777")
    ax[3].axhline(0.15, ls=":", color="#aaa")
    ax[3].axhline(0.5, ls="--", color=BLUE, lw=0.8)
    for r in reps_py:
        ax[3].axvspan(r["start"] / 1000, (r["start"] + r["dur"]) / 1000,
                      color=GREEN if r["eff"] else "#E69F00", alpha=0.25)
    for g in truth:
        ax[3].plot(g["start"] / 1000 + 0.6, 1.25, "v", color="k", ms=3)
    ax[3].set_ylabel("activation (fraction of MVC)")
    ax[3].set_xlabel("time (s)")
    ax[3].set_ylim(0, 1.4)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "sim_session.pdf"))
    fig.savefig(os.path.join(IMG, "sim_session.png"), dpi=150)
    plt.close(fig)

    from numpy.fft import rfft, rfftfreq

    seg = slice(int(cal["t_ex"] + 500), int(cal["t_ex"] + 9000))
    fig, ax = plt.subplots(figsize=(3.4, 2.4))
    for sig, lab, c in ((mv[seg] - mv[seg].mean(), "raw", GREY), (xf[seg], "filtered", BLUE)):
        spec = np.abs(rfft(sig * np.hanning(len(sig))))
        ax.semilogy(rfftfreq(len(sig), 1 / FS), spec / len(sig) + 1e-3, label=lab, color=c, lw=0.8)
    ax.axvline(50, color=RED, ls=":", lw=0.8)
    ax.text(52, ax.get_ylim()[1] * 0.4, "50 Hz", fontsize=6, color=RED)
    ax.set_xlim(0, 500)
    ax.set_xlabel("frequency (Hz)")
    ax.set_ylabel("amplitude (a.u.)")
    ax.legend(frameon=False, fontsize=6)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "sim_spectrum.pdf"))
    fig.savefig(os.path.join(IMG, "sim_spectrum.png"), dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(1, 2, figsize=(7.0, 2.6))
    for k, (key, c) in enumerate((("fitpal", BLUE), ("fixed_threshold", RED))):
        s = summary[key]
        ax[0].bar([k * 3, k * 3 + 1, k * 3 + 2], [s["precision"], s["recall"], s["f1"]], color=c, width=0.9)
    ax[0].set_xticks([1, 4])
    ax[0].set_xticklabels(["FitPal chain\n(P, R, F1)", "fixed threshold\n(P, R, F1)"])
    ax[0].set_ylim(0, 1.05)
    ax[0].set_title("Effective-rep detection, 60 sessions", loc="left", fontsize=8)
    g = np.array([r["gain"] for r in rows])
    ax[1].scatter(g, [r["fp_tp"] for r in rows], s=9, color=BLUE, label="FitPal chain")
    ax[1].scatter(g, [r["ft_tp"] for r in rows], s=9, color=RED, label="fixed threshold")
    ax[1].set_xlabel("subject gain (fraction of nominal)")
    ax[1].set_ylabel("effective reps found (of 8)")
    ax[1].legend(frameon=False, fontsize=6)
    ax[1].set_title("Sensitivity to electrode and subject gain", loc="left", fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "sim_scores.pdf"))
    fig.savefig(os.path.join(IMG, "sim_scores.png"), dpi=150)
    plt.close(fig)
