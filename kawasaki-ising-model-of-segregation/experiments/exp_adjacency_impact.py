"""E4: effect of the uncorrected acceptance rule on equilibrium observables, versus lattice size.

For each (N, T): R independent replicate chains per rule (corrected / uncorrected), each started from a
random configuration at f=0.5 composition... (f given below), burn_in sweeps, then sample_steps sweeps; the
per-replicate observable is the time-mean of e = E/N^2 (energy per site).  Reported: difference of
replicate means (uncorrected - corrected) with Welch standard error.  Replicates of both rules use
disjoint seeds (the chains are independent, so the comparison is unpaired).
"""

import json
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from common import step_variant, seed_all, initial_lattice, total_energy  # noqa

F = 0.5
TEMPS = [1.5, 2.269, 3.0]
CFG = {8: 400, 16: 200, 32: 100, 64: 40, 100: 20}  # N -> replicates
BURN, SAMPLE = 500, 300


def task(a):
    n, T, mode, r = a
    seed = int(np.random.SeedSequence([n, int(T * 1000), mode, r, 777]).generate_state(1)[0])
    seed_all(seed)
    rng = np.random.default_rng(seed)
    lat = initial_lattice(n, F, rng)
    beta = 1.0 / T
    for _ in range(BURN):
        lat = step_variant(lat, beta, n, mode)
    e = np.empty(SAMPLE)
    for k in range(SAMPLE):
        lat = step_variant(lat, beta, n, mode)
        e[k] = total_energy(lat, n) / n**2
    return (n, T, mode, r, e.mean())


if __name__ == "__main__":
    tasks = [(n, T, m, r) for n, R in CFG.items() for T in TEMPS for m in (0, 1) for r in range(R)]
    tasks.sort(key=lambda t: -t[0])
    res = {}
    with Pool(2) as p:
        for n, T, m, r, v in p.imap_unordered(task, tasks, chunksize=4):
            res.setdefault((n, T, m), []).append(v)
    rows = []
    for n in CFG:
        for T in TEMPS:
            a, b = np.array(res[(n, T, 0)]), np.array(res[(n, T, 1)])
            d = b.mean() - a.mean()
            se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
            rows.append(
                {
                    "N": n,
                    "T": T,
                    "R": len(a),
                    "e_corrected": a.mean(),
                    "e_uncorrected": b.mean(),
                    "diff": d,
                    "se": se,
                    "z": d / se,
                    "rel_diff": d / abs(a.mean()),
                }
            )
            print(rows[-1], flush=True)
    Path(__file__).resolve().parents[1].joinpath("results/paper/E4_adjacency_impact.json").write_text(
        json.dumps(rows, indent=1, default=float)
    )
