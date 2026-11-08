"""Regenerate every paper figure, and figures/CAPTIONS.md, from the committed benchmark CSVs.

Usage: python review/benchmark/figures/make_figures.py
Writes fig_*.pdf (vector, TrueType fonts embedded) and fig_*.png (300 dpi previews) next to this script.
Drawn at final print size for the manuscript (elsarticle preprint, 12 pt, text width 390 pt = 5.39 in;
figures are included at natural size, never scaled): full text width, Times (first available of the
FONTS list, never DejaVu), labels and titles 10 pt, everything else 9 pt, lines >= 1 pt. Okabe-Ito
colours (colour-blind safe), with hatching, marker shape or line style so conditions can also be told
apart in greyscale. Captions carry each figure's metric and test prevalence, computed from the same
CSVs, so they stay in sync with the plots.
"""
from pathlib import Path

import matplotlib
import matplotlib.font_manager as fm
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

B = Path(__file__).resolve().parent.parent  # review/benchmark
OUT = Path(__file__).resolve().parent
W = 5.39  # manuscript text width, inches (390 pt = 137 mm)
FONTS = ["Times New Roman", "Nimbus Roman", "TeX Gyre Termes", "Times"]
_have = {f.name for f in fm.fontManager.ttflist}
FONT = next((f for f in FONTS if f in _have), None)
if FONT is None:  # never fall back to DejaVu silently
    raise SystemExit(f"none of {FONTS} is installed; install one before rendering the figures")
LBL, SMALL = 10, 9  # axis labels / titles; ticks, legends, annotations
OI = {"orange": "#E69F00", "sky": "#56B4E9", "green": "#009E73", "yellow": "#F0E442", "blue": "#0072B2",
      "red": "#D55E00", "purple": "#CC79A7", "black": "#000000", "grey": "#999999"}
plt.rcParams.update({"font.family": "serif", "font.serif": [FONT], "mathtext.fontset": "stix",
                     "font.size": SMALL, "axes.titlesize": LBL, "axes.labelsize": LBL, "legend.fontsize": SMALL,
                     "xtick.labelsize": SMALL, "ytick.labelsize": SMALL, "pdf.fonttype": 42, "ps.fonttype": 42,
                     "lines.linewidth": 1.2, "axes.linewidth": 0.8, "hatch.linewidth": 1.0,
                     "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False})
CAPTIONS = {}


def save(fig, name: str) -> None:
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight", pad_inches=0.02)
    fig.savefig(OUT / f"{name}.png", dpi=300, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    print("wrote", name)


def seeds(folder: str, query: str) -> pd.DataFrame:
    d = pd.read_csv(B / folder / "results_per_seed.csv").query(query)
    return d[d["status"].isna() | (d["status"] == "ok")] if "status" in d else d


def stat(d: pd.DataFrame, metric: str = "pr_auc") -> dict:
    """Mean over seeds, SD, mean of the per-seed bootstrap CI bounds, mean test prevalence."""
    out = {"mean": d[metric].mean(), "sd": d[metric].std(), "prev": (d["n_pos"] / d["n"]).mean()}
    ci = d.get(f"{metric}_ci")
    if ci is not None and ci.notna().any():
        p = ci.dropna().str.split("-")
        out["lo"], out["hi"] = p.str[0].astype(float).mean(), p.str[1].astype(float).mean()
    else:
        out["lo"], out["hi"] = out["mean"] - out["sd"], out["mean"] + out["sd"]
    return out


def pct(x: float) -> str:
    return f"{100 * x:.0f}%"


def dots(ax, groups, conds, cell, colours, markers, span=0.7):
    """Dot-and-CI plot: cell(group, cond) -> stat dict or None; one marker per condition, offset in-group."""
    k = len(conds)
    for i, c in enumerate(conds):
        off = -span / 2 + (i + 0.5) * span / k
        for g, grp in enumerate(groups):
            s = cell(grp, c)
            if s is None:
                continue
            # CI bounds are rounded to 4 decimals in the CSVs, so at PR-AUC ~1 they can sit a hair inside the mean
            err = [[max(s["mean"] - s["lo"], 0)], [max(s["hi"] - s["mean"], 0)]]
            ax.errorbar(g + off, s["mean"], yerr=err, fmt=markers[i],
                        color=colours[i], ms=5.5, mfc=colours[i] if i == 0 else "white", mew=1.2, elinewidth=1.0,
                        capsize=2, label=c if g == 0 else None, zorder=3)
    ax.set_xticks(range(len(groups)))
    ax.set_xlim(-0.6, len(groups) - 0.4)
    ax.grid(axis="y", lw=0.5, color="#dddddd", zorder=0)


# --------------------------------------------------------------------------- (a) collapse
def fig_collapse() -> None:
    fs = "g1g2_notime"  # the only feature set available for every dataset and every protocol
    ds = {"mta": ("MTA", "mta>mcfp", "→MCFP"), "mcfp": ("MCFP", "mcfp>mta", "→MTA"),
          "raid": ("RAID", "raid>mta", "→MTA"), "hikari": ("HIKARI", None, " none")}
    exps = ["E1 random", "E2 grouped", "E3 temporal", "E4 cross-dataset"]
    cols = [OI["blue"], OI["sky"], OI["orange"], OI["red"]]
    hatch = [None, None, "///", "xx"]
    cells = {}
    for d, (_, pair, _) in ds.items():
        for e, name in zip(("E1", "E2", "E3"), exps):
            r = seeds(d, f"feature_set == '{fs}' and experiment == '{e}'")
            cells[(d, name)] = (stat(r), stat(r, "macro_f1")) if len(r) else None
        r = seeds("e4", f"pair == '{pair}' and feature_set == '{fs}'") if pair else []
        cells[(d, exps[3])] = (stat(r), stat(r, "macro_f1")) if len(r) else None
    fig, axes = plt.subplots(2, 1, figsize=(W, 4.3), sharex=True)
    width = 0.8 / len(exps)
    for row, (ax, label) in enumerate(zip(axes, ("PR-AUC", "Macro-F1"))):
        for g, d in enumerate(ds):
            for i, e in enumerate(exps):
                x = g - 0.4 + (i + 0.5) * width
                c = cells[(d, e)]
                if c is None:
                    ax.text(x, 0.02, "n/a", rotation=90, ha="center", va="bottom", fontsize=SMALL, color="#555555")
                    continue
                s = c[row]
                transfer = d == "hikari" and e in exps[1:3]  # 2-attacker transfer tests: outlined, daggered
                ax.bar(x, s["mean"], width, yerr=s["sd"], error_kw={"elinewidth": 1.0, "capsize": 2},
                       color="white" if transfer else cols[i], edgecolor=cols[i] if transfer else "white",
                       linewidth=1.2 if transfer else 0.5, hatch=hatch[i] if not transfer else "....",
                       label=e if (row == 0 and g == 0) else None)
                if transfer:
                    ax.text(x, s["mean"] + s["sd"] + 0.02, "†", ha="center", va="bottom", fontsize=SMALL)
                if row == 0:  # no-skill PR-AUC = test prevalence
                    ax.plot([x - width / 2, x + width / 2], [s["prev"]] * 2, color="black", lw=1.5,
                            label="No-skill (test prevalence)" if (g == 0 and i == 0) else None, zorder=4)
        ax.set_ylim(0, 1.08)
        ax.set_ylabel(label)
    axes[1].set_xticks(range(len(ds)))
    axes[1].set_xticklabels([f"{n}\n(E4{e4})" for n, _, e4 in ds.values()])
    axes[0].legend(ncol=3, loc="lower left", bbox_to_anchor=(0, 1.0), columnspacing=1.0, handlelength=1.6)
    save(fig, "fig_a_collapse")

    rows = []
    for d, (n, _, e4) in ds.items():
        prevs = [f"{e.split()[0]} {pct(cells[(d, e)][0]['prev'])}" for e in exps if cells[(d, e)]]
        rows.append(f"{n}: " + ", ".join(prevs))
    CAPTIONS["fig_a_collapse"] = (
        "**Performance collapse beyond random splits.** XGBoost, features G1+G2 without timing (the only set "
        "available for every dataset and protocol); bars are the mean over 5 seeds, whiskers ± 1 SD. "
        "Top: PR-AUC; the black tick on each bar is that test set's no-skill PR-AUC (the malicious share), "
        "because PR-AUC is not comparable across test sets with different prevalence. Bottom: macro-F1 at the "
        "validation-selected max-F1 threshold. E1 random split; E2 grouped by infection case (MTA), capture "
        "(MCFP, RAID) or client host (HIKARI); E3 trained on older years, tested on newer (infeasible for MCFP "
        "and RAID, where year and class coincide); E4 trained on the group's dataset and tested on the dataset "
        "named under it (MTA→MCFP, MCFP→MTA, RAID→MTA; HIKARI has no same-concept partner). † HIKARI E2 and E3 (outlined bars) are 2-attacker transfer tests (one attacker "
        "IP in training, the other in test), not grouped-generalisation estimates. Test malicious share: "
        + "; ".join(rows) + ".")


# --------------------------------------------------------------------------- (b) E8 tiers
def fig_tiers() -> None:
    tiers = ["tier_tls12_full", "tier_tls13", "tier_tls13_ech"]
    labels = ["Full (TLS 1.2 view)", "TLS 1.3 (no certificate)", "TLS 1.3 + ECH (G1/G2 only)"]
    groups = [("mta", "E2", None, "MTA\nE2"), ("mta", "E3", None, "MTA\nE3"), ("mcfp", "E2", None, "MCFP\nE2"),
              ("mta", "E3", "1.2", "MTA E3\nTLS 1.2\nflows"), ("mta", "E3", "1.3", "MTA E3\nTLS 1.3\nflows")]
    ver = pd.read_csv(B / "e8_mta" / "results_per_tls_version.csv").query("experiment == 'E3'")
    ver["tls_version"] = ver["tls_version"].astype(str)

    def cell(g, c):
        dset, exp, v, _ = g
        t = tiers[labels.index(c)]
        if v is None:
            return stat(seeds(f"e8_{dset}", f"feature_set == '{t}' and experiment == '{exp}'"))
        return stat(ver[(ver.tls_version == v) & (ver.feature_set == t)])  # no per-version CI: ± 1 SD
    fig, ax = plt.subplots(figsize=(W, 2.9))
    dots(ax, groups, labels, cell, [OI["blue"], OI["green"], OI["orange"]], ["o", "s", "^"])
    ax.set_xticklabels([g[3] for g in groups])
    ax.axvline(2.5, color=OI["grey"], lw=1.0, ls=":")
    ax.set_ylabel("PR-AUC")
    ax.legend(ncol=2, loc="lower left", bbox_to_anchor=(0, 1.0), columnspacing=1.0, handlelength=1.2)
    save(fig, "fig_b_tiers")

    prev = {g[3].replace("\n", " "): pct(cell(g, labels[0])["prev"]) for g in groups}
    CAPTIONS["fig_b_tiers"] = (
        "**Accuracy by TLS visibility tier.** XGBoost, 5 seeds. Tiers are simulated by masking feature groups on "
        "the same flows: full = G1–G5; TLS 1.3 = without the certificate group (G4); TLS 1.3 + ECH = flow "
        "statistics and packet sizes/directions/timing only (G1, G2). Points are mean PR-AUC; whiskers are the "
        "mean 95% bootstrap CI for the three left groups and ± 1 SD over seeds for the per-TLS-version "
        "groups (right of the dotted line; the flows of the MTA E3 test set split by the TLS version actually "
        "negotiated). The y-axis does not start at 0. Test malicious share: "
        + "; ".join(f"{k} {v}" for k, v in prev.items()) + ".")


# --------------------------------------------------------------------------- (c) fingerprints
def fig_fingerprints() -> None:
    sets = ["no_fp", "fp_ja3", "fp_ja4", "fp_both"]
    labels = ["No fingerprint (G1–G4)", "+JA3/JA3S", "+JA4/JA4S", "+both"]
    cols = [OI["green"], OI["orange"], OI["purple"], OI["red"]]
    marks = ["o", "s", "D", "^"]
    scen = {"mta_old>mta_new": "MTA ≤2022 → 2023–26", "mcfp>mta_new": "MCFP → MTA 2023–26"}
    fams = {"xgb": ("e9", "XGB"), "lgbm": ("cf_e9_lgbm", "LGBM"), "rf": ("cf_e9_rf", "RF"), "lr": ("cf_e9_lr", "LR")}
    fams = {k: v for k, v in fams.items() if (B / v[0] / "results_per_seed.csv").exists()}

    def cell_for(folder):
        return lambda sc, lab: stat(seeds(folder, f"scenario == '{sc}' and feature_set == '{sets[labels.index(lab)]}'"))
    fig = plt.figure(figsize=(W, 4.5 if len(fams) > 1 else 2.6))
    gs = fig.add_gridspec(2 if len(fams) > 1 else 1, 2, hspace=0.55, wspace=0.1)
    ax = fig.add_subplot(gs[0, :])
    dots(ax, list(scen), labels, cell_for("e9"), cols, marks)
    ax.set_xticklabels(list(scen.values()))
    ax.set_ylabel("PR-AUC")
    ax.set_title("XGBoost, E9", loc="left")
    ax.legend(ncol=4, loc="lower left", bbox_to_anchor=(0, 1.1), columnspacing=0.9, handlelength=1.0,
              handletextpad=0.3)
    if len(fams) > 1:  # cross-family check (batch 4): no fingerprint vs +both, per scenario
        axes = [fig.add_subplot(gs[1, i]) for i in range(2)]
        for ax, (sc, title) in zip(axes, scen.items()):
            dots(ax, list(fams), [labels[0], labels[3]],
                 lambda f, lab, sc=sc: stat(seeds(fams[f][0], f"scenario == '{sc}' and "
                                                               f"feature_set == '{sets[labels.index(lab)]}'")),
                 [cols[0], cols[3]], [marks[0], marks[3]])
            ax.set_xticklabels([v[1] for v in fams.values()])
            ax.set_title(title, loc="left")
        lo = min(a.get_ylim()[0] for a in axes)
        hi = max(a.get_ylim()[1] for a in axes) + 0.02  # room for markers at the top
        for i, a in enumerate(axes):
            a.set_ylim(lo, hi)
            if i:
                a.set_yticklabels([])
        axes[0].set_ylabel("PR-AUC")
    save(fig, "fig_c_fingerprints")

    prev = {v: pct(stat(seeds("e9", f"scenario == '{k}' and feature_set == 'no_fp'"))["prev"]) for k, v in scen.items()}
    CAPTIONS["fig_c_fingerprints"] = (
        "**Fingerprints under drift.** Top: XGBoost on G1–G4 with no fingerprint, or with JA3/JA3S, "
        "JA4/JA4S or both added (E9). Bottom: every tabular model family, no fingerprint vs both. Training on "
        "MTA ≤2022 (left) or on MCFP (right); test is always MTA 2023–26. Points are mean PR-AUC over "
        "5 seeds; whiskers are the mean 95% test-set bootstrap CI, which does not include seed-to-seed variation "
        "(SD up to 0.06 for XGBoost and LightGBM on MCFP → MTA; see SUMMARY_crossfamily.md). The y-axis does "
        "not start at 0. Test malicious share: "
        + "; ".join(f"{k} {v}" for k, v in prev.items())
        + " (the same test flows in both scenarios). "
        "About half of the test flows carry a JA3 or JA4 value never seen in MTA training (53% / 52%).")


# --------------------------------------------------------------------------- (d) E6 early detection
def fig_early() -> None:
    fig, ax = plt.subplots(figsize=(W, 3.0))
    ns = [3, 5, 10, 20]
    style = {("mta", "E2"): (OI["blue"], "o", "MTA E2"), ("mta", "E3"): (OI["orange"], "s", "MTA E3"),
             ("mcfp", "E2"): (OI["green"], "^", "MCFP E2")}
    prevs = []
    for (ds, exp), (c, mk, name) in style.items():
        s = pd.read_csv(B / f"e6_{ds}" / "summary.csv").query("experiment == @exp").set_index("feature_set")
        for suffix, ls, fill in (("", "-", c), ("_notime", "--", "white")):
            y = [s.loc[f"early_{n}{suffix}", "pr_auc_mean"] if f"early_{n}{suffix}" in s.index else np.nan
                 for n in ns]
            ax.plot(ns, y, ls=ls, color=c, marker=mk, mfc=fill, ms=5.5, mew=1.2, lw=1.4,
                    label=f"{name}{'' if not suffix else ', no timing'}")
            full = f"all{suffix}"
            if full in s.index:
                ax.axhline(s.loc[full, "pr_auc_mean"], color=c, ls=ls, lw=1.0, alpha=0.45)
        r = seeds(f"e6_{ds}", f"experiment == '{exp}' and feature_set.str.startswith('early_') and "
                              f"feature_set != 'early_3' and feature_set != 'early_3_notime'", )
        p = r["n_pos"] / r["n"]
        prevs.append(f"{name} {pct(p.min())}–{pct(p.max())}")
    ax.set_xscale("log")
    ax.set_xticks(ns)
    ax.set_xticklabels([str(n) for n in ns])
    ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.set_xlabel("Packets observed per flow (N)")
    ax.set_ylabel("PR-AUC")
    ax.set_ylim(0.2, 1.02)
    ax.axvspan(2.6, 3.6, color=OI["grey"], alpha=0.15, lw=0)
    ax.text(3.0, 0.42, "N=3:\nartefact", ha="center", va="bottom", fontsize=SMALL, color="#444444")
    ax.legend(ncol=3, loc="lower left", bbox_to_anchor=(0, 1.0), handlelength=2.4, columnspacing=1.0)
    save(fig, "fig_d_early")
    CAPTIONS["fig_d_early"] = (
        "**Early detection.** XGBoost on the features visible after the first N packets of a flow (E6), mean "
        "PR-AUC over 5 seeds; solid = with timing, dashed/hollow = without. Thin horizontal lines: whole-flow "
        "features, all groups (dashed: without timing). The y-axis does not start at 0. N = 3 (shaded) covers "
        "only the TCP handshake; per-feature-set deduplication removes 87–99.8% of flows there, so those "
        "points describe an unrepresentative residue, not detection. Test malicious share for N ≥ 5 "
        "(varies with deduplication): " + "; ".join(prevs) + ".")


# --------------------------------------------------------------------------- (e) origin probe
def fig_origin() -> None:
    c = pd.read_csv(B / "e5b" / "origin_probe_confusion_seed0.csv")
    c = c.query("feature_set == 'g1g2_notime' and split == 'grouped'").set_index("true")
    cls = ["RAID Tranco", "HIKARI benign", "CTU-Normal", "MTA background"]
    short = ["RAID", "HIKARI", "MCFP\n(CTU-Normal)", "MTA bg"]
    m = c.loc[cls, cls].astype(float).fillna(0).to_numpy()
    n = m.sum(axis=1)
    m = m / n[:, None]
    fig, ax = plt.subplots(figsize=(4.4, 3.6))
    im = ax.imshow(m, cmap="cividis", vmin=0, vmax=1)
    for i in range(4):
        for j in range(4):
            ax.text(j, i, f"{m[i, j]:.2f}", ha="center", va="center", fontsize=SMALL,
                    color="black" if m[i, j] > 0.5 else "white")
    ax.set_xticks(range(4))
    ax.set_xticklabels(short)
    ax.set_yticks(range(4))
    ax.set_yticklabels(short)
    ax.set_xlabel("Predicted source dataset")
    ax.set_ylabel("True source (benign flows only)")
    ax.spines[:].set_visible(True)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03, label="Row fraction")
    save(fig, "fig_e_origin_probe")
    s = pd.read_csv(B / "e5b" / "origin_probe_summary.csv").query(
        "feature_set == 'g1g2_notime' and split == 'grouped'").iloc[0]
    CAPTIONS["fig_e_origin_probe"] = (
        "**Dataset-of-origin probe.** An XGBoost classifier trained to tell which dataset a *benign* flow comes "
        "from, using G1+G2 without timing, with a split grouped by capture/host (seed 0). Cells are row-normalised "
        f"(test flows per true source: {', '.join(f'{a} {int(b):,}' for a, b in zip(short, n)).replace(chr(10), ' ')}). "
        f"Metric: balanced accuracy {s['balanced_accuracy_mean']:.3f} ± {s['balanced_accuracy_std']:.3f} over "
        f"5 seeds, against a chance level of {s['chance_mean']:.2f} (4 classes). Any benchmark that mixes "
        "benign and malicious traffic from different sources can be separated by environment alone.")


# --------------------------------------------------------------------------- (f) rolling-origin drift
def fig_rolling() -> None:
    p = B / "b6_rolling" / "summary.csv"
    if not p.exists():
        return
    s = pd.read_csv(p)
    fig, axes = plt.subplots(2, 1, figsize=(W, 4.3), sharex=True, gridspec_kw={"height_ratios": [2.2, 1]})
    style = {("all", "expanding"): (OI["red"], "-", "^", "G1–G5, all past years"),
             ("all", "2y"): (OI["red"], "--", "^", "G1–G5, last 2 years"),
             ("loo_g5", "expanding"): (OI["green"], "-", "o", "No fingerprints, all past years"),
             ("loo_g5", "2y"): (OI["green"], "--", "o", "No fingerprints, last 2 years")}
    for (fs, win), (c, ls, mk, lab) in style.items():
        d = s[(s.feature_set == fs) & (s.window == win)].sort_values("test_year")
        axes[0].errorbar(d.test_year, d.pr_auc_mean, yerr=d.pr_auc_std, color=c, ls=ls, marker=mk, ms=5.5,
                         mfc=c if ls == "-" else "white", mew=1.2, lw=1.4, elinewidth=1.0, capsize=2, label=lab)
    d = s[(s.feature_set == "all") & (s.window == "expanding")].sort_values("test_year")
    prev = d.n_pos_mean / d.n_mean
    axes[0].plot(d.test_year, prev, ls="none", marker="_", ms=11, mew=1.8, color="black", label="No-skill (prevalence)")
    axes[0].set_ylabel("PR-AUC")
    axes[0].set_ylim(0, 1.04)
    axes[0].legend(ncol=2, loc="lower left", bbox_to_anchor=(0, 1.0), columnspacing=1.0, handlelength=2.4)
    axes[0].grid(axis="y", lw=0.5, color="#dddddd")
    for fs, c, mk in (("all", OI["red"], "^"), ("loo_g5", OI["green"], "o")):
        d = s[(s.feature_set == fs) & (s.window == "expanding")].sort_values("test_year")
        axes[1].plot(d.test_year, d.roc_auc_mean, color=c, marker=mk, ms=5.5, lw=1.4)
    axes[1].axhline(0.5, color=OI["grey"], lw=1.0, ls=":")
    axes[1].set_ylabel("ROC-AUC\n(all past years)")
    axes[1].set_ylim(0.3, 1.02)
    axes[1].set_xlabel("Test year (trained on earlier years only)")
    axes[1].set_xticks(sorted(s.test_year.unique()))
    save(fig, "fig_f_rolling")
    n = s[(s.feature_set == "all") & (s.window == "expanding")].sort_values("test_year")
    CAPTIONS["fig_f_rolling"] = (
        "**Year-by-year drift on MTA (rolling origin).** For each test year Y, XGBoost is trained on MTA traffic "
        "from earlier years only: all years up to Y−1 (solid) or the last two years (dashed). Validation is the "
        "latest 15% of the training period. Red: all feature groups; green: without the JA3/JA4 fingerprint group "
        "(G5). Points are mean PR-AUC over 5 seeds, whiskers ± 1 SD; the black dash is each test year's no-skill "
        "level. The lower panel shows ROC-AUC (all past years), which does not depend on prevalence; the dotted "
        "line is chance. 2020 is trained on 2019 only (1,398 rows); 2024 and 2025 have small test sets. Test "
        "flows (malicious share): " + "; ".join(f"{int(r.test_year)} {int(r.n_mean):,} ({pct(r.n_pos_mean / r.n_mean)})"
                                                for r in n.itertuples()) + ".")


def write_captions() -> None:
    text = ["# Figure captions", "",
            "Generated by `make_figures.py` from the committed CSVs, so the numbers match the plots. "
            "Copy into the paper as-is; every caption names the metric and the test malicious share.", ""]
    for k, v in CAPTIONS.items():
        text += [f"## {k}", "", v, ""]
    (OUT / "CAPTIONS.md").write_text("\n".join(text), encoding="utf-8")
    print("wrote CAPTIONS.md")


if __name__ == "__main__":
    fig_collapse()
    fig_tiers()
    fig_fingerprints()
    fig_early()
    fig_origin()
    fig_rolling()
    write_captions()
