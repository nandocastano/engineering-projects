"""Trajectories and the variance-peak temperature estimate."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .core import average_immigrant_distance, initial_lattice, kawasaki_step, seed_all, total_energy

__all__ = [
    "SimulationResult",
    "run_simulation",
    "DemixingResult",
    "estimate_demixing_temperature",
    "demixing_vs_composition",
]


@dataclass
class SimulationResult:
    frames: list[np.ndarray]
    frame_steps: list[int]
    distances: list[float]
    n: int
    temperature: float
    immigrant_fraction: float
    seed: int


def run_simulation(
    n: int,
    temperature: float,
    steps: int,
    immigrant_fraction: float,
    seed: int,
    interval: int = 100,
    track_distance: bool = True,
    periodic_distance: bool = True,
) -> SimulationResult:
    """Run one trajectory, storing a snapshot and the clustering distance every ``interval`` sweeps.

    The initial lattice and the Metropolis draws are both seeded from
    ``seed``, so a run reproduces exactly across processes.
    """
    beta = 1.0 / temperature
    rng = np.random.default_rng(seed)
    seed_all(seed)

    lattice = initial_lattice(n, immigrant_fraction, rng)
    frames = [lattice.copy()]
    frame_steps = [0]
    distances = [average_immigrant_distance(lattice, periodic=periodic_distance)] if track_distance else []

    for step in range(1, steps + 1):
        lattice = kawasaki_step(lattice, beta, n)
        if step % interval == 0 or step == steps:
            frames.append(lattice.copy())
            frame_steps.append(step)
            if track_distance:
                distances.append(average_immigrant_distance(lattice, periodic=periodic_distance))

    return SimulationResult(
        frames=frames,
        frame_steps=frame_steps,
        distances=distances,
        n=n,
        temperature=temperature,
        immigrant_fraction=immigrant_fraction,
        seed=seed,
    )


@dataclass
class DemixingResult:
    """Energy statistics over a temperature grid at fixed composition."""

    temperatures: np.ndarray
    mean_energy: np.ndarray
    var_energy: np.ndarray
    t_demix: float
    immigrant_fraction: float
    n: int


def estimate_demixing_temperature(
    n: int,
    immigrant_fraction: float,
    temperatures: np.ndarray,
    seed: int,
    burn_in: int = 500,
    sample_steps: int = 300,
) -> DemixingResult:
    r"""Temperature of maximum energy variance on a grid, at fixed composition.

    One chain per temperature: ``burn_in`` sweeps, then the variance of the
    energy over ``sample_steps`` sweeps. The location of the maximum is a
    finite-size, noisy estimate; at compositions other than one half it is
    not the Onsager critical temperature and need not coincide with the
    exact coexistence temperature (see the paper in ``paper/``).
    """
    mean_e = np.empty(len(temperatures))
    var_e = np.empty(len(temperatures))
    seed_all(seed)
    rng = np.random.default_rng(seed)

    for i, t in enumerate(temperatures):
        beta = 1.0 / t
        lattice = initial_lattice(n, immigrant_fraction, rng)
        for _ in range(burn_in):
            lattice = kawasaki_step(lattice, beta, n)
        energies = np.empty(sample_steps)
        for k in range(sample_steps):
            lattice = kawasaki_step(lattice, beta, n)
            energies[k] = total_energy(lattice, n)
        mean_e[i] = energies.mean()
        var_e[i] = energies.var()

    t_demix = float(temperatures[np.argmax(var_e)])
    return DemixingResult(
        temperatures=np.asarray(temperatures),
        mean_energy=mean_e,
        var_energy=var_e,
        t_demix=t_demix,
        immigrant_fraction=immigrant_fraction,
        n=n,
    )


def demixing_vs_composition(
    n: int,
    fractions: np.ndarray,
    temperatures: np.ndarray,
    seed: int,
    burn_in: int = 500,
    sample_steps: int = 300,
) -> dict[str, np.ndarray]:
    """Run :func:`estimate_demixing_temperature` for each immigrant fraction."""
    t_demix = np.empty(len(fractions))
    for i, f in enumerate(fractions):
        result = estimate_demixing_temperature(
            n, float(f), temperatures, seed=seed + i, burn_in=burn_in, sample_steps=sample_steps
        )
        t_demix[i] = result.t_demix
    return {"fractions": np.asarray(fractions), "t_demix": t_demix}
