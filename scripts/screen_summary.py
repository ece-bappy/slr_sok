"""Summarise the two screening passes: Gemma (lenient, all records) vs Gemini (strict, Gemma-kept records).

Usage: python scripts/screen_summary.py
Prints cross-tabulations and writes review/screening_llm/combined_suggestions.csv with one row per
record: Gemma, Gemini and (for title-only records) agy suggestions, plus a suggested_bucket for the
human screener:
  A_both_include      both passes include
  B_check             any include/maybe left (disagreement or maybe)
  C_strict_exclude    Gemma kept it, the strict pass excluded it (spot-check a sample)
  D_gemma_exclude     Gemma excluded it in the first pass (spot-check a sample)
  E_low_venue         would be A or B, but fails the venue-quality criterion (venue_check.py);
                      exclude as low_venue unless the screener overrides with a reason
"""
import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "review" / "screening_llm"


def load(p: Path) -> dict:
    return {r["id"]: r for r in csv.DictReader(open(p, encoding="utf-8"))} if p.exists() else {}


def main() -> None:
    gemma = load(D / "gemma_nothink_all.csv")
    gemini = load(D / "gemini_strict_all.csv")
    gemini.update(load(D / "gemini_strict_manual.csv"))  # re-screens after hand-entered abstracts
    agy = load(D / "agy_title_only.csv")
    recs = load(ROOT / "review" / "search" / "records.csv")
    venue = load(ROOT / "review" / "search" / "venue_check.csv")

    print("Gemma first pass:", dict(Counter(r["decision"] for r in gemma.values())))
    kept = [i for i, r in gemma.items() if r["decision"] != "exclude"]
    print(f"Gemma kept {len(kept)}; strict Gemini answered {sum(i in gemini for i in kept)}")
    print("Strict Gemini:", dict(Counter(gemini[i]["decision"] for i in kept if i in gemini)))
    print("\nGemma -> Gemini (kept records):")
    for (a, b), n in sorted(Counter((gemma[i]["decision"], gemini[i]["decision"]) for i in kept if i in gemini).items()):
        print(f"  {a:8} -> {b:8} {n}")
    print("\nStrict exclusion criteria:", Counter(gemini[i]["criterion"] for i in kept
                                                  if i in gemini and gemini[i]["decision"] == "exclude").most_common())
    if agy:
        print("\nTitle-only records, agy -> Gemini:")
        for (a, b), n in sorted(Counter((agy[i]["decision"], gemini[i]["decision"]) for i in agy if i in gemini).items()):
            print(f"  {a:8} -> {b:8} {n}")

    rows = []
    for i, g in gemma.items():
        s = gemini.get(i, {})
        t = agy.get(i, {})
        if g["decision"] == "exclude":
            bucket = "D_gemma_exclude"
        elif s.get("decision") == "include" and g["decision"] == "include" and t.get("decision", "include") != "exclude":
            bucket = "A_both_include"
        elif s.get("decision") == "exclude" and t.get("decision", "exclude") == "exclude":
            bucket = "C_strict_exclude"
        else:
            bucket = "B_check"
        v = venue.get(i, {})
        if bucket in ("A_both_include", "B_check") and v.get("venue_ok") == "False":
            bucket = "E_low_venue"
        r = recs.get(i, {})
        rows.append({"id": i, "suggested_bucket": bucket, "title": r.get("title", ""), "year": r.get("year", ""),
                     "type": r.get("type_norm", ""), "flags": r.get("flags", ""),
                     "gemma": g["decision"], "gemma_reason": g["reason"],
                     "gemini_strict": s.get("decision", ""), "gemini_criterion": s.get("criterion", ""),
                     "gemini_reason": s.get("reason", ""),
                     "agy_title_only": t.get("decision", ""), "agy_reason": t.get("reason", ""),
                     "venue": r.get("venue", ""), "venue_rule": v.get("venue_rule", "")})
    rows.sort(key=lambda r: (r["suggested_bucket"], r["id"]))
    with open(D / "combined_suggestions.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("\nBuckets:", sorted(Counter(r["suggested_bucket"] for r in rows).items()))


if __name__ == "__main__":
    main()
