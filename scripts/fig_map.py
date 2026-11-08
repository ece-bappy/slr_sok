"""Figure 3: the 291-paper systematic map (threat per year; model class share per year).

Usage: python scripts/fig_map.py
Reads review/map_labels/final_labels.csv; writes review/map_labels/fig_map.pdf/.png and copies the PDF
to the manuscript's figures/ folder. Same style as review/benchmark/figures/make_figures.py: text
width 390 pt, Times, labels 10 pt, other text 9 pt, Okabe-Ito colours plus hatching for greyscale.
"""
import csv
import shutil
from collections import Counter
from pathlib import Path

import matplotlib
import matplotlib.font_manager as fm
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "review" / "map_labels"
MANU = ROOT.parent / "manuscript" / "figures"
W = 5.39
FONTS = ["Times New Roman", "Nimbus Roman", "TeX Gyre Termes", "Times"]
FONT = next((f for f in FONTS if f in {x.name for x in fm.fontManager.ttflist}), None)
if FONT is None:
    raise SystemExit(f"none of {FONTS} is installed")
LBL, SMALL = 10, 9
plt.rcParams.update({"font.family": "serif", "font.serif": [FONT], "font.size": SMALL, "axes.labelsize": LBL,
                     "axes.titlesize": LBL, "legend.fontsize": SMALL, "xtick.labelsize": SMALL,
                     "ytick.labelsize": SMALL, "pdf.fonttype": 42, "ps.fonttype": 42, "axes.linewidth": 0.8,
                     "hatch.linewidth": 0.8, "axes.spines.top": False, "axes.spines.right": False,
                     "legend.frameon": False})
OI = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9", "#999999"]
HATCH = ["", "//", "..", "\\\\", "xx", "--", ""]

TASK_GROUPS = [("Malware, general", {"malware"}), ("DoH tunnelling", {"doh_tunnel"}),
               ("C2 / botnet", {"c2_botnet"}), ("Multi-attack IDS", {"multi_attack"}), ("DoS / flooding", {"dos"}),
               ("Other threats", {"web_attack", "malicious_server", "anomaly", "other"})]
MODEL_GROUPS = [("Classical ML", {"classical_ml"}), ("Deep learning", {"deep_learning"}),
                ("Transformer / LLM", {"transformer", "llm"}), ("Graph", {"graph"}), ("Hybrid", {"hybrid"}),
                ("Not stated", {"unclear"})]
MODEL_COL = [0, 1, 2, 3, 4, 6]  # "not stated" in grey


def main():
    rows = list(csv.DictReader(open(D / "final_labels.csv", encoding="utf-8")))
    years = sorted({int(r["year"]) for r in rows})
    xl = [str(y) if y < 2026 else "2026*" for y in years]
    x = np.arange(len(years))

    fig, (a, b) = plt.subplots(2, 1, figsize=(W, 5.0), sharex=True)
    fig.subplots_adjust(left=0.105, right=0.655, bottom=0.09, top=0.95, hspace=0.2)  # legends fill the right
    bottom = np.zeros(len(years))
    for k, (name, keys) in enumerate(TASK_GROUPS):
        c = Counter(int(r["year"]) for r in rows if r["task"] in keys)
        v = np.array([c[y] for y in years])
        nz = v > 0  # zero-height hatched bars leave hatch artefacts in some PDF viewers
        a.bar(x[nz], v[nz], 0.72, bottom=bottom[nz], color=OI[k], hatch=HATCH[k], edgecolor="white", lw=0.5,
              label=f"{name} ({v.sum()})")
        bottom += v
    for xi, t in zip(x, bottom):
        a.text(xi, t + 1, f"{int(t)}", ha="center", va="bottom", fontsize=SMALL)
    a.set_ylabel("Papers")
    a.set_ylim(0, bottom.max() * 1.12)
    a.set_title("(a) Threat targeted", loc="left")
    a.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), handlelength=1.4, borderaxespad=0.1)
    a.grid(axis="y", lw=0.5, color="#dddddd", zorder=0)
    a.set_axisbelow(True)

    tot = Counter(int(r["year"]) for r in rows)
    bottom = np.zeros(len(years))
    for k, (name, keys) in enumerate(MODEL_GROUPS):
        c = Counter(int(r["year"]) for r in rows if r["model_class"] in keys)
        v = np.array([100 * c[y] / tot[y] for y in years])
        n = sum(c.values())
        nz = v > 0
        b.bar(x[nz], v[nz], 0.72, bottom=bottom[nz], color=OI[MODEL_COL[k]], hatch=HATCH[k], edgecolor="white",
              lw=0.5, label=f"{name} ({n})")
        bottom += v
    b.set_ylabel("Share of papers (%)")
    b.set_ylim(0, 100)
    b.set_title("(b) Model class of the paper's own method", loc="left")
    b.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), handlelength=1.4, borderaxespad=0.1)
    b.set_xticks(x, xl)
    b.set_xlabel("Publication year")

    for ext in ("pdf", "png"):
        fig.savefig(D / f"fig_map.{ext}", dpi=300)  # fixed size: exactly text width, never scaled
    plt.close(fig)
    if MANU.exists():
        shutil.copyfile(D / "fig_map.pdf", MANU / "fig_map.pdf")
    print("wrote fig_map;", len(rows), "papers")


if __name__ == "__main__":
    main()
