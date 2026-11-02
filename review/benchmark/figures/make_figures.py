"""Regenerate every paper figure from the committed benchmark CSVs.

Usage: python review/benchmark/figures/make_figures.py
Writes fig_*.pdf (vector) and fig_*.png (300 dpi) next to this script. Sized for a single column
(3.5 in wide); Okabe-Ito colours (colour-blind safe) plus hatching where bars must be told apart in
greyscale.
"""
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

B = Path(__file__).resolve().parent.parent  # review/benchmark
OUT = Path(__file__).resolve().parent
W = 3.5  # single-column width, inches
OI = {"orange": "#E69F00", "sky": "#56B4E9", "green": "#009E73", "yellow": "#F0E442", "blue": "#0072B2",
      "red": "#D55E00", "purple": "#CC79A7", "black": "#000000", "grey": "#999999"}
plt.rcParams.update({"font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8, "legend.fontsize": 7,
                     "xtick.labelsize": 7, "ytick.labelsize": 7, "pdf.fonttype": 42, "ps.fonttype": 42,
                     "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False})


def save(fig, name: str) -> None:
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(OUT / f"{name}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("wrote", name)


def bars(ax, groups, series, values, colours, hatches=None, errs=None, width=0.8, na_text="n/a"):
    """Grouped bars; values[s][g] may be NaN (drawn as a small 'n/a' label)."""
    k = len(series)
    x = np.arange(len(groups))
    for i, s in enumerate(series):
        v = np.array(values[s], dtype=float)
        pos = x - width / 2 + (i + 0.5) * width / k
        ax.bar(pos, np.nan_to_num(v), width / k, color=colours[i], label=s, edgecolor="white", linewidth=0.4,
               hatch=(hatches or [None] * k)[i], yerr=None if errs is None else np.nan_to_num(errs[s]),
               error_kw={"elinewidth": 0.6, "capsize": 1.2})
        for p, val in zip(pos, v):
            if np.isnan(val):
                ax.text(p, 0.02, na_text, rotation=90, ha="center", va="bottom", fontsize=5.5, color=OI["grey"])
    ax.set_xticks(x)
    ax.set_xticklabels(groups)
    return x


# --------------------------------------------------------------------------- (a) collapse
def fig_collapse() -> None:
    fs = "g1g2_notime"  # the only feature set available for every dataset and every protocol
    within = {d: pd.read_csv(B / d / "summary.csv").query("feature_set == @fs").set_index("experiment")
              for d in ("mta", "mcfp", "raid", "hikari")}
    e4 = pd.read_csv(B / "e4" / "summary.csv").query("feature_set == @fs").set_index("pair")
    e4_pair = {"mta": "mta>mcfp", "mcfp": "mcfp>mta", "raid": "raid>mta", "hikari": None}
    names = {"mta": "MTA", "mcfp": "MCFP", "raid": "RAID", "hikari": "HIKARI†"}
    series = ["E1 random", "E2 grouped", "E3 temporal", "E4 cross-dataset"]
    fig, axes = plt.subplots(2, 1, figsize=(W, 3.6), sharex=True)
    for ax, metric, label in zip(axes, ("pr_auc", "macro_f1"), ("PR-AUC", "Macro-F1")):
        vals, errs = {s: [] for s in series}, {s: [] for s in series}
        for d in names:
            t = within[d]
            for s, e in zip(series[:3], ("E1", "E2", "E3")):
                ok = e in t.index and pd.isna(t.loc[e].get("status", np.nan))
                vals[s].append(t.loc[e, f"{metric}_mean"] if ok else np.nan)
                errs[s].append(t.loc[e, f"{metric}_std"] if ok else np.nan)
            p = e4_pair[d]
            vals[series[3]].append(e4.loc[p, f"{metric}_mean"] if p else np.nan)
            errs[series[3]].append(e4.loc[p, f"{metric}_std"] if p else np.nan)
        bars(ax, list(names.values()), series, vals, [OI["blue"], OI["sky"], OI["orange"], OI["red"]],
             [None, None, "///", "xx"], errs)
        ax.set_ylim(0, 1.05)
        ax.set_ylabel(label)
    axes[0].legend(ncol=2, loc="lower left", bbox_to_anchor=(0, 1.0))
    axes[1].text(1.0, -0.32, "† HIKARI E2/E3: 2-attacker transfer tests. E4 = MTA→MCFP, MCFP→MTA, "
                 "RAID→MTA.\nFeatures G1+G2 without timing; XGBoost; mean ± SD over 5 seeds.",
                 transform=axes[1].transAxes, ha="right", va="top", fontsize=6)
    save(fig, "fig_a_collapse")


# --------------------------------------------------------------------------- (b) E8 tiers
def fig_tiers() -> None:
    tiers = ["tier_tls12_full", "tier_tls13", "tier_tls13_ech"]
    labels = ["Full (TLS 1.2 view)", "TLS 1.3 (no cert.)", "TLS 1.3 + ECH (G1/G2)"]
    groups, vals = [], {l: [] for l in labels}
    for ds, exp, name in (("mta", "E2", "MTA\nE2"), ("mta", "E3", "MTA\nE3"), ("mcfp", "E2", "MCFP\nE2")):
        s = pd.read_csv(B / f"e8_{ds}" / "summary.csv").query("experiment == @exp").set_index("feature_set")
        groups.append(name)
        for t, l in zip(tiers, labels):
            vals[l].append(s.loc[t, "pr_auc_mean"])
    v = pd.read_csv(B / "e8_mta" / "results_per_tls_version.csv").query("experiment == 'E3'")
    v["tls_version"] = v["tls_version"].astype(str)
    for ver, name in (("1.2", "MTA E3\nTLS 1.2\nflows"), ("1.3", "MTA E3\nTLS 1.3\nflows")):
        groups.append(name)
        m = v[v.tls_version == ver].groupby("feature_set")["pr_auc"].mean()
        for t, l in zip(tiers, labels):
            vals[l].append(m[t])
    fig, ax = plt.subplots(figsize=(W, 2.2))
    bars(ax, groups, labels, vals, [OI["blue"], OI["green"], OI["orange"]], [None, "..", "///"])
    ax.set_ylim(0.5, 1.02)
    ax.set_ylabel("PR-AUC")
    ax.axvline(2.5, color=OI["grey"], lw=0.6, ls=":")
    ax.legend(ncol=2, loc="lower left", bbox_to_anchor=(0, 1.0), columnspacing=0.8, handlelength=1.2)
    save(fig, "fig_b_tiers")


# --------------------------------------------------------------------------- (c) fingerprints
def fig_fingerprints() -> None:
    e9 = pd.read_csv(B / "e9" / "summary.csv").set_index(["scenario", "feature_set"])
    sets = ["no_fp", "fp_ja3", "fp_ja4", "fp_both"]
    labels = ["No fingerprint", "+JA3/JA3S", "+JA4/JA4S", "+both"]
    scen = {"mta_old>mta_new": "MTA ≤2022\n→ 2023–26", "mcfp>mta_new": "MCFP\n→ MTA 2023–26"}
    cf = sorted(B.glob("cf_e9_*/summary.csv"))
    fig, axes = plt.subplots(1, 2 if cf else 1, figsize=(W if cf else W * 0.6, 2.2), squeeze=False,
                             gridspec_kw={"width_ratios": [1, 1.3] if cf else [1]})
    ax = axes[0, 0]
    vals = {l: [e9.loc[(s, f), "pr_auc_mean"] for s in scen] for f, l in zip(sets, labels)}
    errs = {l: [e9.loc[(s, f), "pr_auc_std"] for s in scen] for f, l in zip(sets, labels)}
    bars(ax, list(scen.values()), labels, vals, [OI["green"], OI["orange"], OI["purple"], OI["red"]],
         [None, "///", "\\\\\\", "xx"], errs)
    ax.set_ylim(0.5, 1.0)
    ax.set_ylabel("PR-AUC")
    ax.set_title("XGBoost (E9)")
    ax.legend(ncol=2, loc="lower left", bbox_to_anchor=(0, 1.08), columnspacing=0.8, handlelength=1.2)
    if cf:  # cross-family check (batch 4): no fingerprints vs JA3+JA4, MTA <=2022 -> 2023-26
        ax = axes[0, 1]
        fam = {"xgb": e9.xs("mta_old>mta_new")}
        for p in cf:
            fam[p.parent.name.split("_")[-1]] = pd.read_csv(p).set_index(["scenario", "feature_set"]).xs(
                "mta_old>mta_new")
        names = {"xgb": "XGB", "lgbm": "LGBM", "rf": "RF", "lr": "LR"}
        order = [k for k in names if k in fam]
        vals = {l: [fam[k].loc[f, "pr_auc_mean"] for k in order] for f, l in (("no_fp", "No fingerprint"),
                                                                              ("fp_both", "+both"))}
        bars(ax, [names[k] for k in order], list(vals), vals, [OI["green"], OI["red"]], [None, "xx"])
        ax.set_ylim(0.5, 1.0)
        ax.set_title("All families, MTA ≤2022 → 2023–26")
    save(fig, "fig_c_fingerprints")


# --------------------------------------------------------------------------- (d) E6 early detection
def fig_early() -> None:
    fig, ax = plt.subplots(figsize=(W, 2.2))
    ns = [3, 5, 10, 20]
    style = {("mta", "E2"): (OI["blue"], "o", "MTA E2"), ("mta", "E3"): (OI["orange"], "s", "MTA E3"),
             ("mcfp", "E2"): (OI["green"], "^", "MCFP E2")}
    for (ds, exp), (c, mk, name) in style.items():
        s = pd.read_csv(B / f"e6_{ds}" / "summary.csv").query("experiment == @exp").set_index("feature_set")
        for suffix, ls, fill in (("", "-", c), ("_notime", "--", "white")):
            y = [s.loc[f"early_{n}{suffix}", "pr_auc_mean"] if f"early_{n}{suffix}" in s.index else np.nan
                 for n in ns]
            ax.plot(ns, y, ls=ls, color=c, marker=mk, mfc=fill, ms=4, lw=1,
                    label=f"{name}{'' if not suffix else ', no timing'}")
            full = f"all{suffix}"
            if full in s.index:
                ax.axhline(s.loc[full, "pr_auc_mean"], color=c, ls=ls, lw=0.5, alpha=0.5)
    ax.set_xscale("log")
    ax.set_xticks(ns)
    ax.set_xticklabels([str(n) for n in ns])
    ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.set_xlabel("Packets observed per flow (N)")
    ax.set_ylabel("PR-AUC")
    ax.set_ylim(0.2, 1.02)
    ax.axvspan(2.6, 3.6, color=OI["grey"], alpha=0.15, lw=0)
    ax.text(3.0, 0.42, "N=3:\nartefact", ha="center", va="bottom", fontsize=5.5, color="#555555")
    ax.legend(ncol=2, loc="lower left", bbox_to_anchor=(0, 1.0), handlelength=2.2, columnspacing=0.8)
    ax.text(0, -0.3, "Thin lines: whole-flow features, all groups (dashed: no timing). XGBoost, 5 seeds.",
            transform=ax.transAxes, fontsize=6)
    save(fig, "fig_d_early")


# --------------------------------------------------------------------------- (e) origin probe
def fig_origin() -> None:
    c = pd.read_csv(B / "e5b" / "origin_probe_confusion_seed0.csv")
    c = c.query("feature_set == 'g1g2_notime' and split == 'grouped'").set_index("true")
    cls = ["RAID Tranco", "HIKARI benign", "CTU-Normal", "MTA background"]
    short = ["RAID", "HIKARI", "MCFP\n(CTU-Normal)", "MTA bg"]
    m = c.loc[cls, cls].astype(float).fillna(0).to_numpy()
    m = m / m.sum(axis=1, keepdims=True)
    fig, ax = plt.subplots(figsize=(W * 0.75, W * 0.65))
    im = ax.imshow(m, cmap="cividis", vmin=0, vmax=1)
    for i in range(4):
        for j in range(4):
            ax.text(j, i, f"{m[i, j]:.2f}", ha="center", va="center", fontsize=7,
                    color="black" if m[i, j] > 0.5 else "white")
    ax.set_xticks(range(4))
    ax.set_xticklabels(short, fontsize=6.5)
    ax.set_yticks(range(4))
    ax.set_yticklabels(short, fontsize=6.5)
    ax.set_xlabel("Predicted source dataset")
    ax.set_ylabel("True source (benign flows only)")
    ax.spines[:].set_visible(True)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03, label="Row fraction")
    save(fig, "fig_e_origin_probe")


if __name__ == "__main__":
    fig_collapse()
    fig_tiers()
    fig_fingerprints()
    fig_early()
    fig_origin()
