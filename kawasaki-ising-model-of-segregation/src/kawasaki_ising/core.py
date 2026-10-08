"""Lattice mechanics for the Kawasaki-Ising model of segregation.

Everything here is a function of a lattice array and explicit parameters;
there is no I/O and no UI code, so the physics can be tested on its own.

Numba is optional. When it is installed the hot loops are compiled, which
makes N = 100 runs of thousands of sweeps practical. Without it the same
functions run as plain NumPy/Python and give identical results, only slower.
"""

from __future__ import annotations

import numpy as np

try:
    from numba import njit

    NUMBA_AVAILABLE = True
except ImportError:  # pragma: no cover
    NUMBA_AVAILABLE = False

    def njit(*args, **kwargs):  # type: ignore[no-redef]
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]
        return lambda func: func


__all__ = [
    "NUMBA_AVAILABLE",
    "seed_all",
    "initial_lattice",
    "total_energy",
    "delta_energy_kawasaki",
    "kawasaki_step",
    "average_immigrant_distance",
]


@njit(cache=True)
def _seed_numba_rng(seed: int) -> None:
    # Jitted code draws from numba's own RNG state, which np.random.seed()
    # called from Python does not touch. Seeding has to happen inside a
    # jitted function to reach it.
    np.random.seed(seed)


def seed_all(seed: int) -> None:
    """Seed NumPy's global state and, when numba is active, numba's internal state.

    Call this before :func:`kawasaki_step` for runs that must reproduce
    across processes. A bare ``np.random.seed`` is not enough under numba.
    """
    np.random.seed(seed)
    _seed_numba_rng(seed)


def initial_lattice(n: int, immigrant_fraction: float, rng: np.random.Generator) -> np.ndarray:
    """Random ``n`` x ``n`` lattice with natives at -1 and exactly round(f n^2) immigrants at +1."""
    if not 0.0 <= immigrant_fraction <= 1.0:
        raise ValueError("immigrant_fraction must lie in [0, 1]")
    lattice = -np.ones((n, n), dtype=np.int8)
    total_sites = n * n
    num_immigrants = int(round(immigrant_fraction * total_sites))
    if num_immigrants > 0:
        indices = rng.choice(total_sites, size=num_immigrants, replace=False)
        lattice.flat[indices] = 1
    return lattice


@njit(cache=True)
def total_energy(lattice: np.ndarray, n: int, j: float = 1.0) -> float:
    r"""Ising energy :math:`-J \sum_{\langle xy \rangle} s_x s_y` on the periodic lattice.

    Each bond is counted once, through the right and down neighbours of
    every site.
    """
    energy = 0.0
    for x in range(n):
        for y in range(n):
            spin = lattice[x, y]
            neighbor_sum = lattice[(x + 1) % n, y] + lattice[x, (y + 1) % n]
            energy -= j * spin * neighbor_sum
    return energy


@njit(cache=True)
def delta_energy_kawasaki(
    lattice: np.ndarray, x1: int, y1: int, x2: int, y2: int, n: int, j: float = 1.0
) -> float:
    r"""Exact energy change for exchanging the (unlike) spins at two sites.

    Exchanging unlike spins is the same as flipping both. The sum of the two
    single-flip changes counts the bond between the sites as if each flip
    changed it; if the sites are neighbours that bond is unchanged, so the
    exact change is the sum plus :math:`4J`. Callers must only propose
    pairs with different spins.
    """
    dx = min(abs(x1 - x2), n - abs(x1 - x2))
    dy = min(abs(y1 - y2), n - abs(y1 - y2))
    adjacent = (dx + dy) == 1

    de = 0.0
    for x, y in ((x1, y1), (x2, y2)):
        spin = lattice[x, y]
        neighbor_sum = (
            lattice[(x + 1) % n, y]
            + lattice[x, (y + 1) % n]
            + lattice[(x - 1) % n, y]
            + lattice[x, (y - 1) % n]
        )
        de += 2.0 * j * spin * neighbor_sum

    if adjacent:
        de += 4.0 * j

    return de


@njit(cache=True)
def kawasaki_step(lattice: np.ndarray, beta: float, n: int, j: float = 1.0) -> np.ndarray:
    """One sweep: ``n * n`` uniformly random pair exchanges with Metropolis acceptance.

    The lattice is modified in place and returned. The random draws use the
    legacy ``np.random`` functions because that is what numba supports in
    compiled code; seed them with :func:`seed_all`.
    """
    for _ in range(n * n):
        x1, y1 = np.random.randint(0, n), np.random.randint(0, n)
        x2, y2 = np.random.randint(0, n), np.random.randint(0, n)
        if lattice[x1, y1] == lattice[x2, y2]:
            continue
        de = delta_energy_kawasaki(lattice, x1, y1, x2, y2, n, j)
        if de <= 0.0 or np.random.random() < np.exp(-beta * de):
            tmp = lattice[x1, y1]
            lattice[x1, y1] = lattice[x2, y2]
            lattice[x2, y2] = tmp
    return lattice


def average_immigrant_distance(lattice: np.ndarray, periodic: bool = True) -> float:
    """Mean pairwise distance between immigrant sites.

    With ``periodic=True`` (default) distances use the minimum-image
    convention, matching the periodic dynamics. ``periodic=False`` uses plain
    Euclidean distance between array indices, which depends on where the
    lattice boundary falls; it is kept only for comparison.
    """
    coords = np.argwhere(lattice == 1)
    m = len(coords)
    if m < 2:
        return 0.0
    if not periodic:
        from scipy.spatial.distance import pdist

        return float(pdist(coords).mean())

    n = lattice.shape[0]
    total = 0.0
    count = 0
    for i in range(m):
        dx = np.abs(coords[i + 1 :, 0] - coords[i, 0])
        dy = np.abs(coords[i + 1 :, 1] - coords[i, 1])
        dx = np.minimum(dx, n - dx)
        dy = np.minimum(dy, n - dy)
        total += np.sqrt(dx**2 + dy**2).sum()
        count += len(dx)
    return float(total / count) if count > 0 else 0.0
