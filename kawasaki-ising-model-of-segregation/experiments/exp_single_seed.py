"""E6: re-run the single-seed protocol (single seed, 20-point grid, N=100) and store the values."""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from common import yang_binodal_T, TC_ONSAGER  # noqa
from kawasaki_ising.simulate import estimate_demixing_temperature  # noqa

FR = [0.05, 0.10, 0.20, 0.30, 0.40, 0.60, 0.80, 0.95]
TEMPS = np.linspace(1.5, 3.0, 20)
SEED = 20260728
rows = []
for i, f in enumerate(FR):
    r = estimate_demixing_temperature(
        n=100, immigrant_fraction=f, temperatures=TEMPS, seed=SEED + i, burn_in=500, sample_steps=300
    )
    rows.append(
        {
            "f": f,
            "T_demix_single": r.t_demix,
            "T_binodal_exact": yang_binodal_T(f),
            "var_E": r.var_energy.tolist(),
        }
    )
    print(rows[-1]["f"], rows[-1]["T_demix_single"], round(rows[-1]["T_binodal_exact"], 4), flush=True)
Path(__file__).resolve().parents[1].joinpath("results/paper/E6_single_seed.json").write_text(
    json.dumps({"seed": SEED, "temps": TEMPS.tolist(), "rows": rows}, indent=1)
)
