"""Re-run code_released / data_released on the core set with the author-aware link classification.

Usage: python scripts/recheck_release.py [--runs 3]
For every core paper: link scan of the whole PDF, then the link classification `runs` times; each URL takes
its majority class, and derive() turns the voted links into code_released / data_released. Results are cached in
results/release_recheck/<id>.json (rerun-safe). Writes review/coding/release_recheck.csv: one row per paper and
field with the current verified value next to the new answer, so changed answers can be reviewed by hand.
"""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from artifact_links import find_links
from extract_v2 import classify_links, derive
from pdf_prep import prepare

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "results" / "release_recheck"


def vote_links(runs: list[list[dict]]) -> list[dict]:
    by_url: dict[str, list[dict]] = {}
    for run in runs:
        for l in run:
            by_url.setdefault(l.get("url", ""), []).append(l)
    out = []
    for url, ls in by_url.items():
        kind, n = Counter(l.get("kind") for l in ls).most_common(1)[0]
        best = next(l for l in ls if l.get("kind") == kind)
        out.append({**best, "votes": f"{n}/{len(runs)}"})
    return out


def majority_only(links: list[dict]) -> list[dict]:
    """A link class without a majority of runs (e.g. 1/3 after a three-way split) does not count."""
    out = []
    for l in links:
        n, total = (int(x) for x in str(l.get("votes", "1/1")).split("/"))
        out.append(l if 2 * n > total else {**l, "kind": "no_majority"})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--model", default="gemini-3.1-flash-lite")
    a = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sheet = list(csv.DictReader(open(ROOT / "review" / "coding" / "core_67_papers_verification.csv", encoding="utf-8-sig")))
    current = {(r["paper_id"], r["field"]): r for r in sheet if r["field"] in ("code_released", "data_released")}
    papers = sorted({(r["paper_id"], r["pdf_path"]) for r in current.values()})
    rows = []
    for pid, rel in papers:
        cache = OUT_DIR / f"{pid}.json"
        if cache.exists():
            res = json.loads(cache.read_text(encoding="utf-8"))
        else:
            paper = prepare(str(ROOT.parent / rel))
            links = find_links(paper)
            runs = [classify_links(a.model, "high", paper, links) for _ in range(a.runs)] if links["links"] else []
            voted = vote_links(runs)
            same = {l["url"]: l.get("same_authors") for l in links["links"]}
            for l in voted:
                l["same_authors"] = same.get(l.get("url"))
            d = derive({}, {"classified": voted})
            res = {"paper_id": pid, "links": voted, "not_released_statements": links.get("not_released_statements", []),
                   "code_released": d["code_released"], "data_released": d["data_released"]}
            cache.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
        res["links"] = majority_only(res["links"])
        res.update({k: v for k, v in derive({}, {"classified": res["links"]}).items() if k in ("code_released", "data_released")})
        print(f"{pid}: code={res['code_released']['value']} data={res['data_released']['value']} links={len(res['links'])}")
        for field in ("code_released", "data_released"):
            cur, new = current[(pid, field)], res[field]
            own = [f"{l['url']} [{l['kind']} {l['votes']}]" for l in res["links"] if str(l.get("kind", "")).startswith("own_")]
            rows.append({"paper_id": pid, "title": cur["title"], "field": field,
                         "current_value": cur["verified_value"], "new_value": new["value"],
                         "changed": "CHANGED" if cur["verified_value"].strip().lower() != new["value"] else "",
                         "flags": ";".join(new.get("review_flags", [])),
                         "own_links": " | ".join(own),
                         "all_links": " | ".join(f"{l.get('url')} [{l.get('kind')} {l.get('votes')}]" for l in res["links"]),
                         "evidence": " | ".join(str(l.get("evidence", ""))[:200] for l in res["links"]
                                                if str(l.get("kind", "")).startswith("own_")),
                         "not_released_statements": " | ".join(str(s)[:200] for s in res["not_released_statements"]),
                         "pdf": str(ROOT.parent / cur["pdf_path"]), "my_decision": "", "my_note": ""})
    out = ROOT / "review" / "coding" / "release_recheck.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    changed = [r for r in rows if r["changed"]]
    print(f"{len(rows)} rows, {len(changed)} changed -> {out}")
    for r in changed:
        print(f"   {r['paper_id']} {r['field']}: {r['current_value']} -> {r['new_value']}  {r['own_links'][:80]}")


if __name__ == "__main__":
    main()
