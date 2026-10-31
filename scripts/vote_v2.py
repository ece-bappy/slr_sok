"""Majority vote over v2 extraction runs, then recompute the derived fields from the voted answers.

Usage: python scripts/vote_v2.py RUN_DIR TAG OUT_TAG
Like llm_vote.py, but datasets are compared by canonical name (their quotes differ between runs), and
derive() is re-applied so computed fields agree with the voted inputs. Link classes are voted per URL.
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from extract_v2 import FIELDS, derive


def key(field: str, v) -> str:
    if field == "datasets_evaluated" and isinstance(v, list):
        return json.dumps(sorted({str(d.get("canonical") or d.get("name")) for d in v if isinstance(d, dict)}))
    if isinstance(v, list):
        return json.dumps(sorted(str(x).strip().lower() for x in v))
    return json.dumps(str(v).strip().lower())


def main(run_dir: str, tag: str, out_tag: str) -> None:
    runs = defaultdict(list)
    for p in sorted(Path(run_dir).glob(f"*__{tag}_r*.json")):
        if re.search(rf"__{re.escape(tag)}_r\d+\.json$", p.name):
            runs[p.name.split("__")[0]].append(json.loads(p.read_text(encoding="utf-8")))
    for paper, docs in runs.items():
        voted = {}
        for field in FIELDS:
            vals = [d["fields"].get(field, {}) for d in docs]
            counts = Counter(key(field, v.get("value")) for v in vals)
            best, n = counts.most_common(1)[0]
            pick = next(v for v in vals if key(field, v.get("value")) == best)
            flags = list(pick.get("review_flags", [])) + ([] if n == len(vals) else ["not_unanimous"])
            voted[field] = {**pick, "votes": f"{n}/{len(vals)}", "review_flags": flags,
                            "alternatives": [v.get("value") for v in vals if key(field, v.get("value")) != best]}
        by_url = defaultdict(list)
        for d in docs:
            for l in d["links"]["classified"]:
                by_url[l["url"]].append(l)
        classified = []
        for url, ls in by_url.items():
            kind, n = Counter(l["kind"] for l in ls).most_common(1)[0]
            classified.append({**next(l for l in ls if l["kind"] == kind), "votes": f"{n}/{len(docs)}"})
        link_info = {**docs[0]["links"], "classified": classified}
        voted.update(derive(voted, link_info))
        out = Path(run_dir) / f"{paper}__{out_tag}.json"
        out.write_text(json.dumps({"paper": paper, "method": f"majority vote over {len(docs)} x {tag}",
                                   "links": link_info, "fields": voted}, indent=2, ensure_ascii=False), encoding="utf-8")
        split = [f for f in FIELDS if not voted[f].get("votes", f"{len(docs)}/{len(docs)}").startswith(str(len(docs)))]
        print(f"{paper}: {len(docs)} runs, not unanimous: {split}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
