"""Merge the map labels: agreed judge labels plus the human's decisions (todo/07_map_labels.csv).

Final label per paper and field = my_label if the field was in the human sheet (disputed or
spot-checked), else the label both judges agreed on. Writes review/map_labels/final_labels.csv and
appends the human-check results to review/map_labels/agreement.md.
"""
import csv
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from label_map import included, TASKS, STUDY, MODELS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "review" / "map_labels"
FIELDS = {"task": TASKS, "study_type": STUDY, "model_class": MODELS}


def read(p, enc="utf-8"):
    return list(csv.DictReader(open(p, encoding=enc)))


def wilson_upper(k, n, z=1.96):
    p = k / n
    return (p + z * z / (2 * n) + z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / (1 + z * z / n)


def main():
    recs = included()
    fl = {r["id"]: r for r in read(D / "flash_lite.csv")}
    gm = {r["id"]: r for r in read(D / "gemini38.csv")}
    human = {(r["id"], r["field"]): r for r in read(ROOT / "todo" / "07_map_labels.csv", "utf-8-sig")}
    rows = []
    for i in sorted(recs):
        out = {"id": i, "year": recs[i]["year"], "title": recs[i]["title"]}
        for f, allowed in FIELDS.items():
            h = human.get((i, f))
            if h:
                v, src = h["my_label"].strip().lower(), "human_" + h["why_here"]
            elif fl[i][f] == gm[i][f]:
                v, src = fl[i][f], "judges_agreed"
            else:
                raise SystemExit(f"{i} {f}: disputed but not in the human sheet")
            if v not in allowed:
                raise SystemExit(f"{i} {f}: {v!r}")
            out[f], out[f + "_source"] = v, src
        rows.append(out)
    with open(D / "final_labels.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    spot = [h for h in human.values() if h["why_here"] == "spot_check"]
    wrong = [h for h in spot if h["my_label"].strip().lower() != h["flash_lite"]]
    disp = [h for h in human.values() if h["why_here"] == "disputed"]
    pick = lambda k: sum(h["my_label"].strip().lower() == h[k] for h in disp)
    neither = sum(h["my_label"].strip().lower() not in (h["flash_lite"], h["gemini38"]) for h in disp)
    md = (D / "agreement.md").read_text(encoding="utf-8").split("\n## Human check")[0].rstrip()
    md += "\n\n## Human check (8 Nov 2026)\n\n" + "\n".join([
        f"- Spot check of agreed labels: {len(wrong)}/{len(spot)} field labels wrong "
        f"({len(wrong) / len(spot):.1%}; 95% Wilson upper bound {wilson_upper(len(wrong), len(spot)):.1%}), "
        f"on {len({h['id'] for h in spot})} randomly drawn papers.",
        *[f"  - {h['id']} {h['field']}: {h['flash_lite']} -> {h['my_label'].strip()} ({h['note'].strip()})" for h in wrong],
        f"- Disputed labels ({len(disp)}): human sided with Flash Lite {pick('flash_lite')}, "
        f"with Gemini 3.8 {pick('gemini38')}, with neither {neither}.",
        "- Final labels: `final_labels.csv` (source column per field).",
    ]) + "\n"
    (D / "agreement.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
