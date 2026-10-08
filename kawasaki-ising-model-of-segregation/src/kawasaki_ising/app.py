"""Streamlit front end. Run with ``streamlit run src/kawasaki_ising/app.py``."""

from __future__ import annotations

import io

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import streamlit as st

from kawasaki_ising.core import NUMBA_AVAILABLE
from kawasaki_ising.simulate import demixing_vs_composition, estimate_demixing_temperature, run_simulation

CMAP = mcolors.ListedColormap(["red", "blue"])

st.title("Kawasaki-Ising Model of Segregation")
if not NUMBA_AVAILABLE:
    st.warning("numba is not installed; simulations will run correctly but slowly (pip install numba).")

with st.sidebar:
    st.header("Parameters")
    n = st.slider("Lattice size (N)", 10, 100, 100, 10)
    temperature = st.slider("Social temperature (T)", 0.5, 5.0, 1.0, 0.1)
    steps = st.slider("Simulation steps", 1000, 10000, 5000, 1000)
    imm_frac = st.slider("Immigrant fraction", 0.0, 1.0, 0.2, 0.05)
    interval = st.slider("Snapshot interval", 20, 2000, 500, 20)
    seed = st.number_input("Random seed (reproducibility)", value=42, step=1)

if st.button("Run simulation", type="primary"):
    with st.spinner("Running..."):
        result = run_simulation(n, temperature, steps, imm_frac, seed=int(seed), interval=interval)
        st.session_state.result = result
        st.session_state.save_steps = sorted(
            set([0, 40, 200, 400, 1000, 2000, 4000, 5000, 8000, steps]) & set(result.frame_steps)
            | {result.frame_steps[0], result.frame_steps[-1]}
        )

if "result" in st.session_state:
    result = st.session_state.result

    st.subheader("Lattice evolution")
    idx = st.slider("Frame", 0, len(result.frames) - 1, 0)
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.imshow(result.frames[idx], cmap=CMAP, interpolation="nearest")
    ax.set_title(f"Step {result.frame_steps[idx]}")
    ax.axis("off")
    st.pyplot(fig)
    plt.close(fig)

    st.subheader("Immigrant clustering vs. time")
    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.plot(result.frame_steps, result.distances, "-o", markersize=4)
    ax.set_xlabel("Step")
    ax.set_ylabel("Avg. immigrant distance (periodic)")
    st.pyplot(fig)
    plt.close(fig)

    st.subheader("Energy-variance peak at this composition")
    st.caption(
        "Temperature of maximum energy variance for the current immigrant fraction, from a single run per "
        "temperature. It is a noisy finite-size estimate; see the paper for how it compares with the exact "
        "coexistence temperature."
    )
    if st.button("Compute demixing temperature"):
        with st.spinner("Scanning temperatures..."):
            temps = np.linspace(1.5, 3.0, 20)
            demix = estimate_demixing_temperature(n, imm_frac, temps, seed=int(seed))
        st.success(f"Variance peak at T = {demix.t_demix:.3f}")
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 3.5))
        ax1.plot(demix.temperatures, demix.mean_energy, "o-")
        ax1.axvline(demix.t_demix, color="red", linestyle="--")
        ax1.set_xlabel("Temperature (T)")
        ax1.set_ylabel("Mean energy")
        ax2.plot(demix.temperatures, demix.var_energy, "o-", color="orange")
        ax2.axvline(demix.t_demix, color="red", linestyle="--")
        ax2.set_xlabel("Temperature (T)")
        ax2.set_ylabel("Variance of energy")
        st.pyplot(fig)
        plt.close(fig)

    st.subheader("Variance peak vs. immigrant fraction")
    if st.button("Compute demixing vs. composition"):
        with st.spinner("Scanning fractions and temperatures; this can take a while."):
            fracs = np.linspace(0.1, 0.9, 9)
            temps = np.linspace(1.5, 3.5, 20)
            sweep = demixing_vs_composition(n, fracs, temps, seed=int(seed))
        fig, ax = plt.subplots(figsize=(6, 3.5))
        ax.plot(sweep["fractions"], sweep["t_demix"], "-o", color="blue")
        ax.axhline(2.269, color="green", linestyle=":", label="Onsager Tc")
        ax.set_xlabel("Immigrant fraction")
        ax.set_ylabel("Variance-peak temperature")
        ax.legend()
        ax.grid(True)
        st.pyplot(fig)
        plt.close(fig)

    st.subheader("Downloads")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Prepare snapshot grid PNG"):
            steps_list = st.session_state.save_steps
            cols, rows = 5, (len(steps_list) + 4) // 5
            fig, axes = plt.subplots(rows, cols, figsize=(4 * cols, 4 * rows))
            axes_flat = np.atleast_1d(axes).flatten()
            for ax, s in zip(axes_flat, steps_list):
                frame_idx = result.frame_steps.index(s)
                ax.imshow(result.frames[frame_idx], cmap=CMAP)
                ax.set_title(f"Step {s}")
                ax.axis("off")
            for ax in axes_flat[len(steps_list) :]:
                ax.axis("off")
            buf = io.BytesIO()
            plt.tight_layout()
            fig.savefig(buf, format="png")
            buf.seek(0)
            plt.close(fig)
            st.download_button(
                "Download snapshots PNG", buf, file_name="ising_snapshots.png", mime="image/png"
            )

    with col2:
        if st.button("Prepare evolution GIF"):
            import imageio

            buf = io.BytesIO()
            gif_frames = []
            for lattice in result.frames:
                rgb = np.zeros((n, n, 3), dtype=np.uint8)
                rgb[lattice == -1] = [255, 0, 0]
                rgb[lattice == 1] = [0, 0, 255]
                gif_frames.append(rgb)
            imageio.mimsave(buf, gif_frames, format="GIF", duration=0.5)
            buf.seek(0)
            st.download_button(
                "Download evolution GIF", buf, file_name="ising_evolution.gif", mime="image/gif"
            )
