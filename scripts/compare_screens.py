"""Compare screening decisions from several judges against a reference and list disagreements.

Usage: python scripts/compare_screens.py REFERENCE.csv OUT_REVIEW.csv NAME=FILE.csv [NAME=FILE.csv ...]
Each CSV has id, decision, criterion, reason. Writes OUT_REVIEW.csv with every record where any
judge's decision differs from the reference (titles and abstracts included for the reviewer).
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(p: str) -> dict:
    return {r["id"]: r for r in csv.DictReader(open(p, encoding="utf-8"))}


def main(ref_path: str, out_path: str, judges: list[str]) -> None:
    ref = load(ref_path)
    others = {name: load(p) for name, p in (j.split("=", 1) for j in judges)}
    recs = load(str(ROOT / "review" / "search" / "records.csv"))
    rows, agree = [], {n: 0 for n in others}
    all_agree = 0
    for i, r in ref.items():
        diff = False
        row = {"id": i, "title": recs[i]["title"], "reference": f"{r['decision']} {r['criterion']}".strip(),
               "reference_reason": r["reason"]}
        for n, d in others.items():
            o = d.get(i, {"decision": "MISSING", "criterion": "", "reason": ""})
            row[n] = f"{o['decision']} {o['criterion']}".strip()
            row[f"{n}_reason"] = o["reason"]
            if o["decision"] == r["decision"]:
                agree[n] += 1
            else:
                diff = True
        all_agree += not diff
        if diff:
            ab = recs[i]["abstract"] if recs[i].get("abstract_source") != "none" else "(no abstract)"
            rows.append({**row, "abstract": ab, "your_decision": "", "your_note": ""})
    n = len(ref)
    print(f"{n} records; all judges agree with reference on {all_agree}")
    for name, k in agree.items():
        print(f"  {name}: same decision as reference {k}/{n}")
    if rows:
        with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"{len(rows)} disagreements -> {out_path}")
        for r in rows:
            print(f"  {r['id']}: ref={r['reference']} | " + " | ".join(f"{k}={r[k]}" for k in others))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
