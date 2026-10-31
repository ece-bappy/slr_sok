"""Score v2 extraction outputs against review/llm_test/gold_v2.json.

Usage: python scripts/score_v2.py RUN_DIR TAG [TAG ...]
Reads <paper>__<TAG>_r<N>.json or <paper>__<TAG>.json. Grades: C correct, P partial (set overlap), W wrong;
"pending" fields (new in v2, reference not yet confirmed by the user) are listed, not scored.
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

GOLD = Path(__file__).resolve().parent.parent / "review" / "llm_test" / "gold_v2.json"
SYN = {"f1-score": "f1", "f1 score": "f1", "f-score": "f1", "f-measure": "f1", "true positive rate": "tpr",
       "true negative rate": "tnr", "false detection rate": "fdr"}


def items(v) -> set:
    vals = v if isinstance(v, list) else re.split(r"[;,]", str(v))
    out = set()
    for x in vals:
        s = re.sub(r"\(.*?\)", "", str(x)).strip()
        out.add(s if re.fullmatch(r"G[1-5]|\d\.\d", s) else SYN.get(s.lower(), s.lower()))
    return {x for x in out if x}


def grade(rule: dict, value) -> str:
    t = rule["type"]
    if t == "scalar":
        return "C" if str(value).strip().lower() in [a.lower() for a in rule["accepted"]] else "W"
    if t == "contains":
        return "C" if any(k in str(value).lower() for k in rule["any"]) else "W"
    if t == "set":
        if rule.get("exact"):  # canonical names: compare as written
            norm, got = (lambda s: set(s)), set(value or [])
        else:
            norm = lambda s: {x if re.fullmatch(r"G[1-5]|\d\.\d", x) else x.lower() for x in s}
            got = norm(items(value))
        req, opt = norm(set(rule["required"])), norm(set(rule["optional"]))
        if rule.get("nonempty") and not got:
            return "W"
        if got & norm(set(rule.get("forbidden", []))):
            return "W"
        if req <= got <= req | opt:
            return "C"
        return "P" if got & (req | opt) else "W"
    return "-"


def main(run_dir: str, tags: list[str]) -> None:
    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    for tag in tags:
        files = sorted(Path(run_dir).glob(f"*__{tag}_r*.json")) or sorted(Path(run_dir).glob(f"*__{tag}.json"))
        files = [f for f in files if re.search(rf"__{re.escape(tag)}(_r\d+)?\.json$", f.name)]
        per = defaultdict(Counter)
        errors, pending = Counter(), defaultdict(list)
        for f in files:
            paper = f.name.split("__")[0]
            run = (re.search(r"_r(\d+)\.json$", f.name) or [None, "vote"])[1]
            fields = json.loads(f.read_text(encoding="utf-8"))["fields"]
            for name, rule in gold[paper].items():
                if name.startswith("_"):
                    continue
                value = (fields.get(name) or {}).get("value")
                g = grade(rule, value)
                if g == "-":
                    pending[(paper[:3], name)].append(json.dumps(value, ensure_ascii=False)[:70])
                    continue
                per[run][g] += 1
                if g != "C":
                    errors[f"{paper[:3]} {name}={json.dumps(value, ensure_ascii=False)[:60]} ({g})"] += 1
        print(f"== {tag}")
        for r, c in sorted(per.items()):
            n = sum(c.values())
            print(f"   r{r}: C={c['C']} P={c['P']} W={c['W']} of {n}")
        for e, n in errors.most_common():
            print(f"     x{n} {e}")
        print("   pending (not scored):")
        for (p, name), vals in sorted(pending.items()):
            print(f"     {p} {name}: {' | '.join(sorted(set(vals)))}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
