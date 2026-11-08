"""Compare the two judges' map labels and build the human review sheet.

Inputs:  review/map_labels/flash_lite.csv, review/map_labels/gemini38.csv
Outputs: review/map_labels/agreement.md
         todo/07_map_labels.csv  - every disputed field, plus a random spot-check of 30 agreed papers
Per field, a label is accepted only if both judges gave it; otherwise the human decides.
"""
import csv
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from label_map import included  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "review" / "map_labels"
FIELDS = ["task", "study_type", "model_class"]
SPOT = 30


def read(p):
    return {r["id"]: r for r in csv.DictReader(open(p, encoding="utf-8"))}


def kappa(a, b):
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in ca) / n / n
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def main():
    recs = included()
    fl, gm = read(D / "flash_lite.csv"), read(D / "gemini38.csv")
    ids = sorted(recs)
    missing = [i for i in ids if i not in fl or i not in gm]
    if missing:
        raise SystemExit(f"{len(missing)} papers lack a label from one judge: {missing[:10]}")

    lines = ["# Map labels: judge agreement (291 included papers)", "",
             "Flash Lite = gemini-3.1-flash-lite (API); Gemini 3.8 = gemini-3.8-flash-high (agy). Same prompt "
             "(`review/coding/map_label_rulebook.txt`), blind to each other.", "",
             "| Field | Agreement | Cohen's κ |", "|---|---|---|"]
    for f in FIELDS:
        a, b = [fl[i][f] for i in ids], [gm[i][f] for i in ids]
        agree = sum(x == y for x, y in zip(a, b))
        lines.append(f"| {f} | {agree}/{len(ids)} ({agree / len(ids):.0%}) | {kappa(a, b):.2f} |")
    full = [i for i in ids if all(fl[i][f] == gm[i][f] for f in FIELDS)]
    lines += ["", f"Papers agreed on all three fields: {len(full)}/{len(ids)}."]
    (D / "agreement.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))

    random.seed(20261108)
    spot = set(random.sample(full, min(SPOT, len(full))))
    out = ROOT / "todo" / "07_map_labels.csv"
    cols = ["id", "why_here", "field", "flash_lite", "gemini38", "my_label", "note",
            "flash_lite_reason", "gemini38_reason", "year", "title", "abstract"]
    n = 0
    with open(out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for i in ids:
            r = recs[i]
            for f in FIELDS:
                disputed = fl[i][f] != gm[i][f]
                if not disputed and i not in spot:
                    continue
                w.writerow({"id": i, "why_here": "disputed" if disputed else "spot_check", "field": f,
                            "flash_lite": fl[i][f], "gemini38": gm[i][f], "my_label": "", "note": "",
                            "flash_lite_reason": fl[i]["reason"], "gemini38_reason": gm[i]["reason"],
                            "year": r["year"], "title": r["title"],
                            "abstract": str(r["abstract"] or "")[:1500]})
                n += 1
    print(f"{n} rows -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
