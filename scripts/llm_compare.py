"""Side-by-side table of LLM extraction runs against the reference coding.

Usage: python scripts/llm_compare.py GOLD.json RUN_DIR OUT.csv [SUFFIX ...]
RUN_DIR holds <paper>__<suffix>.json files from llm_extract.py; each SUFFIX
(e.g. "think__denoised") becomes a value/evidence column pair.
"""
import csv
import json
import sys
from pathlib import Path


def main(gold_path: str, run_dir: str, out_path: str, suffixes: list[str]) -> None:
    gold = json.loads(Path(gold_path).read_text(encoding="utf-8"))
    rows = []
    for paper, fields in gold.items():
        if paper.startswith("_"):
            continue
        runs = {}
        for sfx in suffixes:
            p = Path(run_dir) / f"{paper}__{sfx}.json"
            runs[sfx] = json.loads(p.read_text(encoding="utf-8"))["fields"] if p.exists() else {}
        for field, accepted in fields.items():
            row = {"paper": paper, "field": field, "reference": " | ".join(accepted)}
            for sfx, ans in runs.items():
                v = ans.get(field, {})
                v = v if isinstance(v, dict) else {}
                row[f"{sfx}"] = json.dumps(v.get("value"), ensure_ascii=False)
                row[f"{sfx}_evidence"] = v.get("evidence", "")
            row["human_verdict"] = ""
            row["human_note"] = ""
            rows.append(row)
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:] or ["think", "no-think"])
