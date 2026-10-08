"""Same N = 100, 20% composition run at six temperatures; writes the figures to ``figures/``."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from demo_runs import OUT_DIR, run_and_report  # noqa: E402

TEMPERATURES = [0.8, 1.2, 1.5, 2.0, 2.2, 3.0]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for t in TEMPERATURES:
        tag = f"tsweep_T{t:.1f}_N100_f20"
        run_and_report(tag, n=100, temperature=t, steps=10000, fraction=0.20, seed=20260728)
    print(f"\nTemperature sweep figures written to {OUT_DIR}")


if __name__ == "__main__":
    main()
