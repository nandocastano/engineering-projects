"""E1: exhaustive verification of the exchange Delta E on a periodic lattice.

For every displacement vector (dx,dy) != 0 on an L x L torus (L=6) and for *every*
assignment of spins to the union of the closed neighbourhoods of the two sites
(<=10 sites), compares (a) the corrected rule, (b) the uncorrected pair-sum rule against
Delta E from recomputing the total energy before/after the swap.  Spins elsewhere are
random (they cancel exactly).  Only unlike-spin pairs are exchanged by the dynamics.
"""

import itertools
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from common import pair_sum_delta, total_energy, is_adjacent  # noqa
from kawasaki_ising.core import delta_energy_kawasaki  # noqa

L = 6
rng = np.random.default_rng(0)
res = {
    "L": L,
    "displacements": 0,
    "configs": 0,
    "adjacent_configs": 0,
    "nonadjacent_configs": 0,
    "fixed_mismatch": 0,
    "pairsum_mismatch_nonadj": 0,
    "pairsum_err_adj_values": set(),
    "pairsum_err_nonadj_values": set(),
    "max_union": 0,
    "true_dE_values_adj": set(),
    "true_dE_values_nonadj": set(),
}


def nbrs(x, y):
    return [((x + 1) % L, y), ((x - 1) % L, y), (x, (y + 1) % L), (x, (y - 1) % L)]


for dx in range(L):
    for dy in range(L):
        if dx == 0 and dy == 0:
            continue
        res["displacements"] += 1
        a, b = (2, 2), ((2 + dx) % L, (2 + dy) % L)
        sites = set([a, b]) | set(nbrs(*a)) | set(nbrs(*b))
        sites = sorted(sites)
        res["max_union"] = max(res["max_union"], len(sites))
        adj = bool(is_adjacent(a[0], a[1], b[0], b[1], L))
        for bits in itertools.product([-1, 1], repeat=len(sites)):
            lat = rng.choice(np.array([-1, 1], dtype=np.int8), size=(L, L))
            for s, v in zip(sites, bits):
                lat[s] = v
            if lat[a] == lat[b]:
                continue
            e0 = total_energy(lat, L)
            lat2 = lat.copy()
            lat2[a], lat2[b] = lat[b], lat[a]
            truth = total_energy(lat2, L) - e0
            fixed = delta_energy_kawasaki(lat, a[0], a[1], b[0], b[1], L)
            ps = pair_sum_delta(lat, a[0], a[1], b[0], b[1], L)
            res["configs"] += 1
            (res["true_dE_values_adj"] if adj else res["true_dE_values_nonadj"]).add(float(truth))
            if fixed != truth:
                res["fixed_mismatch"] += 1
            if adj:
                res["adjacent_configs"] += 1
                res["pairsum_err_adj_values"].add(float(ps - truth))
            else:
                res["nonadjacent_configs"] += 1
                res["pairsum_err_nonadj_values"].add(float(ps - truth))
                if ps != truth:
                    res["pairsum_mismatch_nonadj"] += 1
res["true_dE_values_adj"] = sorted(res["true_dE_values_adj"])
res["true_dE_values_nonadj"] = sorted(res["true_dE_values_nonadj"])
res["pairsum_err_adj_values"] = sorted(res["pairsum_err_adj_values"])
res["pairsum_err_nonadj_values"] = sorted(res["pairsum_err_nonadj_values"])
# Set of attainable true Delta E values (multiples of 4J?)
print(json.dumps(res, indent=1))
Path(__file__).resolve().parents[1].joinpath("results/paper/E1_exact_local.json").write_text(
    json.dumps(res, indent=1)
)
