"""Side-by-side table of LLM extraction runs against the reference coding.

Usage: python scripts/llm_compare.py GOLD.json RUN_DIR OUT.csv
RUN_DIR holds <paper>__think.json and <paper>__no-think.json from llm_extract.py.
"""
import csv
import json
import sys
from pathlib import Path


def main(gold_path: str, run_dir: str, out_path: str) -> None:
    gold = json.loads(Path(gold_path).read_text())
    rows = []
    for paper, fields in gold.items():
        if paper.startswith("_"):
            continue
        runs = {}
        for mode in ("think", "no-think"):
            p = Path(run_dir) / f"{paper}__{mode}.json"
            runs[mode] = json.loads(p.read_text())["fields"] if p.exists() else {}
        for field, accepted in fields.items():
            row = {"paper": paper, "field": field, "gold": " | ".join(accepted)}
            for mode, ans in runs.items():
                v = ans.get(field, {})
                row[f"{mode}_value"] = json.dumps(v.get("value"), ensure_ascii=False) if isinstance(v, dict) else ""
                row[f"{mode}_quote_match"] = v.get("quote_match", "") if isinstance(v, dict) else ""
                row[f"{mode}_evidence"] = v.get("evidence", "") if isinstance(v, dict) else ""
            rows.append(row)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
