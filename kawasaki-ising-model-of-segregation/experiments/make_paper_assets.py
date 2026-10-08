"""Generate every figure, table and number used in paper/ from results/paper/*.{json,npz}.

Tables and figures are written to paper/generated and paper/figures; numbers.tex defines the macros
used for the numbers quoted in the text.
"""

import json
import re
import sys
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).parent))
from common import yang_binodal_T, TC_ONSAGER  # noqa

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results/paper"
PAPER = ROOT / "paper"
(PAPER / "figures").mkdir(parents=True, exist_ok=True)
(PAPER / "generated").mkdir(parents=True, exist_ok=True)
plt.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["DejaVu Serif"],
        "mathtext.fontset": "dejavuserif",
        "font.size": 8,
        "axes.labelsize": 8,
        "axes.titlesize": 8,
        "legend.fontsize": 7,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "grid.linewidth": 0.5,
        "savefig.bbox": "tight",
        "pdf.fonttype": 42,
    }
)
C = {"a": "#1f4e9c", "b": "#c0392b", "c": "#2e7d32", "d": "#6b6b6b", "e": "#e08e0b"}
macros = []


def mac(name, val):
    macros.append("\\newcommand{\\%s}{%s}" % (name, val))


def sci(x, d=1):
    m, e = f"{x:.{d}e}".split("e")
    return f"{m}\\times10^{{{int(e)}}}"


# ---------------------------------------------------------------- E1
e1 = json.loads((RES / "E1_exact_local.json").read_text())
mac("EoneConfigs", f"{e1['configs']:,}".replace(",", "\\,"))
mac("EoneAdj", f"{e1['adjacent_configs']:,}".replace(",", "\\,"))
mac("EoneNonadj", f"{e1['nonadjacent_configs']:,}".replace(",", "\\,"))
mac("EoneDisp", e1["displacements"])
mac("EoneMismatch", e1["fixed_mismatch"] + e1["pairsum_mismatch_nonadj"])

# ---------------------------------------------------------------- E2
e2 = json.loads((RES / "E2_exact_chain.json").read_text())
mac("EtwoMaxTVcorrect", sci(max(r[k]["TV_to_Boltzmann"] for r in e2 for k in ["correct"]), 1))
mac("EtwoMaxStatRes", sci(max(r["correct"]["boltz_stationarity_residual"] for r in e2), 1))
pair = [r for r in e2 if r["proposal"] == "pair"]
nn = [r for r in e2 if r["proposal"] == "nn"]
mac("EtwoPairMin", f"{min(r['pair_sum']['TV_to_Boltzmann'] for r in pair):.2f}")
mac("EtwoPairMax", f"{max(r['pair_sum']['TV_to_Boltzmann'] for r in pair):.2f}")
mac("EtwoNNMin", f"{min(r['pair_sum']['TV_to_Boltzmann'] for r in nn):.2f}")
mac("EtwoNNMax", f"{max(r['pair_sum']['TV_to_Boltzmann'] for r in nn):.2f}")


def e2table(rows_sel, path, caption_T=None):
    lines = []
    for L, M in sorted({(r["L"], r["M"]) for r in e2}):
        for T in sorted({r["T"] for r in e2}):
            if caption_T is not None and T not in caption_T:
                continue
            rp = next(r for r in e2 if (r["L"], r["M"], r["T"], r["proposal"]) == (L, M, T, "pair"))
            rn = next(r for r in e2 if (r["L"], r["M"], r["T"], r["proposal"]) == (L, M, T, "nn"))
            lines.append(
                f"${L}\\times{L}$ & {M} & {rp['correct']['states']:,} & {T:g} & ${sci(rp['correct']['TV_to_Boltzmann'],0)}$ & {rp['pair_sum']['TV_to_Boltzmann']:.3f} & "
                f"{rp['pair_sum']['meanE_stationary']-rp['pair_sum']['meanE_boltzmann']:+.3f} & {rn['pair_sum']['TV_to_Boltzmann']:.3f} & "
                f"{rn['pair_sum']['meanE_stationary']-rn['pair_sum']['meanE_boltzmann']:+.3f} \\\\".replace(
                    ",", "\\,"
                )
            )
    (PAPER / "generated" / path).write_text("\n".join(lines) + "\n")


e2table(e2, "tab_E2_main.tex", caption_T=[2.269])
e2table(e2, "tab_E2_full.tex")

# ---------------------------------------------------------------- E3
e3 = json.loads((RES / "E3_verify_dynamics.json").read_text())
adj = e3["adjacency"]
lines = []
for r in adj:
    lines.append(
        f"{r['n']} & {r['T']:g} & {r['adjacent_rate']:.5f} & {r['theory_4_over_n2']:.5f} & {r['adjacent_among_differing']:.5f} & {r['acceptance_rate_among_differing']:.3f} \\\\"
    )
(PAPER / "generated/tab_E3_adjacency.tex").write_text("\n".join(lines) + "\n")
r100 = [r for r in adj if r["n"] == 100]
mac("EthreeAdjHundred", f"{np.mean([r['adjacent_rate'] for r in r100]):.5f}")
mac("EthreeAdjDiffMaxHundred", f"{max(r['adjacent_among_differing'] for r in r100):.5f}")
mac(
    "EthreeEquivOK",
    "yes" if all(e["package==fixed_variant"] and e["package==counted"] for e in e3["equivalence"]) else "NO",
)
sd = e3["seeding"]
mac("EthreeBareAcross", sd["bare"]["distinct_across_processes"])
mac("EthreeBareWithin", sd["bare"]["distinct_within_process"])
mac("EthreeSeedAcross", sd["seed_all"]["distinct_across_processes"])
mac("EthreeSeedWithin", sd["seed_all"]["distinct_within_process"])
mac("EthreeSpeedup", f"{e3['speed']['speedup']:.0f}")
mac("EthreeJit", f"{e3['speed']['jit_sec_per_sweep']*1e3:.2f}")
mac("EthreePy", f"{e3['speed']['python_sec_per_sweep']*1e3:.0f}")

# ---------------------------------------------------------------- E4
if (RES / "E4_adjacency_impact.json").exists():
    e4 = json.loads((RES / "E4_adjacency_impact.json").read_text())
    lines = []
    for r in e4:
        lines.append(
            f"{r['N']} & {r['T']:g} & {r['R']} & {r['e_corrected']:.5f} & {r['e_uncorrected']:.5f} & {r['diff']:+.5f} & {r['se']:.5f} & {r['z']:+.1f} \\\\"
        )
    (PAPER / "generated/tab_E4.tex").write_text("\n".join(lines) + "\n")
    from scipy import stats

    fig, ax = plt.subplots(figsize=(3.4, 2.5))
    fitrows = []
    for T, col, mk in zip([1.5, 2.269, 3.0], [C["a"], C["b"], C["c"]], ["o", "s", "^"]):
        rr = [r for r in e4 if r["T"] == T]
        N = np.array([r["N"] for r in rr], float)
        d = np.array([r["diff"] for r in rr])
        se = np.array([r["se"] for r in rr])
        x = 1.0 / N**2
        w = 1.0 / se**2
        c = np.sum(w * x * d) / np.sum(w * x * x)
        c_se = 1.0 / np.sqrt(np.sum(w * x * x))
        chi2 = np.sum(w * (d - c * x) ** 2)
        dof = len(N) - 1
        p_fit = 1 - stats.chi2.cdf(chi2, dof)
        chi2_null = np.sum(w * d**2)
        p_null = 1 - stats.chi2.cdf(chi2_null, len(N))
        fitrows.append((T, c, c_se, chi2, dof, p_fit, chi2_null, p_null))
        ax.errorbar(
            N, d, yerr=1.96 * se, fmt=mk, ms=3.5, lw=0.9, capsize=2, color=col, label=f"$T={T:g}$", alpha=0.9
        )
        Ng = np.geomspace(8, 100, 50)
        ax.plot(Ng, c / Ng**2, "--", color=col, lw=0.8)
    ax.axhline(0, color="k", lw=0.5)
    ax.set_xscale("log")
    ax.set_xlabel("lattice size $N$")
    ax.set_ylabel(r"$\langle e\rangle_{\rm uncorr}-\langle e\rangle_{\rm corr}$")
    ax.set_xticks([8, 16, 32, 64, 100])
    ax.set_xticklabels([8, 16, 32, 64, 100])
    ax.legend(frameon=False)
    fig.savefig(PAPER / "figures/fig_adjacency_impact.pdf")
    plt.close(fig)
    (PAPER / "generated/tab_E4_fit.tex").write_text(
        "\n".join(
            f"{T:g} & {c:.2f} & {cs:.2f} & {chi2:.1f} ({dof}) & {pf:.2f} & {chn:.0f} & {'$<10^{-6}$' if pn<1e-6 else f'{pn:.3f}'} \\\\"
            for T, c, cs, chi2, dof, pf, chn, pn in fitrows
        )
        + "\n"
    )
    mac(
        "EfourSmallRatio",
        f"{[r for r in e4 if r['N']==8 and r['T']==1.5][0]['diff']/[r for r in e4 if r['N']==16 and r['T']==1.5][0]['diff']:.1f}",
    )
    mac("EfourPredThirtyTwo", f"{np.mean([f_[1] for f_ in fitrows])/32**2:.4f}")
    mac("EfourSeThirtyTwo", f"{np.mean([r['se'] for r in e4 if r['N']==32]):.4f}")
    mac("EfourCountLargeSig", f"{sum(1 for r in e4 if r['N']>=32 and abs(r['z'])>1.96)}")
    mac("EfourCountLarge", f"{sum(1 for r in e4 if r['N']>=32)}")
    for r in e4:
        if r["N"] == 100 and r["T"] == 2.269:
            mac("EfourHundredZ", f"{r['z']:+.1f}")
    mac("EfourMaxAbsZ", f"{max(abs(r['z']) for r in e4):.1f}")
    mac("EfourSmallN", f"{max(abs(r['z']) for r in e4 if r['N']==8):.1f}")

# ---------------------------------------------------------------- E2 figure
fig, axs = plt.subplots(1, 2, figsize=(6.5, 2.3), sharey=True)
for ax, prop, ttl in zip(
    axs,
    ["pair", "nn"],
    ["Uniform random-pair proposal (production)", "Nearest-neighbour proposal (classical Kawasaki)"],
):
    systems = sorted({(r["L"], r["M"]) for r in e2})
    Ts = sorted({r["T"] for r in e2})
    w = 0.2
    for k, T in enumerate(Ts):
        v = [
            next(r for r in e2 if (r["L"], r["M"], r["T"], r["proposal"]) == (L, M, T, prop))["pair_sum"][
                "TV_to_Boltzmann"
            ]
            for L, M in systems
        ]
        ax.bar(
            np.arange(len(systems)) + (k - 1.5) * w,
            v,
            w,
            label=f"$T={T:g}$",
            color=[C["a"], C["b"], C["e"], C["c"]][k],
        )
    ax.set_xticks(range(len(systems)))
    ax.set_xticklabels([f"${L}\\times{L}$\n$M={M}$" for L, M in systems])
    ax.set_title(ttl)
    ax.set_ylim(0, 0.85)
axs[0].set_ylabel(r"$d_{\rm TV}(\tilde\pi,\pi_{\beta,M})$")
axs[0].legend(frameon=False, ncol=2)
fig.savefig(PAPER / "figures/fig_exact_tv.pdf")
plt.close(fig)

# ---------------------------------------------------------------- E5
if (RES / "E5_demixing.npz").exists():
    z = np.load(RES / "E5_demixing.npz")
    fr = z["fracs"]
    Ts = z["temps"]
    R = int(z["R"])
    rng = np.random.default_rng(12345)
    B = 4000
    Tb = np.array([yang_binodal_T(f) for f in fr])
    out = {}
    rows_tab = []
    for n in [32, 64, 100]:
        V = z[f"varE_{n}"]  # (F, T, R)
        Cv = V / (n**2 * Ts[None, :, None] ** 2)
        for name, arr in [("V", V), ("C", Cv)]:
            per_rep = Ts[np.argmax(arr, axis=1)]  # (F, R)
            mean_curve = arr.mean(axis=2)
            peak = Ts[np.argmax(mean_curve, axis=1)]
            ci = np.empty((len(fr), 2))
            for i in range(len(fr)):
                bs = np.empty(B)
                for b in range(B):
                    idx = rng.integers(0, R, R)
                    bs[b] = Ts[np.argmax(arr[i][:, idx].mean(axis=1))]
                ci[i] = np.percentile(bs, [2.5, 97.5])
            out[(n, name)] = dict(
                per_rep_mean=per_rep.mean(1), per_rep_sd=per_rep.std(1, ddof=1), peak=peak, ci=ci
            )
    # table: all N, estimator V (single-run stats, mean-curve peak, bootstrap CI) and C-peak
    for n in [32, 64, 100]:
        o = out[(n, "V")]
        for i, f in enumerate(fr):
            se = o["per_rep_sd"][i] / np.sqrt(R)
            zz = (o["per_rep_mean"][i] - Tb[i]) / se
            inside = "yes" if o["ci"][i][0] <= Tb[i] <= o["ci"][i][1] else "no"
            rows_tab.append(
                f"{n} & {f:.2f} & {Tb[i]:.3f} & {o['per_rep_mean'][i]:.3f} & {o['per_rep_sd'][i]:.3f} & {zz:+.1f} & {o['peak'][i]:.2f} & [{o['ci'][i][0]:.2f}, {o['ci'][i][1]:.2f}] & {inside} & {out[(n,'C')]['peak'][i]:.2f} \\\\"
            )
        rows_tab.append("\\midrule" if n != 100 else "")
    (PAPER / "generated/tab_E5.tex").write_text("\n".join(rows_tab) + "\n")
    ext_idx = [i for i, f in enumerate(fr) if f in (0.05, 0.10, 0.95)]
    cen_idx = [i for i, f in enumerate(fr) if 0.2 - 1e-9 <= f <= 0.8 + 1e-9]

    def count_contained(idx, key="V"):
        return sum(
            1
            for n in [32, 64, 100]
            for i in idx
            if out[(n, key)]["ci"][i][0] <= Tb[i] <= out[(n, key)]["ci"][i][1]
        )

    mac("EfiveCentralIn", count_contained(cen_idx))
    mac("EfiveCentralTot", 3 * len(cen_idx))
    mac("EfiveExtremeIn", count_contained(ext_idx))
    mac("EfiveExtremeTot", 3 * len(ext_idx))
    mac("EfiveCentralInC", count_contained(cen_idx, "C"))
    mac("EfiveExtremeInC", count_contained(ext_idx, "C"))
    bias_ext = np.array([out[(n, "V")]["per_rep_mean"][i] - Tb[i] for n in [32, 64, 100] for i in ext_idx])
    z_ext = np.array(
        [
            (out[(n, "V")]["per_rep_mean"][i] - Tb[i]) / (out[(n, "V")]["per_rep_sd"][i] / np.sqrt(R))
            for n in [32, 64, 100]
            for i in ext_idx
        ]
    )
    z_cen = np.array(
        [
            (out[(n, "V")]["per_rep_mean"][i] - Tb[i]) / (out[(n, "V")]["per_rep_sd"][i] / np.sqrt(R))
            for n in [32, 64, 100]
            for i in cen_idx
        ]
    )
    mac("EfiveExtBiasMin", f"{bias_ext.min():+.2f}")
    mac("EfiveExtBiasMax", f"{bias_ext.max():+.2f}")
    mac("EfiveExtZMin", f"{np.abs(z_ext).min():.1f}")
    mac("EfiveCenZMax", f"{np.abs(z_cen).max():.1f}")
    mac("EfiveCenZGtTwo", int((np.abs(z_cen) > 2).sum()))
    mac("EfiveCenTot", len(z_cen))
    allsd = np.concatenate([out[(n, "V")]["per_rep_sd"] for n in [32, 64, 100]])
    wid = np.array(
        [out[(n, "V")]["ci"][i][1] - out[(n, "V")]["ci"][i][0] for n in [32, 64, 100] for i in cen_idx]
    )
    mac("EfiveCIWidthMin", f"{wid.min():.2f}")
    mac("EfiveCIWidthMax", f"{wid.max():.2f}")
    bias_cen = np.array([out[(n, "V")]["per_rep_mean"][i] - Tb[i] for n in [32, 64, 100] for i in cen_idx])
    mac("EfiveCenBiasMax", f"{np.abs(bias_cen).max():.2f}")
    mac("EfiveSdMin", f"{allsd.min():.2f}")
    mac("EfiveSdMax", f"{allsd.max():.2f}")
    i5 = list(np.round(fr, 2)).index(0.05)
    for n, tag in [(32, "XXXII"), (64, "LXIV"), (100, "C")]:
        mac(f"EfiveMeanAtFiveHundredth{tag}", f"{out[(n,'V')]['per_rep_mean'][i5]:.2f}")
    mac("EfiveTbAtFiveHundredth", f"{Tb[i5]:.2f}")
    # single-seed values versus replicate distribution (N=100)
    e6 = json.loads((RES / "E6_single_seed.json").read_text())
    zs = []
    for r in e6["rows"]:
        i = list(np.round(fr, 2)).index(round(r["f"], 2))
        zs.append(
            (r["T_demix_single"] - out[(100, "V")]["per_rep_mean"][i]) / out[(100, "V")]["per_rep_sd"][i]
        )
    mac("EsixZMax", f"{np.max(np.abs(zs)):.1f}")
    # symmetry test f vs 1-f for N=100
    o = out[(100, "V")]
    sym = []
    for fa, fb in [(0.05, 0.95), (0.20, 0.80), (0.40, 0.60)]:
        ia, ib = list(np.round(fr, 2)).index(fa), list(np.round(fr, 2)).index(fb)
        sym.append((fa, fb, o["per_rep_mean"][ia], o["per_rep_mean"][ib]))
    mac("EfiveSymMin", f"{min(abs(x-y) for _,_,x,y in sym):.2f}")
    mac("EfiveSymMax", f"{max(abs(x-y) for _,_,x,y in sym):.2f}")
    (PAPER / "generated/tab_E5_sym.tex").write_text(
        "\n".join(f"{a:.2f} & {b:.2f} & {x:.3f} & {y:.3f} & {abs(x-y):.3f} \\\\" for a, b, x, y in sym) + "\n"
    )
    # Figure: estimator vs exact binodal
    fig, axs = plt.subplots(1, 3, figsize=(6.5, 2.4), sharey=True)
    ff = np.linspace(0.005, 0.995, 400)
    Tb_curve = np.array([yang_binodal_T(f) for f in ff])
    for ax, n in zip(axs, [32, 64, 100]):
        o = out[(n, "V")]
        ax.plot(ff, Tb_curve, color=C["b"], lw=1.2, label="exact binodal $T_b(f)$ (Yang)")
        ax.axhline(TC_ONSAGER, color=C["d"], lw=0.7, ls=":")
        ax.errorbar(
            fr,
            o["per_rep_mean"],
            yerr=o["per_rep_sd"],
            fmt="o",
            ms=3.5,
            capsize=2,
            lw=0.9,
            color=C["a"],
            label=r"single-run argmax $\hat T$ (mean $\pm$ s.d., $R=%d$)" % R,
        )
        ax.plot(fr, o["peak"], "x", ms=4, color=C["e"], label=r"argmax of replicate-mean ${\rm Var}(E)$")
        ax.set_title(f"$N={n}$")
        ax.set_xlabel("immigrant fraction $f$")
        ax.set_ylim(1.45, 3.05)
    axs[0].set_ylabel("temperature")
    h, l = axs[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=3, frameon=False, fontsize=6.5, bbox_to_anchor=(0.5, -0.12))
    fig.savefig(PAPER / "figures/fig_demixing.pdf")
    plt.close(fig)
    # Figure: Var(E)/N^2 curves with replicate spread, N=100, selected fractions
    fig, axs = plt.subplots(1, 3, figsize=(6.5, 2.1), sharex=True)
    for ax, f in zip(axs, [0.05, 0.20, 0.50]):
        i = list(np.round(fr, 2)).index(f)
        for n, col in zip([32, 64, 100], [C["c"], C["e"], C["a"]]):
            v = z[f"varE_{n}"][i] / n**2
            m = v.mean(1)
            se = v.std(1, ddof=1) / np.sqrt(R)
            ax.plot(Ts, m, color=col, lw=1, label=f"$N={n}$")
            ax.fill_between(Ts, m - se, m + se, color=col, alpha=0.25, lw=0)
        ax.axvline(yang_binodal_T(f), color=C["b"], lw=1, ls="--")
        ax.set_title(f"$f={f:g}$")
        ax.set_xlabel("$T$")
    axs[0].set_ylabel(r"${\rm Var}(E)/N^2$")
    axs[0].legend(frameon=False)
    fig.savefig(PAPER / "figures/fig_variance_curves.pdf")
    plt.close(fig)
    mac("EfiveR", R)
    mac("EfiveBurn", int(z["burn"]))
    mac("EfiveSample", int(z["sample"]))
    mac("EfiveGridStep", f"{Ts[1]-Ts[0]:.2f}")
    mac("EfiveNT", len(Ts))
    json.dump(
        {f"{n}_{k}": {kk: np.asarray(vv).tolist() for kk, vv in v.items()} for (n, k), v in out.items()}
        | {"binodal": Tb.tolist(), "fracs": fr.tolist()},
        open(RES / "E5_analysis.json", "w"),
        indent=1,
    )


# ---------------------------------------------------------------- binodal macros, E6, E8
for name, f in [("EbFiveHundredth", 0.05), ("EbTenth", 0.10), ("EbFifth", 0.20), ("EbThree", 0.30)]:
    mac(name, f"{yang_binodal_T(f):.3f}")
mac("EbHalf", f"{TC_ONSAGER:.4f}")
mac("EbDevTwoTenths", f"{TC_ONSAGER-yang_binodal_T(0.2):.4f}")
mac("EbDevThreeTenths", f"{TC_ONSAGER-yang_binodal_T(0.3):.4f}")
mac("EbRelTwoTenths", f"{100*(TC_ONSAGER-yang_binodal_T(0.2))/TC_ONSAGER:.1f}")
e6 = json.loads((RES / "E6_single_seed.json").read_text())
lines = []
for r in e6["rows"]:
    lines.append(
        f"{r['f']:.2f} & {r['T_binodal_exact']:.3f} & {r['T_demix_single']:.3f} & {r['T_demix_single']-r['T_binodal_exact']:+.3f} \\\\"
    )
(PAPER / "generated/tab_E6.tex").write_text("\n".join(lines) + "\n")
dev = [r["T_demix_single"] - r["T_binodal_exact"] for r in e6["rows"]]
mac("EsixMaxAbsDev", f"{max(abs(d) for d in dev):.2f}")
mac("EsixMaxOver", f"{max(r['T_demix_single'] for r in e6['rows']):.3f}")
mac("EsixMinDev", f"{min(dev):+.2f}")
mac("EsixMaxDev", f"{max(dev):+.2f}")
mac("EsixAsym", f"{abs(e6['rows'][0]['T_demix_single']-e6['rows'][-1]['T_demix_single']):.2f}")
e8 = json.loads((RES / "E8_metric_invariance.json").read_text())
mac("EeightPerSpread", sci(e8["periodic_spread"], 1))
mac("EeightNonSpread", f"{e8['nonperiodic_spread']:.1f}")
mac("EeightNonMin", f"{e8['nonperiodic_min']:.1f}")
mac("EeightNonMax", f"{e8['nonperiodic_max']:.1f}")
mac("EeightNonRel", f"{100*e8['nonperiodic_rel_spread']:.0f}")
mac("EeightPer", f"{e8['periodic_min']:.2f}")

# ---------------------------------------------------------------- E9a / E9b
if (RES / "E9a_equilibration.json").exists():
    e9a = json.loads((RES / "E9a_equilibration.json").read_text())
    lines = []
    for r in e9a:
        lines.append(
            f"{r['N']} & {r['f']:.2f} & {r['T']:g} & {r['mean_offset_in_sd']:+.1f} & {r['var_protocol']:.0f} & {r['var_late_full']:.0f} & {r['var_protocol']/r['var_late_full']:.2f} \\\\"
        )
    (PAPER / "generated/tab_E9a.tex").write_text("\n".join(lines) + "\n")
    ratio = np.array([r["var_protocol"] / r["var_late_full"] for r in e9a])
    mac("EnineaRatioMin", f"{ratio.min():.2f}")
    mac("EnineaRatioMax", f"{ratio.max():.2f}")
    mac("EnineaRatioMedian", f"{np.median(ratio):.2f}")
    mac("EnineaBelowHalf", int((ratio < 0.5).sum()))
    mac("EnineaCases", len(ratio))
    off = np.array([abs(r["mean_offset_in_sd"]) for r in e9a])
    mac("EnineaOffMax", f"{off.max():.1f}")
    mac("EnineaOffGtOne", int((off > 1).sum()))
    mac("EnineaTotalSweeps", f"{40000:,}".replace(",", "\\,"))
if (RES / "E9b_equilibrium_variance.json").exists():
    d = json.loads((RES / "E9b_equilibrium_variance.json").read_text())
    rows = d["rows"]
    Tg = np.array(d["temps"])
    z5 = np.load(RES / "E5_demixing.npz")
    systems = sorted({(r[0], r[1]) for r in rows})
    tab = []
    curves = {}
    for n, f in systems:
        rr = [r for r in rows if r[0] == n and r[1] == f]
        reps = sorted({r[3] for r in rr})
        V = np.full((len(Tg), len(reps)), np.nan)
        tau = np.full((len(Tg), len(reps)), np.nan)
        for r in rr:
            V[r[2], reps.index(r[3])] = r[5]
            tau[r[2], reps.index(r[3])] = r[8]
        Vm, taum = V.mean(1), tau.mean(1)
        peak = Tg[np.argmax(Vm)]
        per = Tg[np.argmax(V, axis=0)]
        Cm = (V / (n**2 * Tg[:, None] ** 2)).mean(1)
        peakC = Tg[np.argmax(Cm)]
        fi = list(np.round(z5["fracs"], 2)).index(round(f, 2))
        Vp = z5[f"varE_{n}"][fi].mean(2 - 1)  # (T,)
        Tp = z5["temps"]
        prot_peak = Tp[np.argmax(Vp)]
        Tbf = yang_binodal_T(f)
        curves[(n, f)] = (Vm, taum, V, Vp, Tp)
        tab.append(
            f"{n} & {f:.2f} & {Tbf:.3f} & {peak:.2f} & {per.min():.2f}--{per.max():.2f} & {peakC:.2f} & {prot_peak:.2f} & {taum[np.argmax(Vm)]:.0f} \\\\"
        )
    (PAPER / "generated/tab_E9b.tex").write_text("\n".join(tab) + "\n")
    # figure: equilibrium vs protocol variance curves, tau_int
    sel = [(32, 0.05), (32, 0.10), (32, 0.20), (32, 0.50), (64, 0.05), (64, 0.50)]
    fig, axs = plt.subplots(2, 3, figsize=(6.5, 3.9), sharex=True)
    for ax, (n, f) in zip(axs.ravel(), sel):
        Vm, taum, V, Vp, Tp = curves[(n, f)]
        ax.plot(Tg, Vm / n**2, color=C["a"], lw=1.1, label="equilibrium (50,000 sweeps)")
        ax.plot(Tp, Vp / n**2, color=C["e"], lw=1.0, label="protocol (300 sweeps), E5")
        ax.axvline(yang_binodal_T(f), color=C["b"], ls="--", lw=0.9)
        ax2 = ax.twinx()
        ax2.plot(
            Tg,
            np.nanmean(
                np.array(
                    [[r[8] for r in rows if r[0] == n and r[1] == f and r[2] == ti] for ti in range(len(Tg))]
                ),
                axis=1,
            ),
            color=C["d"],
            lw=0.7,
            ls=":",
        )
        ax2.set_yscale("log")
        ax2.minorticks_off()
        ax2.tick_params(labelsize=5)
        ax2.grid(False)
        ax2.spines["right"].set_visible(True)
        ax.set_title(f"$N={n}$, $f={f:g}$")
        if ax in axs[1]:
            ax.set_xlabel("$T$")
    axs[0, 0].set_ylabel(r"${\rm Var}(E)/N^2$")
    axs[1, 0].set_ylabel(r"${\rm Var}(E)/N^2$")
    h, l = axs[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=2, frameon=False, bbox_to_anchor=(0.5, -0.04))
    fig.text(
        0.995, 0.5, r"$\tau_{\rm int}$ (dotted, sweeps, log scale)", rotation=90, va="center", fontsize=7
    )
    fig.tight_layout(rect=(0, 0.04, 0.98, 1))
    fig.savefig(PAPER / "figures/fig_equilibrium.pdf")
    plt.close(fig)
    taus = np.array([r[8] for r in rows])
    mac("EninebTauMax", f"{taus.max():.0f}")
    mac("EninebTauMedian", f"{np.median(taus):.0f}")
    mac("EninebRuns", len(rows))

(PAPER / "generated/numbers.tex").write_text("\n".join(macros) + "\n")
# LaTeX workaround: table-body files must not end in a row break (the \\ after \input supplies it)
for _f in (PAPER / "generated").glob("tab_*.tex"):
    _t = _f.read_text().rstrip()
    _f.write_text(re.sub(r"\s*\\\\$", "", _t))
print("assets written;", len(macros), "macros")
