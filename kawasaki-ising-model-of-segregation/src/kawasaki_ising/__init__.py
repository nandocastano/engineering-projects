"""Kawasaki-Ising model of residential segregation."""

from .core import (
    NUMBA_AVAILABLE,
    average_immigrant_distance,
    delta_energy_kawasaki,
    initial_lattice,
    kawasaki_step,
    seed_all,
    total_energy,
)
from .simulate import (
    DemixingResult,
    SimulationResult,
    demixing_vs_composition,
    estimate_demixing_temperature,
    run_simulation,
)

__version__ = "2.0.0"

__all__ = [
    "NUMBA_AVAILABLE",
    "DemixingResult",
    "SimulationResult",
    "average_immigrant_distance",
    "delta_energy_kawasaki",
    "demixing_vs_composition",
    "estimate_demixing_temperature",
    "initial_lattice",
    "kawasaki_step",
    "run_simulation",
    "seed_all",
    "total_energy",
    "__version__",
]
