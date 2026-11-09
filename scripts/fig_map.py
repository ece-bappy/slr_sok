"""Figure 3: the 291-paper systematic map (threat per year; model class share per year).

Usage: python scripts/fig_map.py
Reads review/map_labels/final_labels.csv; writes review/map_labels/fig_map.pdf/.png and copies the PDF
to the manuscript's figures/ folder. Style: the manuscript's shared module figures/src/palette.py
(two-column Elsevier layout: full width 7.25 in, Times, 8 pt text, palette colours plus hatching for
greyscale). Panels side by side; each panel has its own legend above it (different categories).
"""
import csv
import shutil
import sys
from collections import Counter
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "review" / "map_labels"
MANU = ROOT.parent / "manuscript" / "figures"
sys.path.insert(0, str(MANU / "src"))
from palette import CYCLE, FULL, HATCHES, apply_style, panel_label, save  # noqa: E402

apply_style()

TASK_GROUPS = [("Malware, general", {"malware"}), ("DoH tunnelling", {"doh_tunnel"}),
               ("C2 / botnet", {"c2_botnet"}), ("Multi-attack IDS", {"multi_attack"}), ("DoS / flooding", {"dos"}),
               ("Other threats", {"web_attack", "malicious_server", "anomaly", "other"})]
MODEL_GROUPS = [("Classical ML", {"classical_ml"}), ("Deep learning", {"deep_learning"}),
                ("Transformer / LLM", {"transformer", "llm"}), ("Graph", {"graph"}), ("Hybrid", {"hybrid"}),
                ("Not stated", {"unclear"})]  # CYCLE[5] is GREY: "not stated" in grey


def legend_above(ax, ncol=3):
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.01), ncol=ncol, handlelength=1.2,
              columnspacing=0.6, handletextpad=0.3, borderaxespad=0.0)


def main():
    rows = list(csv.DictReader(open(D / "final_labels.csv", encoding="utf-8")))
    years = sorted({int(r["year"]) for r in rows})
    xl = [str(y) if y < 2026 else "2026*" for y in years]
    x = np.arange(len(years))

    fig, (a, b) = plt.subplots(1, 2, figsize=(FULL, 2.55))
    fig.subplots_adjust(left=0.065, right=0.99, bottom=0.25, top=0.80, wspace=0.20)
    bottom = np.zeros(len(years))
    for k, (name, keys) in enumerate(TASK_GROUPS):
        c = Counter(int(r["year"]) for r in rows if r["task"] in keys)
        v = np.array([c[y] for y in years])
        nz = v > 0  # zero-height hatched bars leave hatch artefacts in some PDF viewers
        a.bar(x[nz], v[nz], 0.72, bottom=bottom[nz], color=CYCLE[k], hatch=HATCHES[k], edgecolor="white",
              lw=0.4, label=f"{name} ({v.sum()})")
        bottom += v
    for xi, t in zip(x, bottom):
        a.text(xi, t + 0.8, f"{int(t)}", ha="center", va="bottom")
    a.set_ylabel("Papers")
    a.set_ylim(0, bottom.max() * 1.13)
    a.grid(axis="x", visible=False)
    a.set_xticks(x, xl)
    a.set_xlabel("Publication year")
    legend_above(a)
    panel_label(a, "(a) Threat targeted", y=-0.27)

    tot = Counter(int(r["year"]) for r in rows)
    bottom = np.zeros(len(years))
    for k, (name, keys) in enumerate(MODEL_GROUPS):
        c = Counter(int(r["year"]) for r in rows if r["model_class"] in keys)
        v = np.array([100 * c[y] / tot[y] for y in years])
        n = sum(c.values())
        nz = v > 0
        b.bar(x[nz], v[nz], 0.72, bottom=bottom[nz], color=CYCLE[k], hatch=HATCHES[k], edgecolor="white",
              lw=0.4, label=f"{name} ({n})")
        bottom += v
    b.set_ylabel("Share of papers (%)")
    b.set_ylim(0, 100)
    b.grid(axis="x", visible=False)
    b.set_xticks(x, xl)
    b.set_xlabel("Publication year")
    legend_above(b)
    panel_label(b, "(b) Model class of the paper's own method", y=-0.27)

    save(fig, D / "fig_map.pdf")  # final size: at most full text width, never scaled
    fig.savefig(D / "fig_map.png", bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    if MANU.exists():
        shutil.copyfile(D / "fig_map.pdf", MANU / "fig_map.pdf")
    print("wrote fig_map;", len(rows), "papers")


if __name__ == "__main__":
    main()
