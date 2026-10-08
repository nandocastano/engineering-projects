"""Shared helpers for the paper experiments.

``step_variant`` replicates ``kawasaki_ising.core.kawasaki_step`` draw-for-draw
(same RNG call order) but lets the acceptance rule be switched between the
corrected exact Delta E (mode 0) and the uncorrected pair-sum rule of the
earlier pair-sum implementation (mode 1).  ``step_counted`` additionally tallies
proposal statistics.  Equivalence with the package step is asserted in
``exp_verify_dynamics.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from kawasaki_ising.core import njit  # noqa: E402

TC_ONSAGER = 2.0 / np.log(1.0 + np.sqrt(2.0))


@njit(cache=True)
def pair_sum_delta(lat, x1, y1, x2, y2, n):
    """Uncorrected rule: sum of two independent single-flip energy changes (J=1)."""
    de = 0.0
    for k in range(2):
        x = x1 if k == 0 else x2
        y = y1 if k == 0 else y2
        s = lat[x, y]
        nb = lat[(x + 1) % n, y] + lat[x, (y + 1) % n] + lat[(x - 1) % n, y] + lat[x, (y - 1) % n]
        de += 2.0 * s * nb
    return de


@njit(cache=True)
def is_adjacent(x1, y1, x2, y2, n):
    dx = min(abs(x1 - x2), n - abs(x1 - x2))
    dy = min(abs(y1 - y2), n - abs(y1 - y2))
    return (dx + dy) == 1


@njit(cache=True)
def step_variant(lat, beta, n, mode):
    for _ in range(n * n):
        x1, y1 = np.random.randint(0, n), np.random.randint(0, n)
        x2, y2 = np.random.randint(0, n), np.random.randint(0, n)
        if lat[x1, y1] == lat[x2, y2]:
            continue
        de = pair_sum_delta(lat, x1, y1, x2, y2, n)
        if mode == 0 and is_adjacent(x1, y1, x2, y2, n):
            de += 4.0
        if de <= 0.0 or np.random.random() < np.exp(-beta * de):
            t = lat[x1, y1]
            lat[x1, y1] = lat[x2, y2]
            lat[x2, y2] = t
    return lat


@njit(cache=True)
def step_counted(lat, beta, n, counts):
    """Corrected dynamics; counts = [proposals, differing, adjacent, adjacent_differing, accepted, accepted_adjacent]."""
    for _ in range(n * n):
        x1, y1 = np.random.randint(0, n), np.random.randint(0, n)
        x2, y2 = np.random.randint(0, n), np.random.randint(0, n)
        counts[0] += 1
        adj = is_adjacent(x1, y1, x2, y2, n)
        if adj:
            counts[2] += 1
        if lat[x1, y1] == lat[x2, y2]:
            continue
        counts[1] += 1
        if adj:
            counts[3] += 1
        de = pair_sum_delta(lat, x1, y1, x2, y2, n)
        if adj:
            de += 4.0
        if de <= 0.0 or np.random.random() < np.exp(-beta * de):
            t = lat[x1, y1]
            lat[x1, y1] = lat[x2, y2]
            lat[x2, y2] = t
            counts[4] += 1
            if adj:
                counts[5] += 1
    return lat


def yang_binodal_T(f: float) -> float:
    """Exact coexistence temperature T_b(f) of the 2D square-lattice Ising lattice gas (J=1, k_B=1).

    Solving Yang's spontaneous magnetisation m_s(T) = (1 - sinh(2/T)^-4)^(1/8) = |2f-1| =: m in closed form
    gives sinh(2/T)^4 = 1/(1-m^8), i.e. T_b = 2 / arsinh((1 - m^8)^(-1/4)).
    Returns T_c at f = 1/2 and 0 at f in {0, 1}.
    """
    m = abs(2.0 * f - 1.0)
    if m >= 1.0:
        return 0.0
    return float(2.0 / np.arcsinh((1.0 - m**8) ** -0.25))
