"""Compare repeated LLM extraction runs and flag fields where they disagree.

Usage: python scripts/llm_flag.py RUN_DIR OUT.csv TAG [--gold GOLD.json]
Reads <paper>__<TAG>_r1.json, <paper>__<TAG>_r2.json, ... and writes one row per
paper/field with each run's value, an agree flag, and the reference value if given.
Enumerated fields must match exactly (as sets of items); free-text fields agree when
their word sets overlap by at least 60%.
"""
import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

FREE_TEXT = {"datasets", "model_family", "metrics", "best_reported_score", "hardware", "tls_versions",
             "first_n_packets"}


def items(v) -> set[str]:
    if isinstance(v, list):
        v = ";".join(map(str, v))
    s = str(v).lower()
    parts = re.split(r"[;,]|\band\b", s)
    out = set()
    for p in parts:
        p = re.sub(r"\(.*?\)", "", p)
        p = re.sub(r"\b(g[1-5])\b.*", r"\1", p.strip())  # "G3 handshake fields" -> "g3"
        p = re.sub(r"[^a-z0-9._]+", " ", p).strip()
        if p:
            out.add(p)
    return out


def words(v) -> set[str]:
    return set(re.findall(r"[a-z0-9.]+", json.dumps(v).lower()))


def agree(field: str, a, b) -> bool:
    if field in FREE_TEXT:
        wa, wb = words(a), words(b)
        return bool(wa | wb) and len(wa & wb) / len(wa | wb) >= 0.6
    return items(a) == items(b)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("out")
    ap.add_argument("tag")
    ap.add_argument("--gold")
    a = ap.parse_args()

    gold = json.loads(Path(a.gold).read_text(encoding="utf-8")) if a.gold else {}
    runs: dict[str, dict[int, dict]] = defaultdict(dict)
    for p in sorted(Path(a.run_dir).glob(f"*__{a.tag}_r*.json")):
        paper, run = re.match(rf"(.+)__{re.escape(a.tag)}_r(\d+)\.json$", p.name).groups()
        runs[paper][int(run)] = json.loads(p.read_text(encoding="utf-8"))["fields"]

    if not runs:
        raise SystemExit(f"no *__{a.tag}_r<N>.json files in {a.run_dir}")
    rows, n_flag = [], 0
    for paper, by_run in sorted(runs.items()):
        ids = sorted(by_run)
        fields = list(by_run[ids[0]].keys())
        for field in fields:
            vals = [by_run[i].get(field, {}).get("value") for i in ids]
            ok = all(agree(field, vals[0], v) for v in vals[1:])
            n_flag += not ok
            row = {"paper": paper, "field": field, "flag": "" if ok else "DISAGREE"}
            for i, v in zip(ids, vals):
                row[f"r{i}"] = json.dumps(v, ensure_ascii=False)
            row["reference"] = " | ".join(gold.get(paper, {}).get(field, []))
            for i in ids:
                row[f"r{i}_evidence"] = by_run[i].get(field, {}).get("evidence", "")
            row["human_verdict"] = ""
            row["human_note"] = ""
            rows.append(row)
    with open(a.out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} cells, {n_flag} flagged as DISAGREE -> {a.out}")
    for r in rows:
        if r["flag"]:
            print(f"  {r['paper'][:24]:24} {r['field']:24} " + " vs ".join(r[k] for k in r if re.fullmatch(r"r\d+", k)))


if __name__ == "__main__":
    main()
