"""E9a: is the single-seed protocol (500 burn-in + 300 sampling sweeps) equilibrated?

Long energy traces E(t), t=1..T_total sweeps from a random start; compares the mean and variance of E in the
protocol sampling window [500,800) with those of late windows of the same length and with the long-run
variance estimated from non-overlapping late blocks.
"""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from common import seed_all, initial_lattice, total_energy  # noqa
from kawasaki_ising.core import kawasaki_step  # noqa

TOT = 40000


def trace(n, f, T, seed):
    seed_all(seed)
    rng = np.random.default_rng(seed)
    lat = initial_lattice(n, f, rng)
    b = 1.0 / T
    e = np.empty(TOT)
    for t in range(TOT):
        lat = kawasaki_step(lat, b, n)
        e[t] = total_energy(lat, n)
    return e


rows = []
for n, f, T in [
    (64, 0.05, 1.8),
    (64, 0.05, 2.0),
    (64, 0.05, 2.2),
    (64, 0.2, 2.0),
    (64, 0.2, 2.2),
    (64, 0.2, 2.4),
    (64, 0.5, 2.2),
    (64, 0.5, 2.4),
    (64, 0.5, 2.6),
    (100, 0.05, 1.8),
    (100, 0.05, 2.0),
]:
    e = trace(n, f, T, 123)
    def w(a, b):
        return e[a:b]

    late_blocks = [e[k : k + 300] for k in range(20000, TOT, 300)]
    row = {
        "N": n,
        "f": f,
        "T": T,
        "mean_protocol": float(w(500, 800).mean()),
        "mean_5k_10k": float(w(5000, 10000).mean()),
        "mean_late_20k_40k": float(w(20000, TOT).mean()),
        "var_protocol": float(w(500, 800).var()),
        "var_late_block_mean": float(np.mean([b.var() for b in late_blocks])),
        "var_late_full": float(w(20000, TOT).var()),
        "drift_in_protocol_window": float(e[799] - e[500]),
        "mean_first_half_late": float(w(20000, 30000).mean()),
        "mean_second_half_late": float(w(30000, TOT).mean()),
    }
    row["mean_offset_in_sd"] = (row["mean_protocol"] - row["mean_late_20k_40k"]) / np.sqrt(
        row["var_late_full"]
    )
    rows.append(row)
    print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items()}, flush=True)
Path(__file__).resolve().parents[1].joinpath("results/paper/E9a_equilibration.json").write_text(
    json.dumps(rows, indent=1)
)
