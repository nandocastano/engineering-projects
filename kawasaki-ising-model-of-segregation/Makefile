PYTHON ?= python3

.PHONY: install test lint run cli demo experiments paper clean

install:
	$(PYTHON) -m pip install -e ".[fast,app,test]"

test:
	$(PYTHON) -m pytest -q

lint:
	ruff check src tests experiments scripts

run:
	streamlit run src/kawasaki_ising/app.py

cli:
	$(PYTHON) -m kawasaki_ising.cli --n 100 --steps 10000 --immigrant-fraction 0.2

# Snapshot grids, distance curves and animations for the README (a few minutes with numba).
demo:
	$(PYTHON) scripts/demo_runs.py
	$(PYTHON) scripts/temperature_sweep.py

# Rerun every experiment in the paper (about an hour on two cores), then rebuild its tables and figures.
experiments:
	$(PYTHON) experiments/exp_exact_local.py
	$(PYTHON) experiments/exp_exact_chain.py
	$(PYTHON) experiments/exp_verify_dynamics.py
	$(PYTHON) experiments/exp_adjacency_impact.py
	$(PYTHON) experiments/exp_demixing.py
	$(PYTHON) experiments/exp_single_seed.py
	$(PYTHON) experiments/exp_metric_invariance.py
	$(PYTHON) experiments/exp_equilibration.py
	$(PYTHON) experiments/exp_equilibrium_variance.py
	$(PYTHON) experiments/make_paper_assets.py

# Tables and figures from the stored results, then the PDF.
paper:
	$(PYTHON) experiments/make_paper_assets.py
	cd paper && pdflatex -interaction=nonstopmode main.tex && bibtex main && \
		pdflatex -interaction=nonstopmode main.tex && pdflatex -interaction=nonstopmode main.tex

clean:
	rm -rf .pytest_cache .ruff_cache build dist *.egg-info
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	cd paper && rm -f *.aux *.log *.out *.bbl *.blg
