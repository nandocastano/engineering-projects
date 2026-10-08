# Kawasaki-Ising Model of Segregation

Pair-exchange Metropolis sampling for the two-dimensional Ising lattice gas at fixed composition, used as a lattice model of residential segregation. The repository contains the simulator, a command-line tool and a Streamlit app, the experiments behind the accompanying paper, and the paper source (`paper/`).

The paper asks two questions about Monte Carlo output from this kind of model:

1. Does the Markov chain sample the distribution we intend?
2. Does the observable we read off identify the transition we intend?

## Main results

- **Exact exchange energy.** For a pair exchange, the energy change is the sum of the two single-site terms plus a correction of `4J` when the exchanged sites are neighbours. With the correct rule the kernel is reversible, irreducible and aperiodic, and the canonical distribution is its unique stationary law. Omitting the correction breaks detailed balance by exactly `e^{±4βJ}`.
- **Local versus stationary error.** With uniform random-pair proposals the one-step perturbation is at most `4N⁻²(1 − e^{−4βJ})`. This does not bound the stationary law. On tori small enough to solve exactly, the stationary law moves by 0.07 to 0.77 in total variation. The mean-energy shift is 5.5 to 6.3% at N = 8, 1.0 to 2.2% at N = 16, and not detectable with our replication at N ≥ 32.
- **Variance peak versus exact coexistence curve.** Over eight replicates the single-run variance-peak estimate has a standard deviation of 0.09 to 0.30, larger than the whole composition dependence of the exact Onsager–Yang curve over 0.2 ≤ f ≤ 0.8 (0.0077 in temperature). At dilute compositions the estimate lies 0.17 to 0.29 below the exact curve.
- **Equilibration.** The standard 300-sweep sampling window is shorter than the energy autocorrelation time in the worst cases. This does not explain the dilute offset, which persists in a long equilibrium reference.

Every table and figure in the paper is generated from the stored raw output in `results/paper/`. See the paper for definitions, proofs, protocols and caveats.

## Installation

Python 3.10 or newer.

```bash
# from the repository root
pip install -e ".[fast,app,test]"
```

The extras are optional: `fast` installs numba (over 100 times faster in our timing), `app` the Streamlit interface, and `test` pytest. Without numba the simulator falls back to plain Python.

## Usage

Command line:

```bash
kawasaki-ising --n 100 --temperature 1.0 --immigrant-fraction 0.2 --steps 10000 --seed 1
```

The run writes a JSON summary of the energy and the average immigrant distance to the output directory.

Interactive app:

```bash
streamlit run src/kawasaki_ising/app.py
```

Python:

```python
import numpy as np
from kawasaki_ising import seed_all, initial_lattice, kawasaki_step

seed_all(1)
lattice = initial_lattice(40, 0.2, np.random.default_rng(1))
kawasaki_step(lattice, beta=1.0, n=40)  # one sweep, in place
```

See `src/kawasaki_ising/core.py` and `simulate.py` for the full interface.

## Tests

```bash
make test    # 19 tests
make lint
```

The tests check the exchange energy against brute-force recomputation of the full Hamiltonian, composition conservation, seeded reproducibility across processes, and the periodic-distance metric. Detailed balance and stationarity are checked exactly on small tori by `experiments/exp_exact_chain.py`.

## Reproducing the paper

```bash
make experiments   # reruns every experiment; about an hour on two cores
make paper         # rebuilds tables, figures and the PDF (needs a LaTeX installation)
```

`make paper` alone regenerates the tables and figures from the stored results in `results/paper/`.

`make demo` produces the snapshot grids, distance curves and animations in `figures/`.

## Layout

```
src/kawasaki_ising/   simulator, CLI and Streamlit app
tests/                unit and regression tests
experiments/          experiments E1 to E9 and the paper asset generator
scripts/              demo figures and the temperature sweep
results/paper/        raw experiment output used by the paper
paper/                LaTeX source and generated tables
figures/              demo figures
```

## Citation

If you use this code or the paper, please cite it using `CITATION.cff`.

## License

MIT. See `LICENSE`.
