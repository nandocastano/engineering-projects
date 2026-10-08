"""E2: exact stationary distributions of the pair-exchange chains on small tori.

Builds the full transition matrix on the fixed-composition state space
Omega_M = {sigma in {-1,1}^(L^2): #(+1) = M} for the corrected rule and for the
uncorrected pair-sum rule, for (a) the production proposal (uniform random ordered
site pair) and (b) a nearest-neighbour-only proposal (classical Kawasaki).
Reports TV distance to the Boltzmann law pi(sigma) ~ exp(-E/T), the largest
detailed-balance residual and the shift of the mean energy.
"""

import itertools
import json
import sys
from pathlib import Path

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

sys.path.insert(0, str(Path(__file__).parent))
from common import total_energy  # noqa


def build(L, M, T, rule, proposal):
    nsite = L * L
    combos = list(itertools.combinations(range(nsite), M))
    index = {c: i for i, c in enumerate(combos)}
    S = len(combos)
    E = np.empty(S)

    def lat_of(c):
        lat = -np.ones(nsite, dtype=np.int8)
        lat[list(c)] = 1
        return lat.reshape(L, L)

    for i, c in enumerate(combos):
        E[i] = total_energy(lat_of(c), L)

    def nb(s):
        x, y = divmod(s, L)
        return {((x + 1) % L) * L + y, ((x - 1) % L) * L + y, x * L + (y + 1) % L, x * L + (y - 1) % L}

    NB = [nb(s) for s in range(nsite)]
    rows, cols, vals = [], [], []
    diag = np.ones(S)
    for i, c in enumerate(combos):
        cs = set(c)
        for u in c:
            for v in range(nsite):
                if v in cs:
                    continue
                adj = v in NB[u]
                if proposal == "nn":
                    if not adj:
                        continue
                    q = 2.0 / (
                        nsite * 4
                    )  # pick site, then one of 4 neighbours; both orders lead to the same swap
                else:
                    q = 2.0 / nsite**2  # ordered pair uniform; (u,v) and (v,u) give the same swap
                new = cs.symmetric_difference({u, v})
                j = index[tuple(sorted(new))]
                dE_true = E[j] - E[i]
                dE = dE_true if rule == "correct" else dE_true - (4.0 if adj else 0.0)
                a = 1.0 if dE <= 0 else np.exp(-dE / T)
                rows.append(i)
                cols.append(j)
                vals.append(q * a)
                diag[i] -= q * a
    P = sp.csr_matrix((vals, (rows, cols)), shape=(S, S)) + sp.diags(diag)
    return P, E


def stationary(P):
    S = P.shape[0]
    A = (P.T - sp.identity(S)).tocsc()
    B = A[:-1, :-1]
    rhs = -np.asarray(A[:-1, -1].todense()).ravel()
    x = spla.spsolve(B.tocsc(), rhs)
    pi = np.append(x, 1.0)
    return pi / pi.sum()


out = []
for L, M in [(3, 3), (3, 4), (4, 4), (4, 6)]:
    for T in [1.0, 2.0, 2.269, 3.0]:
        for proposal in ["pair", "nn"]:
            rec = {"L": L, "M": M, "T": T, "proposal": proposal}
            for rule in ["correct", "pair_sum"]:
                P, E = build(L, M, T, rule, proposal)
                pi = stationary(P)
                boltz = np.exp(-(E - E.min()) / T)
                boltz /= boltz.sum()
                tv = 0.5 * np.abs(pi - boltz).sum()
                # detailed balance residual w.r.t. Boltzmann: max |boltz_i P_ij - boltz_j P_ji|
                Pc = P.tocoo()
                F = sp.csr_matrix((boltz[Pc.row] * Pc.data, (Pc.row, Pc.col)), shape=P.shape)
                db = abs(F - F.T).max()
                stat_res = np.abs(boltz @ P - boltz).max()
                rec[rule] = {
                    "TV_to_Boltzmann": float(tv),
                    "max_DB_residual": float(db),
                    "boltz_stationarity_residual": float(stat_res),
                    "meanE_stationary": float(pi @ E),
                    "meanE_boltzmann": float(boltz @ E),
                    "states": int(P.shape[0]),
                }
            out.append(rec)
            print(
                L,
                M,
                T,
                proposal,
                "correct TV=%.2e  pair_sum TV=%.3e  dE=%.4f"
                % (
                    rec["correct"]["TV_to_Boltzmann"],
                    rec["pair_sum"]["TV_to_Boltzmann"],
                    rec["pair_sum"]["meanE_stationary"] - rec["pair_sum"]["meanE_boltzmann"],
                ),
                flush=True,
            )
Path(__file__).resolve().parents[1].joinpath("results/paper/E2_exact_chain.json").write_text(
    json.dumps(out, indent=1)
)
