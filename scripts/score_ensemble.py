"""Validate the two-model ensemble (Flash Lite v2 vote + Gemini 3.8 agent) against the human blind coding.

Usage: python scripts/score_ensemble.py [--flash DIR] [--g38 DIR]
For every paper/field in review/coding/blind_validation_sheet.csv: are the two models' answers the same
(the core-set rule accepted those without human review), and is the agreed answer the human's answer?
Categorical fields are compared on their allowed values (free words after an allowed value, e.g.
"other: JARM", count as that value); datasets on registry canonical names; free-text fields
(features_used, model_family, hardware, first_n_packets, metrics) are listed for hand grading.
Writes review/coding/ensemble_validation.csv.
"""
import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from dataset_registry import canonical
from save_result import ALLOWED_VALUES

ROOT = Path(__file__).resolve().parent.parent
FREE = {"features_used", "model_family", "hardware", "first_n_packets", "metrics"}


def norm(s) -> str:
    return re.sub(r"[^a-z0-9.]+", " ", str(s).lower()).strip()


def items(v) -> list:
    if isinstance(v, list):
        return v
    s = str(v).strip()
    if s.startswith("["):
        try:
            return json.loads(s.replace("'", '"'))
        except json.JSONDecodeError:
            pass
    return [x for x in re.split(r"[;,|]", s) if x.strip()]


def as_set(field: str, v) -> frozenset:
    out = set()
    for it in items(v):
        if field == "datasets_evaluated":
            name = it.get("canonical") or it.get("name") if isinstance(it, dict) else re.sub(r"\(.*?\)", "", str(it))
            out.add(canonical(str(name))["name"])
            continue
        t = norm(it)
        if field in ("split_protocols", "main_split") and t in ("not stated", "none"):
            t = "unclear"  # human wording outside the allowed values, same meaning
        allowed = sorted(ALLOWED_VALUES.get(field, []), key=len, reverse=True)
        hit = next((a for a in allowed if t == norm(a) or t.startswith(norm(a) + " ")), None)
        out.add(hit or t)
    return frozenset(x for x in out if x)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--flash", default=str(ROOT.parent / "papers" / "llm_validation"))
    ap.add_argument("--g38", default=str(ROOT / "results" / "validation_gemini38"))
    a = ap.parse_args()
    human = [r for r in csv.DictReader(open(ROOT / "review" / "coding" / "blind_validation_sheet.csv", encoding="utf-8-sig"))
             if r["validation_id"].startswith("V")]
    rows, stats = [], defaultdict(Counter)
    for r in human:
        pid, field = r["paper_id"], r["field"]
        fl = json.load(open(Path(a.flash) / f"{pid}__v2vote.json", encoding="utf-8"))["fields"].get(field, {})
        g38_path = Path(a.g38) / f"{pid}.json"
        if not g38_path.exists():
            continue
        g = json.load(open(g38_path, encoding="utf-8"))["fields"].get(field, {})
        fv, gv, hv = fl.get("value"), g.get("value"), r["your_value"]
        kind = "free_text" if field in FREE else "scored"
        if kind == "scored":
            fs, gs, hs = as_set(field, fv), as_set(field, gv), as_set(field, hv)
            models_agree = fs == gs
            correct = (fs == hs) if models_agree else None
            outcome = ("agreed_correct" if correct else "agreed_WRONG") if models_agree else "disputed (human reviews)"
            flagged = bool(fl.get("review_flags")) or bool(g.get("validation_warnings"))
            stats["all"][outcome] += 1
            stats[field][outcome] += 1
        else:
            outcome, flagged = "grade by hand", ""
        rows.append({"paper_id": pid, "field": field, "kind": kind, "outcome": outcome,
                     "flash_lite": json.dumps(fv, ensure_ascii=False)[:300], "gemini38": json.dumps(gv, ensure_ascii=False)[:300],
                     "human": hv, "flash_flags": ";".join(fl.get("review_flags") or [])})
    out = ROOT / "review" / "coding" / "ensemble_validation.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    s = stats["all"]
    agreed = s["agreed_correct"] + s["agreed_WRONG"]
    print(f"papers scored: {sorted({r['paper_id'] for r in rows})}")
    print(f"scored rows: {sum(s.values())}; models agree on {agreed}; agreed rows correct {s['agreed_correct']}/{agreed}"
          f" ({100 * s['agreed_correct'] / max(agreed, 1):.0f}%); disputed {s['disputed (human reviews)']}")
    print("per field (agreed_correct / agreed_WRONG / disputed):")
    for field, c in sorted(stats.items()):
        if field != "all":
            print(f"   {field:22} {c['agreed_correct']} / {c['agreed_WRONG']} / {c['disputed (human reviews)']}")
    print("agreed but WRONG:")
    for r in rows:
        if r["outcome"] == "agreed_WRONG":
            print(f"   {r['paper_id']} {r['field']}: models {r['flash_lite'][:60]} | human {r['human'][:60]}")
    print(f"-> {out}")


if __name__ == "__main__":
    main()
