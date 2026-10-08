"""Tests for the lattice core and the simulation wrappers. None needs numba or the network."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kawasaki_ising.core import (  # noqa: E402
    NUMBA_AVAILABLE,
    average_immigrant_distance,
    delta_energy_kawasaki,
    initial_lattice,
    kawasaki_step,
    seed_all,
    total_energy,
)
from kawasaki_ising.simulate import estimate_demixing_temperature, run_simulation  # noqa: E402

SEED = 20260728


def _brute_force_delta_energy(lattice: np.ndarray, x1: int, y1: int, x2: int, y2: int, n: int) -> float:
    e0 = total_energy(lattice, n)
    lattice[x1, y1], lattice[x2, y2] = lattice[x2, y2], lattice[x1, y1]
    e1 = total_energy(lattice, n)
    lattice[x1, y1], lattice[x2, y2] = lattice[x2, y2], lattice[x1, y1]
    return e1 - e0


# --------------------------------------------------------------------------- #
# initial_lattice                                                             #
# --------------------------------------------------------------------------- #
def test_initial_lattice_composition_exact() -> None:
    rng = np.random.default_rng(SEED)
    lattice = initial_lattice(20, 0.25, rng)
    assert (lattice == 1).sum() == round(0.25 * 400)
    assert (lattice == -1).sum() == 400 - round(0.25 * 400)


def test_initial_lattice_reproducible_given_rng_state() -> None:
    a = initial_lattice(20, 0.3, np.random.default_rng(5))
    b = initial_lattice(20, 0.3, np.random.default_rng(5))
    assert np.array_equal(a, b)


def test_initial_lattice_rejects_invalid_fraction() -> None:
    rng = np.random.default_rng(SEED)
    for bad in (-0.1, 1.1):
        try:
            initial_lattice(10, bad, rng)
        except ValueError:
            continue
        raise AssertionError(f"fraction={bad} should have been rejected")


def test_initial_lattice_extremes() -> None:
    rng = np.random.default_rng(SEED)
    assert (initial_lattice(10, 0.0, rng) == -1).all()
    assert (initial_lattice(10, 1.0, rng) == 1).all()


# --------------------------------------------------------------------------- #
# delta_energy_kawasaki                                                       #
# --------------------------------------------------------------------------- #
def test_delta_energy_matches_brute_force_non_adjacent() -> None:
    rng = np.random.default_rng(SEED)
    n = 16
    lattice = rng.choice(np.array([-1, 1], dtype=np.int8), size=(n, n))
    checked = 0
    for _ in range(3000):
        x1, y1, x2, y2 = [int(v) for v in rng.integers(0, n, 4)]
        if lattice[x1, y1] == lattice[x2, y2]:
            continue
        dx, dy = min(abs(x1 - x2), n - abs(x1 - x2)), min(abs(y1 - y2), n - abs(y1 - y2))
        if dx + dy == 1:
            continue
        fixed = delta_energy_kawasaki(lattice.copy(), x1, y1, x2, y2, n)
        truth = _brute_force_delta_energy(lattice.copy(), x1, y1, x2, y2, n)
        assert fixed == truth
        checked += 1
    assert checked > 100, "too few non-adjacent pairs"


def test_delta_energy_matches_brute_force_adjacent() -> None:
    """Neighbouring sites are where the pair-sum formula fails (by exactly 4J)."""
    rng = np.random.default_rng(SEED)
    n = 16
    lattice = rng.choice(np.array([-1, 1], dtype=np.int8), size=(n, n))
    checked = 0
    for x in range(n):
        for y in range(n):
            for x2, y2 in (((x + 1) % n, y), (x, (y + 1) % n)):
                if lattice[x, y] == lattice[x2, y2]:
                    continue
                fixed = delta_energy_kawasaki(lattice.copy(), x, y, x2, y2, n)
                truth = _brute_force_delta_energy(lattice.copy(), x, y, x2, y2, n)
                assert fixed == truth, f"adjacent pair ({x},{y})-({x2},{y2}): {fixed} != {truth}"
                checked += 1
    assert checked > 50, "too few adjacent pairs"


def test_pair_sum_formula_is_off_by_4j_for_adjacent_pairs() -> None:
    """The sum of two single-flip changes misses the exact change by 4J when the sites are neighbours."""
    rng = np.random.default_rng(1)
    n = 12
    lattice = rng.choice(np.array([-1, 1], dtype=np.int8), size=(n, n))

    def pair_sum(lat, x1, y1, x2, y2, n):
        de = 0.0
        for x, y in ((x1, y1), (x2, y2)):
            spin = lat[x, y]
            neighbors = lat[(x + 1) % n, y] + lat[x, (y + 1) % n] + lat[(x - 1) % n, y] + lat[x, (y - 1) % n]
            de += 2 * spin * neighbors
        return de

    found_adjacent = False
    for x in range(n):
        for y in range(n):
            x2, y2 = (x + 1) % n, y
            if lattice[x, y] != lattice[x2, y2]:
                truth = _brute_force_delta_energy(lattice.copy(), x, y, x2, y2, n)
                naive = pair_sum(lattice.copy(), x, y, x2, y2, n)
                assert truth - naive == 4.0
                found_adjacent = True
                break
        if found_adjacent:
            break
    assert found_adjacent, "no adjacent unlike pair found"


# --------------------------------------------------------------------------- #
# total_energy                                                                #
# --------------------------------------------------------------------------- #
def test_total_energy_uniform_lattice_is_maximally_negative() -> None:
    n = 10
    lattice = np.ones((n, n), dtype=np.int8)
    # each of the 2 n^2 bonds contributes -1
    assert total_energy(lattice, n) == -2 * n * n


def test_total_energy_checkerboard_is_maximally_positive() -> None:
    n = 10
    x, y = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
    lattice = np.where((x + y) % 2 == 0, 1, -1).astype(np.int8)
    assert total_energy(lattice, n) == 2 * n * n


# --------------------------------------------------------------------------- #
# kawasaki_step: conservation and stability                                   #
# --------------------------------------------------------------------------- #
def test_kawasaki_step_conserves_composition() -> None:
    rng = np.random.default_rng(SEED)
    n = 20
    lattice = initial_lattice(n, 0.3, rng)
    n_immigrants_before = int((lattice == 1).sum())
    seed_all(SEED)
    for _ in range(20):
        lattice = kawasaki_step(lattice, beta=1.0, n=n)
    assert int((lattice == 1).sum()) == n_immigrants_before


def test_kawasaki_step_never_increases_energy_at_zero_temperature() -> None:
    """At T->0 (beta->inf) every accepted move must be non-increasing in energy."""
    rng = np.random.default_rng(3)
    n = 16
    lattice = initial_lattice(n, 0.3, rng)
    seed_all(3)
    e_prev = total_energy(lattice, n)
    for _ in range(15):
        lattice = kawasaki_step(lattice, beta=1e6, n=n)
        e_now = total_energy(lattice, n)
        assert e_now <= e_prev + 1e-9
        e_prev = e_now


def test_kawasaki_step_deterministic_given_seed() -> None:
    n = 16
    rng1 = np.random.default_rng(SEED)
    lattice1 = initial_lattice(n, 0.2, rng1)
    seed_all(SEED)
    lattice1 = kawasaki_step(lattice1, beta=1.0, n=n)

    rng2 = np.random.default_rng(SEED)
    lattice2 = initial_lattice(n, 0.2, rng2)
    seed_all(SEED)
    lattice2 = kawasaki_step(lattice2, beta=1.0, n=n)

    assert np.array_equal(lattice1, lattice2)


def test_seed_all_reproduces_across_fresh_processes() -> None:
    """seed_all must give identical trajectories in separate interpreters.

    With numba active a bare ``np.random.seed`` does not, because compiled
    code draws from numba's own generator, so that case is checked too.
    """
    import subprocess
    import sys as _sys

    src_dir = str(Path(__file__).resolve().parents[1] / "src")

    def run_in_fresh_process(seed_call: str) -> str:
        code = (
            f"import sys; sys.path.insert(0, {src_dir!r})\n"
            "import numpy as np\n"
            "from kawasaki_ising.core import initial_lattice, kawasaki_step\n"
            f"{seed_call}\n"
            "rng = np.random.default_rng(20260728)\n"
            "lattice = initial_lattice(24, 0.2, rng)\n"
            f"{seed_call}\n"
            "for _ in range(10):\n"
            "    lattice = kawasaki_step(lattice, beta=1.0, n=24)\n"
            "print(lattice.tobytes().hex())\n"
        )
        result = subprocess.run(
            [_sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=120
        )
        assert result.returncode == 0, f"subprocess failed: {result.stderr}"
        return result.stdout.strip()

    seed_all_a = run_in_fresh_process("from kawasaki_ising.core import seed_all; seed_all(20260728)")
    seed_all_b = run_in_fresh_process("from kawasaki_ising.core import seed_all; seed_all(20260728)")
    assert seed_all_a == seed_all_b, "seed_all must reproduce identically across fresh processes"

    if NUMBA_AVAILABLE:
        bare_a = run_in_fresh_process("import numpy as np; np.random.seed(20260728)")
        bare_b = run_in_fresh_process("import numpy as np; np.random.seed(20260728)")
        assert bare_a != bare_b, "bare np.random.seed unexpectedly reproduced under numba"


# --------------------------------------------------------------------------- #
# average_immigrant_distance: periodic vs non-periodic                        #
# --------------------------------------------------------------------------- #
def test_periodic_distance_across_boundary_is_short() -> None:
    n = 20
    lattice = -np.ones((n, n), dtype=np.int8)
    lattice[0, 0] = 1
    lattice[n - 1, 0] = 1  # neighbours across the periodic boundary
    periodic = average_immigrant_distance(lattice, periodic=True)
    non_periodic = average_immigrant_distance(lattice, periodic=False)
    assert periodic == 1.0  # minimum-image distance
    assert non_periodic == n - 1  # plain Euclidean distance
    assert periodic < non_periodic


def test_distance_empty_or_singleton_is_zero() -> None:
    n = 10
    lattice = -np.ones((n, n), dtype=np.int8)
    assert average_immigrant_distance(lattice) == 0.0
    lattice[0, 0] = 1
    assert average_immigrant_distance(lattice) == 0.0


def test_periodic_distance_matches_scipy_when_no_wraparound_benefit() -> None:
    """Away from the boundary the two metrics agree."""
    from scipy.spatial.distance import pdist

    n = 40
    lattice = -np.ones((n, n), dtype=np.int8)
    coords = [(15, 15), (16, 15), (15, 16), (18, 18)]
    for x, y in coords:
        lattice[x, y] = 1
    periodic = average_immigrant_distance(lattice, periodic=True)
    scipy_val = float(pdist(np.array(coords)).mean())
    assert abs(periodic - scipy_val) < 1e-9


# --------------------------------------------------------------------------- #
# simulate.py: orchestration                                                  #
# --------------------------------------------------------------------------- #
def test_run_simulation_reproducible() -> None:
    a = run_simulation(n=16, temperature=1.5, steps=100, immigrant_fraction=0.2, seed=SEED, interval=50)
    b = run_simulation(n=16, temperature=1.5, steps=100, immigrant_fraction=0.2, seed=SEED, interval=50)
    assert np.array_equal(a.frames[-1], b.frames[-1])
    assert a.distances == b.distances


def test_run_simulation_composition_conserved_throughout() -> None:
    result = run_simulation(n=16, temperature=1.0, steps=150, immigrant_fraction=0.25, seed=1, interval=50)
    target = round(0.25 * 16 * 16)
    for frame in result.frames:
        assert int((frame == 1).sum()) == target


def test_estimate_demixing_temperature_returns_value_in_range() -> None:
    temps = np.linspace(1.5, 3.0, 6)
    result = estimate_demixing_temperature(
        n=12, immigrant_fraction=0.3, temperatures=temps, seed=1, burn_in=20, sample_steps=15
    )
    assert temps[0] <= result.t_demix <= temps[-1]
    assert len(result.mean_energy) == len(temps)


# --------------------------------------------------------------------------- #
# Minimal runner for environments without pytest                              #
# --------------------------------------------------------------------------- #
def _main() -> int:  # pragma: no cover
    tests = [(name, obj) for name, obj in sorted(globals().items()) if name.startswith("test_")]
    failures = 0
    for name, test in tests:
        try:
            test()
        except AssertionError as exc:
            failures += 1
            print(f"FAIL  {name}\n      {exc}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"ERROR {name}\n      {type(exc).__name__}: {exc}")
        else:
            print(f"ok    {name}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
