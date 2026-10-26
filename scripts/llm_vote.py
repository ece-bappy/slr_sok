"""Majority vote over repeated extraction runs.

Usage: python scripts/llm_vote.py RUN_DIR TAG OUT_TAG
Reads <paper>__<TAG>_r<N>.json and writes <paper>__<OUT_TAG>.json whose fields hold, per field,
the most common answer (ties: earliest run) plus "votes" ("2/3") and "alternatives".
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


def key(v) -> str:
    if isinstance(v, list):
        return json.dumps(sorted(str(x).strip().lower() for x in v))
    return json.dumps(str(v).strip().lower())


def main(run_dir: str, tag: str, out_tag: str) -> None:
    runs = defaultdict(list)
    for p in sorted(Path(run_dir).glob(f"*__{tag}_r*.json")):
        if re.search(rf"__{re.escape(tag)}_r\d+\.json$", p.name):
            runs[p.name.split("__")[0]].append(json.loads(p.read_text(encoding="utf-8"))["fields"])
    for paper, answers in runs.items():
        voted = {}
        for field in answers[0]:
            vals = [a.get(field, {}) for a in answers]
            counts = Counter(key(v.get("value")) for v in vals)
            best, n = counts.most_common(1)[0]
            pick = next(v for v in vals if key(v.get("value")) == best)
            voted[field] = {**pick, "votes": f"{n}/{len(vals)}",
                            "alternatives": [v.get("value") for v in vals if key(v.get("value")) != best]}
        out = Path(run_dir) / f"{paper}__{out_tag}.json"
        out.write_text(json.dumps({"paper": paper, "method": f"majority vote over {len(answers)} x {tag}",
                                   "fields": voted}, indent=2, ensure_ascii=False), encoding="utf-8")
        split = [f for f, v in voted.items() if not v["votes"].startswith(str(len(answers)))]
        print(f"{paper}: {len(answers)} runs, not unanimous: {split}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
