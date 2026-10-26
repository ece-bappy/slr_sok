"""Compare two merged.csv search results by DOI / arXiv id / normalized title.

Usage: python scripts/search_diff.py OLD/merged.csv NEW/merged.csv [ADDED_OUT.csv]
"""
import csv
import re
import sys
from collections import Counter


def keys(r: dict) -> set[str]:
    k = set()
    if r.get("doi"):
        k.add("doi:" + r["doi"].lower().replace("https://doi.org/", "").strip())
    if r.get("arxiv_id"):
        k.add("arxiv:" + r["arxiv_id"].lower().strip())
    t = re.sub(r"[^a-z0-9]", "", r.get("title", "").lower())
    if t:
        k.add("title:" + t)
    return k


def tls_term(r: dict) -> bool:
    return bool(re.search(r"\btls\b|https|\bssl\b|encrypt", (r["title"] + " " + r["abstract"]).lower()))


def main(old_path: str, new_path: str, out_path: str | None = None) -> None:
    old = list(csv.DictReader(open(old_path, encoding="utf-8")))
    new = list(csv.DictReader(open(new_path, encoding="utf-8")))
    old_keys = set().union(*(keys(r) for r in old))
    new_keys = set().union(*(keys(r) for r in new))
    added = [r for r in new if not keys(r) & old_keys]
    dropped = [r for r in old if not keys(r) & new_keys]
    print(f"old {len(old)}  new {len(new)}  added {len(added)}  no longer found {len(dropped)}")
    print("added by source:", Counter(r["sources"] for r in added).most_common())
    print("added with a TLS/HTTPS/SSL/encrypt term in title+abstract:", sum(tls_term(r) for r in added))
    print("added by year:", sorted(Counter(r["year"] for r in added).items()))
    if out_path and added:
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(added[0].keys()))
            w.writeheader()
            w.writerows(added)


if __name__ == "__main__":
    main(*sys.argv[1:4])
