"""Regenerate every paper figure, and figures/CAPTIONS.md, from the committed benchmark CSVs.

Usage: python review/benchmark/figures/make_figures.py
Writes fig_*.pdf (vector, TrueType fonts embedded) and fig_*.png (300 dpi previews) next to this script.
Drawn at final print size for the two-column Elsevier layout (figures are included at natural size, never
scaled): one column = 3.50 in (252 pt), full width = 7.25 in (522 pt). Style, colours and helpers come from
the shared manuscript module palette.py (Times, 8 pt text, 8.5 pt panel labels centred below each panel,
one shared legend above the panels). Colours are colour-blind safe, with hatching, marker shape or line
style so conditions can also be told apart in greyscale. Captions carry each figure's metric and test
prevalence, computed from the same CSVs, so they stay in sync with the plots.
"""
import sys
from pathlib import Path

import matplotlib
import matplotlib.font_manager as fm
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

sys.path.insert(0, r"D:\new papers\manuscript\figures\src")
from palette import (AMBER, BLUE, BLUE_L, COL, FULL, GREY, INK, PLUM, ROSE, TEAL,  # noqa: E402
                     apply_style, fig_legend, panel_label, save as pal_save)

B = Path(__file__).resolve().parent.parent  # review/benchmark
OUT = Path(__file__).resolve().parent
FONTS = ["Times New Roman", "Nimbus Roman", "TeX Gyre Termes", "Times"]
_have = {f.name for f in fm.fontManager.ttflist}
if not any(f in _have for f in FONTS):  # never fall back to DejaVu silently
    raise SystemExit(f"none of {FONTS} is installed; install one before rendering the figures")
apply_style()
SMALL = 8
MS, MEW, LW = 4.5, 1.0, 1.2  # marker size / edge width, line width
CAPTIONS = {}


def fit_width(fig, target: float, margin: float = 0.035) -> None:
    """Move the subplot edges so the tight bbox spans the target width (inches) minus a small margin."""
    fig.set_figwidth(target)
    for _ in range(5):
        fig.canvas.draw()
        bb = fig.get_tightbbox(fig.canvas.get_renderer())
        sp = fig.subplotpars
        dl, dr = (bb.x0 - margin) / target, (target - margin - bb.x1) / target
        if abs(dl) < 1e-3 and abs(dr) < 1e-3:
            break
        fig.subplots_adjust(left=sp.left - dl, right=sp.right + dr)


def labels_below(fig, axes, texts, gap_pt: float = 3.0) -> None:
    """panel_label() for each axis, on one common line just under the lowest tick labels / x label."""
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    y_disp = min(ax.xaxis.get_tightbbox(r).y0 for ax in axes) - gap_pt * fig.dpi / 72
    for ax, text in zip(axes, texts):
        panel_label(ax, text, y=ax.transAxes.inverted().transform((0, y_disp))[1])


def save(fig, name: str) -> None:
    pal_save(fig, OUT / f"{name}.pdf")
    fig.savefig(OUT / f"{name}.png", dpi=300, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


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
                        color=colours[i], ms=MS, mfc=colours[i] if i == 0 else "white", mew=MEW, elinewidth=0.9,
                        capsize=1.8, label=c if g == 0 else None, zorder=3)
    ax.set_xticks(range(len(groups)))
    ax.set_xlim(-0.6, len(groups) - 0.4)
    ax.grid(axis="x", visible=False)


# --------------------------------------------------------------------------- (a) collapse
def fig_collapse() -> None:
    fs = "g1g2_notime"  # the only feature set available for every dataset and every protocol
    ds = {"mta": ("MTA", "mta>mcfp", "→MCFP"), "mcfp": ("MCFP", "mcfp>mta", "→MTA"),
          "raid": ("RAID", "raid>mta", "→MTA"), "hikari": ("HIKARI", None, " none")}
    exps = ["E1 random", "E2 grouped", "E3 temporal", "E4 cross-dataset"]
    cols = [BLUE, TEAL, AMBER, ROSE]
    hatch = [None, None, "///", "xx"]
    cells = {}
    for d, (_, pair, _) in ds.items():
        for e, name in zip(("E1", "E2", "E3"), exps):
            r = seeds(d, f"feature_set == '{fs}' and experiment == '{e}'")
            cells[(d, name)] = (stat(r), stat(r, "macro_f1")) if len(r) else None
        r = seeds("e4", f"pair == '{pair}' and feature_set == '{fs}'") if pair else []
        cells[(d, exps[3])] = (stat(r), stat(r, "macro_f1")) if len(r) else None
    fig, axes = plt.subplots(1, 2, figsize=(FULL, 2.15), sharey=True)
    fig.subplots_adjust(top=0.97, bottom=0.2, wspace=0.06)
    width = 0.8 / len(exps)
    for row, (ax, label) in enumerate(zip(axes, ("PR-AUC", "Macro-F1"))):
        for g, d in enumerate(ds):
            for i, e in enumerate(exps):
                x = g - 0.4 + (i + 0.5) * width
                c = cells[(d, e)]
                if c is None:
                    ax.text(x, 0.02, "n/a", rotation=90, ha="center", va="bottom", fontsize=SMALL, color=INK)
                    continue
                s = c[row]
                transfer = d == "hikari" and e in exps[1:3]  # 2-attacker transfer tests: outlined, daggered
                ax.bar(x, s["mean"], width, yerr=s["sd"], error_kw={"elinewidth": 0.9, "capsize": 1.8, "ecolor": INK},
                       color="white" if transfer else cols[i], edgecolor=cols[i] if transfer else "white",
                       linewidth=1.0 if transfer else 0.4, hatch=hatch[i] if not transfer else "....",
                       label=e if (row == 0 and g == 0) else None)
                if transfer:
                    ax.text(x, s["mean"] + s["sd"] + 0.02, "†", ha="center", va="bottom", fontsize=SMALL)
                if row == 0:  # no-skill PR-AUC = test prevalence
                    ax.plot([x - width / 2, x + width / 2], [s["prev"]] * 2, color=INK, lw=1.4,
                            label="No-skill (test prevalence)" if (g == 0 and i == 0) else None, zorder=4)
        ax.set_ylim(0, 1.08)
        ax.set_ylabel(label)
        ax.set_xticks(range(len(ds)))
        ax.set_xticklabels([f"{n}\n(E4{e4})" for n, _, e4 in ds.values()])
        ax.grid(axis="x", visible=False)
    axes[1].yaxis.set_tick_params(labelleft=False)
    h, lab = axes[0].get_legend_handles_labels()
    fig_legend(fig, h, lab, ncol=5, y=0.985)
    fit_width(fig, FULL)
    labels_below(fig, axes, ("(a) PR-AUC", "(b) Macro-F1"))
    save(fig, "fig_a_collapse")

    rows = []
    for d, (n, _, e4) in ds.items():
        prevs = [f"{e.split()[0]} {pct(cells[(d, e)][0]['prev'])}" for e in exps if cells[(d, e)]]
        rows.append(f"{n}: " + ", ".join(prevs))
    CAPTIONS["fig_a_collapse"] = (
        "**Performance collapse beyond random splits.** XGBoost, features G1+G2 without timing (the only set "
        "available for every dataset and protocol); bars are the mean over 5 seeds, whiskers ± 1 SD. "
        "(a) PR-AUC; the black tick on each bar is that test set's no-skill PR-AUC (the malicious share), "
        "because PR-AUC is not comparable across test sets with different prevalence. (b) Macro-F1 at the "
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
    fig, ax = plt.subplots(figsize=(COL, 2.2))
    fig.subplots_adjust(top=0.97, bottom=0.25)
    dots(ax, groups, labels, cell, [BLUE, TEAL, AMBER], ["o", "s", "^"])
    ax.set_xticklabels([g[3] for g in groups])
    ax.axvline(2.5, color=GREY, lw=0.9, ls=":")
    ax.set_ylabel("PR-AUC")
    h, lab = ax.get_legend_handles_labels()
    fig_legend(fig, h, lab, ncol=2, y=0.985)
    fit_width(fig, COL)
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
    cols = [TEAL, AMBER, PLUM, ROSE]
    marks = ["o", "s", "D", "^"]
    scen = {"mta_old>mta_new": "MTA ≤2022 → 2023–26", "mcfp>mta_new": "MCFP → MTA 2023–26"}
    fams = {"xgb": ("e9", "XGB"), "lgbm": ("cf_e9_lgbm", "LGBM"), "rf": ("cf_e9_rf", "RF"), "lr": ("cf_e9_lr", "LR")}
    fams = {k: v for k, v in fams.items() if (B / v[0] / "results_per_seed.csv").exists()}

    def cell_for(folder):
        return lambda sc, lab: stat(seeds(folder, f"scenario == '{sc}' and feature_set == '{sets[labels.index(lab)]}'"))
    multi = len(fams) > 1
    fig, axs = plt.subplots(1, 3 if multi else 1, figsize=(FULL if multi else COL, 1.95), sharey=True,
                            gridspec_kw={"width_ratios": [2.3, 3, 3]} if multi else None, squeeze=False)
    axs = list(axs[0])
    fig.subplots_adjust(top=0.97, bottom=0.2, wspace=0.07)
    ax = axs[0]
    dots(ax, list(scen), labels, cell_for("e9"), cols, marks, span=0.75)
    ax.set_xticklabels([v.replace(" → ", "\n→ ") for v in scen.values()])
    ax.set_ylabel("PR-AUC")
    if multi:  # cross-family check (batch 4): no fingerprint vs +both, per scenario
        for ax, sc in zip(axs[1:], scen):
            dots(ax, list(fams), [labels[0], labels[3]],
                 lambda f, lab, sc=sc: stat(seeds(fams[f][0], f"scenario == '{sc}' and "
                                                               f"feature_set == '{sets[labels.index(lab)]}'")),
                 [cols[0], cols[3]], [marks[0], marks[3]], span=0.45)
            ax.set_xticklabels([v[1] for v in fams.values()])
            ax.yaxis.set_tick_params(labelleft=False)
        lo, hi = axs[0].get_ylim()
        axs[0].set_ylim(lo, hi + 0.02)  # room for markers at the top
    h, lab = axs[0].get_legend_handles_labels()
    fig_legend(fig, h, lab, ncol=4, y=0.985)
    fit_width(fig, FULL if multi else COL)
    if multi:
        labels_below(fig, axs, ["(a) XGBoost, E9"] + [f"({'bc'[i]}) {v}" for i, v in enumerate(scen.values())])
    save(fig, "fig_c_fingerprints")

    prev = {v: pct(stat(seeds("e9", f"scenario == '{k}' and feature_set == 'no_fp'"))["prev"]) for k, v in scen.items()}
    CAPTIONS["fig_c_fingerprints"] = (
        "**Fingerprints under drift.** (a) XGBoost on G1–G4 with no fingerprint, or with JA3/JA3S, "
        "JA4/JA4S or both added (E9). (b, c) Every tabular model family, no fingerprint vs both. Training on "
        "MTA ≤2022 (left group in (a); (b)) or on MCFP (right group in (a); (c)); test is always MTA 2023–26. "
        "Points are mean PR-AUC over "
        "5 seeds; whiskers are the mean 95% test-set bootstrap CI, which does not include seed-to-seed variation "
        "(SD up to 0.06 for XGBoost and LightGBM on MCFP → MTA; see SUMMARY_crossfamily.md). The y-axis does "
        "not start at 0. Test malicious share: "
        + "; ".join(f"{k} {v}" for k, v in prev.items())
        + " (the same test flows in both scenarios). "
        "About half of the test flows carry a JA3 or JA4 value never seen in MTA training (53% / 52%).")


# --------------------------------------------------------------------------- (d) E6 early detection
def fig_early() -> None:
    fig, ax = plt.subplots(figsize=(COL, 2.3))
    fig.subplots_adjust(top=0.97, bottom=0.17)
    ns = [3, 5, 10, 20]
    style = {("mta", "E2"): (BLUE, "o", "MTA E2"), ("mta", "E3"): (AMBER, "s", "MTA E3"),
             ("mcfp", "E2"): (TEAL, "^", "MCFP E2")}
    prevs = []
    for (ds, exp), (c, mk, name) in style.items():
        s = pd.read_csv(B / f"e6_{ds}" / "summary.csv").query("experiment == @exp").set_index("feature_set")
        for suffix, ls, fill in (("", "-", c), ("_notime", "--", "white")):
            y = [s.loc[f"early_{n}{suffix}", "pr_auc_mean"] if f"early_{n}{suffix}" in s.index else np.nan
                 for n in ns]
            ax.plot(ns, y, ls=ls, color=c, marker=mk, mfc=fill, ms=MS, mew=MEW, lw=LW,
                    label=f"{name}{'' if not suffix else ', no timing'}")
            full = f"all{suffix}"
            if full in s.index:
                ax.axhline(s.loc[full, "pr_auc_mean"], color=c, ls=ls, lw=0.9, alpha=0.5)
        r = seeds(f"e6_{ds}", f"experiment == '{exp}' and feature_set.str.startswith('early_') and "
                              f"feature_set != 'early_3' and feature_set != 'early_3_notime'", )
        p = r["n_pos"] / r["n"]
        prevs.append(f"{name} {pct(p.min())}–{pct(p.max())}")
    ax.set_xscale("log")
    ax.set_xticks(ns)
    ax.set_xticklabels([str(n) for n in ns])
    ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.set_xlabel("Packets observed per flow (N)")
    ax.set_ylabel("PR-AUC")
    ax.set_ylim(0.2, 1.02)
    ax.axvspan(2.6, 3.6, color=GREY, alpha=0.18, lw=0)
    ax.text(2.74, 0.30, "N=3: artefact", rotation=90, ha="center", va="bottom", fontsize=SMALL, color=INK)
    # compact legend for the same six series: colour/marker = condition, line style/fill = timing
    h = [Line2D([], [], color=c, marker=mk, ms=MS, mew=MEW, lw=LW) for c, mk, _ in style.values()]
    lab = [name for _, _, name in style.values()]
    h += [Line2D([], [], color=INK, marker="o", ms=MS, mew=MEW, lw=LW),
          Line2D([], [], color=INK, ls="--", marker="o", mfc="white", ms=MS, mew=MEW, lw=LW)]
    lab += ["With timing", "No timing"]
    order = [0, 3, 1, 4, 2]  # legend fills column-wise: row 1 = conditions, row 2 = timing
    with plt.rc_context({"legend.handlelength": 2.2, "legend.columnspacing": 1.0}):
        fig_legend(fig, [h[i] for i in order], [lab[i] for i in order], ncol=3, y=0.985)
    fit_width(fig, COL)
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
    cmap = LinearSegmentedColormap.from_list("pal_blue", ["#FFFFFF", BLUE_L, BLUE])
    fig, (ax, cax) = plt.subplots(1, 2, figsize=(COL, 2.9), gridspec_kw={"width_ratios": [1, 0.05]})
    fig.subplots_adjust(top=0.98, bottom=0.2, wspace=0.06)
    im = ax.imshow(m, cmap=cmap, vmin=0, vmax=1)
    for i in range(4):
        for j in range(4):
            ax.text(j, i, f"{m[i, j]:.2f}", ha="center", va="center", fontsize=SMALL,
                    color="white" if m[i, j] > 0.5 else INK)
    ax.set_xticks(range(4))
    ax.set_xticklabels(short)
    ax.set_yticks(range(4))
    ax.set_yticklabels(short)
    ax.set_xlabel("Predicted source dataset")
    ax.set_ylabel("True source (benign flows only)")
    ax.spines[:].set_visible(True)
    ax.grid(False)
    cb = fig.colorbar(im, cax=cax, label="Row fraction")
    cb.outline.set_linewidth(0.6)
    fit_width(fig, COL)
    # keep the colour bar exactly as tall as the (square) heat map
    fig.canvas.draw()
    p, q = ax.get_position(), cax.get_position()
    cax.set_position([q.x0, p.y0, q.width, p.height])
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
    fig, axes = plt.subplots(1, 2, figsize=(FULL, 2.1))
    fig.subplots_adjust(top=0.97, bottom=0.2, wspace=0.18)
    style = {("all", "expanding"): (ROSE, "-", "^", "G1–G5, all past years"),
             ("all", "2y"): (ROSE, "--", "^", "G1–G5, last 2 years"),
             ("loo_g5", "expanding"): (TEAL, "-", "o", "No fingerprints, all past years"),
             ("loo_g5", "2y"): (TEAL, "--", "o", "No fingerprints, last 2 years")}
    for (fs, win), (c, ls, mk, lab) in style.items():
        d = s[(s.feature_set == fs) & (s.window == win)].sort_values("test_year")
        axes[0].errorbar(d.test_year, d.pr_auc_mean, yerr=d.pr_auc_std, color=c, ls=ls, marker=mk, ms=MS,
                         mfc=c if ls == "-" else "white", mew=MEW, lw=LW, elinewidth=0.9, capsize=1.8, label=lab)
    d = s[(s.feature_set == "all") & (s.window == "expanding")].sort_values("test_year")
    prev = d.n_pos_mean / d.n_mean
    axes[0].plot(d.test_year, prev, ls="none", marker="_", ms=9, mew=1.6, color=INK, label="No-skill (prevalence)")
    axes[0].set_ylabel("PR-AUC")
    axes[0].set_ylim(0, 1.04)
    for fs, c, mk in (("all", ROSE, "^"), ("loo_g5", TEAL, "o")):
        d = s[(s.feature_set == fs) & (s.window == "expanding")].sort_values("test_year")
        axes[1].plot(d.test_year, d.roc_auc_mean, color=c, marker=mk, ms=MS, lw=LW)
    axes[1].axhline(0.5, color=GREY, lw=0.9, ls=":")
    axes[1].set_ylabel("ROC-AUC (all past years)")
    axes[1].set_ylim(0.3, 1.02)
    for ax in axes:
        ax.set_xlabel("Test year (trained on earlier years only)")
        ax.set_xticks(sorted(s.test_year.unique()))
        ax.grid(axis="x", visible=False)
    h, lab = axes[0].get_legend_handles_labels()
    order = [lab.index(t) for t in (style[("all", "expanding")][3], style[("loo_g5", "expanding")][3],
                                    style[("all", "2y")][3], style[("loo_g5", "2y")][3], "No-skill (prevalence)")]
    fig_legend(fig, [h[i] for i in order], [lab[i] for i in order], ncol=3, y=0.985)
    fit_width(fig, FULL)
    labels_below(fig, axes, ("(a) PR-AUC", "(b) ROC-AUC"))
    save(fig, "fig_f_rolling")
    n = s[(s.feature_set == "all") & (s.window == "expanding")].sort_values("test_year")
    CAPTIONS["fig_f_rolling"] = (
        "**Year-by-year drift on MTA (rolling origin).** For each test year Y, XGBoost is trained on MTA traffic "
        "from earlier years only: all years up to Y−1 (solid) or the last two years (dashed). Validation is the "
        "latest 15% of the training period. Red: all feature groups; green: without the JA3/JA4 fingerprint group "
        "(G5). (a) Points are mean PR-AUC over 5 seeds, whiskers ± 1 SD; the black dash is each test year's no-skill "
        "level. (b) ROC-AUC (all past years), which does not depend on prevalence; the dotted "
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
