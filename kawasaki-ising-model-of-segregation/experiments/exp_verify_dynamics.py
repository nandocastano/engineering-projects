"""E3/E6/E7: (i) draw-for-draw equivalence of experiment steps with package step;
(ii) adjacent-proposal statistics vs. 4/N^2; (iii) seeding claim; (iv) numba speed-up."""

import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from common import step_variant, step_counted, seed_all, initial_lattice, total_energy  # noqa
from kawasaki_ising.core import kawasaki_step  # noqa

ROOT = Path(__file__).resolve().parents[1]
out = {}

# (i) equivalence
eq = []
for n, T, f, seed in [(16, 1.0, 0.2, 1), (32, 2.27, 0.4, 2), (50, 3.0, 0.5, 3)]:
    rng = np.random.default_rng(seed)
    l0 = initial_lattice(n, f, rng)
    a, b, c = l0.copy(), l0.copy(), l0.copy()
    seed_all(seed)
    for _ in range(30):
        a = kawasaki_step(a, 1 / T, n)
    seed_all(seed)
    for _ in range(30):
        b = step_variant(b, 1 / T, n, 0)
    seed_all(seed)
    cnt = np.zeros(6, dtype=np.int64)
    for _ in range(30):
        c = step_counted(c, 1 / T, n, cnt)
    eq.append(
        {
            "n": n,
            "T": T,
            "f": f,
            "package==fixed_variant": bool((a == b).all()),
            "package==counted": bool((a == c).all()),
        }
    )
out["equivalence"] = eq
print(eq)

# (ii) adjacency statistics, trajectories from random start, after 300 burn-in sweeps, 300 measured sweeps
stats = []
for n in [20, 40, 100]:
    for T in [1.0, 2.269, 3.0]:
        f = 0.2
        rng = np.random.default_rng(7)
        lat = initial_lattice(n, f, rng)
        seed_all(7)
        for _ in range(300):
            lat = kawasaki_step(lat, 1 / T, n)
        cnt = np.zeros(6, dtype=np.int64)
        for _ in range(300):
            lat = step_counted(lat, 1 / T, n, cnt)
        stats.append(
            {
                "n": n,
                "T": T,
                "f": f,
                "proposals": int(cnt[0]),
                "adjacent_rate": cnt[2] / cnt[0],
                "theory_4_over_n2": 4 / n**2,
                "differing_rate": cnt[1] / cnt[0],
                "adjacent_among_differing": cnt[3] / cnt[1],
                "accepted_adjacent_fraction_of_accepted": cnt[5] / max(cnt[4], 1),
                "acceptance_rate_among_differing": cnt[4] / cnt[1],
            }
        )
        s = stats[-1]
        print(
            n,
            T,
            "adj=%.5f (4/N^2=%.5f) adj|diff=%.5f"
            % (s["adjacent_rate"], s["theory_4_over_n2"], s["adjacent_among_differing"]),
        )
out["adjacency"] = [
    {k: (float(v) if isinstance(v, (np.floating,)) else v) for k, v in s.items()} for s in stats
]

# (iii) seeding claim, one isolated fresh process per measurement
probe = """
import sys; sys.path.insert(0, %r)
import numpy as np, hashlib
from kawasaki_ising.core import initial_lattice, kawasaki_step, seed_all
mode, repeats = sys.argv[1], int(sys.argv[2])
def sd():
    np.random.seed(20260728) if mode == "bare" else seed_all(20260728)
def run():
    sd(); l = initial_lattice(24, 0.2, np.random.default_rng(20260728)); sd()
    for _ in range(10): l = kawasaki_step(l, beta=1.0, n=24)
    return hashlib.md5(l.tobytes()).hexdigest()[:12]
print(" ".join(run() for _ in range(repeats)))
""" % str(ROOT / "src")
seeding = {}
for mode in ["bare", "seed_all"]:
    across = [
        subprocess.run(
            [sys.executable, "-I", "-c", probe, mode, "1"], capture_output=True, text=True
        ).stdout.strip()
        for _ in range(6)
    ]
    within = (
        subprocess.run([sys.executable, "-I", "-c", probe, mode, "4"], capture_output=True, text=True)
        .stdout.strip()
        .split()
    )
    seeding[mode] = {
        "first_run_hash_in_6_fresh_processes": across,
        "distinct_across_processes": len(set(across)),
        "4_repeated_seeded_runs_in_one_process": within,
        "distinct_within_process": len(set(within)),
    }
out["seeding"] = seeding
print(json.dumps(seeding, indent=1))

# (iv) speed-up
n = 100
lat = initial_lattice(n, 0.2, np.random.default_rng(1))
seed_all(1)
kawasaki_step(lat, 1.0, n)
t = time.perf_counter()
for _ in range(200):
    lat = kawasaki_step(lat, 1.0, n)
jit = (time.perf_counter() - t) / 200
code2 = """
import os, sys, time; os.environ['NUMBA_DISABLE_JIT']='1'; sys.path.insert(0,%r)
import numpy as np
from kawasaki_ising.core import kawasaki_step, initial_lattice
n=100; l=initial_lattice(n,0.2,np.random.default_rng(1))
t=time.perf_counter()
for _ in range(5): l=kawasaki_step(l,1.0,n)
print((time.perf_counter()-t)/5)
""" % str(ROOT / "src")
py = float(subprocess.run([sys.executable, "-I", "-c", code2], capture_output=True, text=True).stdout.strip())
out["speed"] = {"n": n, "jit_sec_per_sweep": jit, "python_sec_per_sweep": py, "speedup": py / jit}
print(out["speed"])
(ROOT / "results/paper/E3_verify_dynamics.json").write_text(json.dumps(out, indent=1, default=float))
