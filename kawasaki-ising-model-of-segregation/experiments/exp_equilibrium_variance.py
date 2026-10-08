"""E9b: equilibrium Var(E) curves from long runs, with integrated autocorrelation times.

For each (N, f, T, replicate): random start, BURN sweeps, then SAMPLE sweeps recording E after each sweep.
Stored: mean, full-sample variance (ddof=0), variances of the two halves, and the integrated autocorrelation
time tau_int of E (Sokal's automatic windowing, c=6).  The variance of the full 50,000-sweep sample is the
equilibrium estimate; the half-sample values quantify its stationarity/precision.
"""

import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from common import seed_all, initial_lattice, total_energy  # noqa
from kawasaki_ising.core import kawasaki_step  # noqa

BURN, SAMPLE = 10000, 50000
TEMPS = np.round(np.arange(1.5, 2.8001, 0.05), 4)
JOBS = [(32, f) for f in (0.05, 0.10, 0.20, 0.50)] + [(64, f) for f in (0.05, 0.50)]
R = {32: 3, 64: 2}


def tau_int(x, c=6.0):
    x = x - x.mean()
    n = len(x)
    f = np.fft.rfft(x, 2 * n)
    acf = np.fft.irfft(f * np.conj(f))[:n]
    acf /= acf[0]
    tau = 0.5
    for m in range(1, n):
        tau += acf[m]
        if m >= c * tau:
            break
    return float(tau)


def task(a):
    n, f, ti, r = a
    seed = int(np.random.SeedSequence([n, int(f * 1000), ti, r, 99991]).generate_state(1)[0])
    seed_all(seed)
    rng = np.random.default_rng(seed)
    b = 1.0 / TEMPS[ti]
    lat = initial_lattice(n, f, rng)
    for _ in range(BURN):
        lat = kawasaki_step(lat, b, n)
    e = np.empty(SAMPLE)
    for t in range(SAMPLE):
        lat = kawasaki_step(lat, b, n)
        e[t] = total_energy(lat, n)
    return (
        n,
        f,
        ti,
        r,
        float(e.mean()),
        float(e.var()),
        float(e[: SAMPLE // 2].var()),
        float(e[SAMPLE // 2 :].var()),
        tau_int(e),
    )


if __name__ == "__main__":
    tasks = [(n, f, ti, r) for (n, f) in JOBS for ti in range(len(TEMPS)) for r in range(R[n])]
    tasks.sort(key=lambda t: -t[0])
    out = []
    t0 = time.time()
    with Pool(2) as p:
        for i, res in enumerate(p.imap_unordered(task, tasks, chunksize=1)):
            out.append(res)
            if i % 20 == 0:
                print(f"{i}/{len(tasks)} {time.time()-t0:.0f}s", flush=True)
    Path(__file__).resolve().parents[1].joinpath("results/paper/E9b_equilibrium_variance.json").write_text(
        json.dumps({"burn": BURN, "sample": SAMPLE, "temps": TEMPS.tolist(), "rows": out})
    )
    print("done", time.time() - t0)
