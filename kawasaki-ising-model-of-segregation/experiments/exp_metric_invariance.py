"""E8: translation invariance of the clustering metrics on the torus.

The Gibbs measure and the exchange dynamics are invariant under the N^2 torus translations, so an
observable of a configuration should be too.  We equilibrate one N=100 configuration (f=0.2, T=1.0)
and evaluate the periodic (minimum-image) and non-periodic mean pairwise immigrant distance on
n_shift random cyclic translates of it.
"""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from common import seed_all, initial_lattice  # noqa
from kawasaki_ising.core import kawasaki_step, average_immigrant_distance  # noqa

n, f, T = 100, 0.2, 1.0
seed_all(11)
rng = np.random.default_rng(11)
lat = initial_lattice(n, f, rng)
for _ in range(3000):
    lat = kawasaki_step(lat, 1 / T, n)
per, non = [], []
for _ in range(25):
    s = rng.integers(0, n, 2)
    sh = np.roll(lat, (int(s[0]), int(s[1])), axis=(0, 1))
    per.append(average_immigrant_distance(sh, periodic=True))
    non.append(average_immigrant_distance(sh, periodic=False))
res = {
    "N": n,
    "f": f,
    "T": T,
    "sweeps": 3000,
    "n_shifts": 25,
    "periodic_min": min(per),
    "periodic_max": max(per),
    "periodic_spread": max(per) - min(per),
    "nonperiodic_min": min(non),
    "nonperiodic_max": max(non),
    "nonperiodic_spread": max(non) - min(non),
    "nonperiodic_rel_spread": (max(non) - min(non)) / np.mean(non),
}
print(json.dumps(res, indent=1))
Path(__file__).resolve().parents[1].joinpath("results/paper/E8_metric_invariance.json").write_text(
    json.dumps(res, indent=1)
)
