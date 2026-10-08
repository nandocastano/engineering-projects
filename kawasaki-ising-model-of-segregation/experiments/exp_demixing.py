"""E5: replicated variance-peak ("demixing temperature") study against the exact coexistence curve.

Protocol per (N, f, T, replicate) is exactly that of ``simulate.estimate_demixing_temperature``:
random start at composition f, ``burn_in`` sweeps, then ``sample_steps`` sweeps with total
energy recorded after each; Var(E) = np.var (ddof=0).  The only differences: a finer
temperature grid (step 0.05), R independent replicates per point and an extra f=0.5 point.
Output: results/paper/E5_demixing.npz
"""

import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from common import seed_all, initial_lattice, total_energy  # noqa
from kawasaki_ising.core import kawasaki_step  # noqa

NS = [32, 64, 100]
FRACS = [0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.80, 0.95]
TEMPS = np.round(np.linspace(1.5, 3.0, 31), 4)
R = 8
BURN, SAMPLE = 500, 300


def task(args):
    n, fi, ti, r = args
    ss = np.random.SeedSequence([n, fi, ti, r, 20261007])
    seed = int(ss.generate_state(1)[0])
    seed_all(seed)
    rng = np.random.default_rng(seed)
    beta = 1.0 / TEMPS[ti]
    lat = initial_lattice(n, FRACS[fi], rng)
    for _ in range(BURN):
        lat = kawasaki_step(lat, beta, n)
    e = np.empty(SAMPLE)
    for k in range(SAMPLE):
        lat = kawasaki_step(lat, beta, n)
        e[k] = total_energy(lat, n)
    return (n, fi, ti, r, e.mean(), e.var())


if __name__ == "__main__":
    tasks = [
        (n, fi, ti, r) for n in NS for fi in range(len(FRACS)) for ti in range(len(TEMPS)) for r in range(R)
    ]
    # longest first for load balance
    tasks.sort(key=lambda t: -t[0])
    out = {
        n: (np.full((len(FRACS), len(TEMPS), R), np.nan), np.full((len(FRACS), len(TEMPS), R), np.nan))
        for n in NS
    }
    t0 = time.time()
    with Pool(2) as pool:
        for i, (n, fi, ti, r, m, v) in enumerate(pool.imap_unordered(task, tasks, chunksize=4)):
            out[n][0][fi, ti, r] = m
            out[n][1][fi, ti, r] = v
            if i % 100 == 0:
                print(f"{i}/{len(tasks)} {time.time()-t0:.0f}s", flush=True)
    np.savez(
        Path(__file__).resolve().parents[1] / "results/paper/E5_demixing.npz",
        fracs=FRACS,
        temps=TEMPS,
        R=R,
        burn=BURN,
        sample=SAMPLE,
        **{f"meanE_{n}": out[n][0] for n in NS},
        **{f"varE_{n}": out[n][1] for n in NS},
    )
    print("done", time.time() - t0)
