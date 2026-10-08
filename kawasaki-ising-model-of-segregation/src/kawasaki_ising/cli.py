"""Command-line runner: ``python -m kawasaki_ising.cli --n 100 --steps 10000``."""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np

from . import NUMBA_AVAILABLE, __version__
from .simulate import run_simulation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kawasaki-ising",
        description="Run a Kawasaki-Ising segregation simulation and write a JSON summary.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--n", type=int, default=40, help="lattice size")
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--steps", type=int, default=3000)
    parser.add_argument("--immigrant-fraction", type=float, default=0.2)
    parser.add_argument("--interval", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--outdir", type=Path, default=Path("results"))
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not NUMBA_AVAILABLE and not args.quiet:
        print("numba not installed: running without compilation (slower).", file=sys.stderr)

    started = time.perf_counter()
    result = run_simulation(
        n=args.n,
        temperature=args.temperature,
        steps=args.steps,
        immigrant_fraction=args.immigrant_fraction,
        seed=args.seed,
        interval=args.interval,
    )
    elapsed = time.perf_counter() - started

    summary = {
        "meta": {
            "version": __version__,
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "numba_available": NUMBA_AVAILABLE,
            "platform": platform.platform(),
            "wall_time_seconds": round(elapsed, 3),
        },
        "config": {
            "n": args.n,
            "temperature": args.temperature,
            "steps": args.steps,
            "immigrant_fraction": args.immigrant_fraction,
            "interval": args.interval,
            "seed": args.seed,
        },
        "results": {
            "frame_steps": result.frame_steps,
            "distances": result.distances,
            "initial_distance": result.distances[0] if result.distances else None,
            "final_distance": result.distances[-1] if result.distances else None,
        },
    }

    args.outdir.mkdir(parents=True, exist_ok=True)
    (args.outdir / "summary.json").write_text(json.dumps(summary, indent=2))

    if not args.quiet:
        print(
            f"N={args.n}  T={args.temperature}  steps={args.steps}  "
            f"immigrant_fraction={args.immigrant_fraction}"
        )
        print(f"initial avg. distance: {summary['results']['initial_distance']:.3f}")
        print(f"final avg. distance:   {summary['results']['final_distance']:.3f}")
        print(f"wall time: {elapsed:.1f}s")
        print(f"wrote {args.outdir/'summary.json'}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
