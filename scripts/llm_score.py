"""Score LLM extraction runs against the reference coding.

Usage: python scripts/llm_score.py RUN_DIR GOLD_DIR TAG [TAG ...]
For each TAG, reads <paper>__<TAG>_r<N>.json (or <paper>__<TAG>.json) from RUN_DIR and scores
every field as C (correct), P (partial), W (wrong) or ? (free text not yet graded).
GOLD_DIR holds gold.json (accepted scalar values), gold_sets.json (list-field rules) and
free_text_grades.json ({paper: {field: {answer_text: "C"|"P"|"W"}}}), which this script
extends with any ungraded free-text answers marked "?" so they can be graded by hand.
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

LIST_FIELDS = {"label_source", "feature_groups", "tls_versions", "metrics"}
FREE_FIELDS = {"datasets", "model_family", "first_n_packets", "hardware", "best_reported_score"}
SYNONYMS = {"f1-score": "f1", "f1 score": "f1", "f-score": "f1", "false detection rate": "fdr",
            "true positive rate": "tpr", "true negative rate": "tnr"}


def as_list(v) -> list[str]:
    if isinstance(v, list):
        items = v
    else:
        items = re.split(r"[;,]|\band\b", str(v))
    out = []
    for it in items:
        s = re.sub(r"\(.*?\)", "", str(it)).strip().lower()
        s = re.sub(r"^tls\s*", "", s)
        s = re.sub(r"^(g[1-5])\b.*", r"\1", s)
        s = SYNONYMS.get(s, s)
        if s:
            out.append(s.upper() if re.fullmatch(r"g[1-5]", s) else s)
    return out


def score_list(ans, rule: dict) -> str:
    got = set(as_list(ans))
    req = {x.lower() if not x.startswith("G") else x for x in rule["required"]}
    opt = {x.lower() if not x.startswith("G") else x for x in rule["optional"]}
    if rule.get("nonempty") and not got:
        return "W"
    if req <= got <= req | opt:
        return "C"
    return "P" if got & (req | opt) else "W"


def score_scalar(ans, accepted: list[str]) -> str:
    a = str(ans).strip().lower()
    ok = [x.rstrip("*").lower() for x in accepted]
    return "C" if a in ok else "W"


def main(run_dir: str, gold_dir: str, tags: list[str]) -> None:
    gd = Path(gold_dir)
    gold = json.loads((gd / "gold.json").read_text(encoding="utf-8"))
    sets = json.loads((gd / "gold_sets.json").read_text(encoding="utf-8"))
    ft_path = gd / "free_text_grades.json"
    free = json.loads(ft_path.read_text(encoding="utf-8")) if ft_path.exists() else {}

    summary = {}
    errors = defaultdict(Counter)
    for tag in tags:
        files = sorted(Path(run_dir).glob(f"*__{tag}_r*.json")) or sorted(Path(run_dir).glob(f"*__{tag}.json"))
        per_run = defaultdict(Counter)
        for f in files:
            paper = f.name.split("__")[0]
            run = re.search(r"_r(\d+)\.json$", f.name)
            run = run.group(1) if run else "1"
            fields = json.loads(f.read_text(encoding="utf-8"))["fields"]
            for field, accepted in gold[paper].items():
                v = fields.get(field, {})
                ans = v.get("value") if isinstance(v, dict) else None
                if field in FREE_FIELDS:
                    key = json.dumps(ans, ensure_ascii=False)
                    grade = free.setdefault(paper, {}).setdefault(field, {}).setdefault(key, "?")
                elif field in LIST_FIELDS:
                    grade = score_list(ans, sets[paper][field])
                else:
                    grade = score_scalar(ans, accepted)
                per_run[run][grade] += 1
                if grade in "PW":
                    errors[tag][f"{paper[:3]} {field}={json.dumps(ans, ensure_ascii=False)[:40]} ({grade})"] += 1
        summary[tag] = {r: dict(c) for r, c in sorted(per_run.items())}

    ft_path.write_text(json.dumps(free, indent=1, ensure_ascii=False), encoding="utf-8")
    for tag, runs in summary.items():
        print(f"== {tag}")
        for r, c in runs.items():
            print(f"   r{r}: C={c.get('C', 0)} P={c.get('P', 0)} W={c.get('W', 0)} ungraded={c.get('?', 0)}")
        for e, n in errors[tag].most_common():
            print(f"     x{n} {e}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
