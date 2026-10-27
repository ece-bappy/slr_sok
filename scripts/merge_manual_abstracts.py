"""Copy hand-entered abstracts from missing_abstracts_TODO.csv into records.csv.

Usage: python scripts/merge_manual_abstracts.py [TODO.csv]
Only rows with a non-empty `abstract` are used; those records get abstract_source=manual. Prints the
updated ids so they can be re-screened, e.g.
  python scripts/screen_strict.py review/screening_llm/gemini_strict_manual.csv --ids <ids> --judge gemini
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORDS = ROOT / "review" / "search" / "records.csv"


def main(todo: Path) -> None:
    filled = {r["id"]: " ".join(r["abstract"].split())
              for r in csv.DictReader(open(todo, encoding="utf-8-sig")) if r["abstract"].strip()}
    rows = list(csv.DictReader(open(RECORDS, encoding="utf-8")))
    for r in rows:
        if r["id"] in filled:
            r["abstract"], r["abstract_source"] = filled[r["id"]], "manual"
    with open(RECORDS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(filled)} abstracts merged: {','.join(sorted(filled))}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "review" / "search" / "missing_abstracts_TODO.csv")
