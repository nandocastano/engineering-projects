"""Snapshot grids, clustering curves and animations for N = 100, 10,000-sweep runs.

Writes ``figures/<tag>_snapshots.png``, ``<tag>_distance.png`` and ``<tag>.gif``.
Run with ``python scripts/demo_runs.py`` (or ``make demo``).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import imageio.v2 as imageio
import matplotlib

matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from kawasaki_ising.core import NUMBA_AVAILABLE  # noqa: E402
from kawasaki_ising.simulate import run_simulation  # noqa: E402

OUT_DIR = Path(__file__).resolve().parents[1] / "figures"
SNAPSHOT_STEPS = [0, 40, 200, 400, 1000, 2000, 4000, 5000, 8000, 10000]
CMAP = mcolors.ListedColormap(
    ["red", "blue"]
)  # -1 native, +1 immigrant

PALETTE = {"ink": "#14171F", "muted": "#6B7280", "grid": "#DDE1E6", "a": "#0F62FE"}
plt.rcParams.update(
    {
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": PALETTE["muted"],
        "axes.labelcolor": PALETTE["ink"],
        "text.color": PALETTE["ink"],
        "axes.titlesize": 10,
        "axes.titleweight": "bold",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": PALETTE["grid"],
        "grid.linewidth": 0.7,
        "font.size": 9,
    }
)


def snapshot_grid(result, tag: str, title: str) -> Path:
    """Grid of lattice snapshots at the steps in SNAPSHOT_STEPS."""
    steps_list = [s for s in SNAPSHOT_STEPS if s <= result.frame_steps[-1]]
    cols = 5
    rows = (len(steps_list) + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(3.4 * cols, 3.4 * rows))
    axes = np.atleast_1d(axes).flatten()
    for ax, s in zip(axes, steps_list):
        idx = result.frame_steps.index(s)
        ax.imshow(result.frames[idx], cmap=CMAP, interpolation="nearest", vmin=-1, vmax=1)
        ax.set_title(f"step {s}", fontsize=9.5)
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
    for ax in axes[len(steps_list) :]:
        ax.axis("off")
    fig.suptitle(title, fontsize=12, fontweight="bold", y=1.02)
    fig.tight_layout()
    out = OUT_DIR / f"{tag}_snapshots.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def distance_plot(result, tag: str, title: str) -> Path:
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    ax.plot(result.frame_steps, result.distances, "-o", ms=3.5, color=PALETTE["a"])
    ax.set_xlabel("Monte Carlo step")
    ax.set_ylabel("avg. immigrant pairwise distance (periodic)")
    ax.set_title(title)
    out = OUT_DIR / f"{tag}_distance.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def make_gif(result, tag: str, duration: float = 0.35) -> Path:
    n = result.n
    frames_rgb = []
    for lattice in result.frames:
        rgb = np.zeros((n, n, 3), dtype=np.uint8)
        rgb[lattice == -1] = [255, 0, 0]
        rgb[lattice == 1] = [0, 0, 255]
        frames_rgb.append(rgb)
    out = OUT_DIR / f"{tag}.gif"
    imageio.mimsave(out, frames_rgb, format="GIF", duration=duration)
    return out


def run_and_report(
    tag: str, n: int, temperature: float, steps: int, fraction: float, seed: int, interval: int = 20
):
    t0 = time.time()
    result = run_simulation(
        n=n, temperature=temperature, steps=steps, immigrant_fraction=fraction, seed=seed, interval=interval
    )
    dt = time.time() - t0
    print(
        f"[{tag}] N={n} T={temperature} frac={fraction:.0%} steps={steps} seed={seed} "
        f"-> {dt:.1f}s, d0={result.distances[0]:.2f} -> dT={result.distances[-1]:.2f}"
    )
    title = f"N={n}, T={temperature}, {fraction:.0%} immigrants (seed={seed})"
    snapshot_grid(result, tag, title)
    distance_plot(result, tag, f"Immigrant clustering vs. step -- {title}")
    make_gif(result, tag)
    return result


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"numba: {'on' if NUMBA_AVAILABLE else 'off (slow)'}")

    run_and_report("main_N100_T1.0_f20", n=100, temperature=1.0, steps=10000, fraction=0.20, seed=20260728)

    # same N, T, steps and seed at two other compositions
    run_and_report("sparse_N100_T1.0_f05", n=100, temperature=1.0, steps=10000, fraction=0.05, seed=20260728)
    run_and_report("dense_N100_T1.0_f40", n=100, temperature=1.0, steps=10000, fraction=0.40, seed=20260728)

    print(f"\nAll full-scale figures written to {OUT_DIR}")


if __name__ == "__main__":
    main()
