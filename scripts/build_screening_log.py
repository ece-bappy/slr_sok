"""Normalise record types, flag records that need care, and (re)build the screening log.

Usage: python scripts/build_screening_log.py [--records review/search/records.csv] [--force]

Adds to records.csv: type_norm, flags (semicolon list), related_id (published version of a preprint).
Writes review/screening_log.csv with the flags in its notes column. Refuses to overwrite a
screening log that already contains human decisions unless --force is given.

Flags (nothing is excluded automatically; they tell the screener what to look at):
  no_abstract, no_tls_term, retracted, nonresearch (erratum, editorial, paratext, peer review,
  reference entry, conference abstract), dataset, software, review, dissertation, book, preprint,
  preprint_has_published_version
"""
import argparse
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

TYPE_RULES = [  # first match wins; tested against the lower-cased raw type list
    ("retraction", r"retraction"),
    ("erratum", r"erratum|correction"),
    ("nonresearch", r"editorial|paratext|peer-review|reference-entry|conference-abstract|letter|news"),
    ("dataset", r"dataset|data-paper"),
    ("software", r"software"),
    ("review", r"\breview\b"),
    ("dissertation", r"dissertation|thesis"),
    ("book", r"\bbook\b|book-chapter"),
    ("journal_article", r"journalarticle|\barticle\b"),
    ("conference_paper", r"conference"),
    ("report", r"report"),
    ("preprint", r"preprint"),
]
FLAG_FOR = {"retraction": "retracted", "erratum": "nonresearch", "nonresearch": "nonresearch",
            "dataset": "dataset", "software": "software", "review": "review",
            "dissertation": "dissertation", "book": "book", "preprint": "preprint"}


def norm_type(raw: str, abstract: str) -> str:
    if re.match(r"\s*this article has been retracted", abstract or "", re.I):
        return "retraction"
    t = (raw or "").lower()
    for name, pat in TYPE_RULES:
        if re.search(pat, t):
            return name
    return "unknown"


def title_tokens(t: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{3,}", t.lower()))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", default=str(ROOT / "review" / "search" / "records.csv"))
    ap.add_argument("--log", default=str(ROOT / "review" / "screening_log.csv"))
    ap.add_argument("--search-date", default="2026-10-26")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    log_path = Path(a.log)
    if log_path.exists() and not a.force:
        existing = list(csv.DictReader(open(log_path, encoding="utf-8")))
        if any((r.get("decision") or "").strip() for r in existing):
            raise SystemExit("screening_log.csv already has human decisions; use --force only if you mean it")

    rows = list(csv.DictReader(open(a.records, encoding="utf-8")))
    published = [(r["id"], title_tokens(r["title"])) for r in rows
                 if norm_type(r["type"], r["abstract"]) in ("journal_article", "conference_paper")]
    for r in rows:
        tn = norm_type(r["type"], r["abstract"])
        flags = []
        if r.get("abstract_source") == "none" or not r["abstract"].strip():
            flags.append("no_abstract")
        text = (r["title"] + " " + r["abstract"]).lower()
        if not re.search(r"\btls\b|https|\bssl\b|encrypt", text):
            flags.append("no_tls_term")
        if tn in FLAG_FOR:
            flags.append(FLAG_FOR[tn])
        related = ""
        if tn == "preprint":
            mine = title_tokens(r["title"])
            best = max(((len(mine & t) / len(mine | t), i) for i, t in published if mine | t), default=(0, ""))
            if best[0] >= 0.8:
                related = best[1]
                flags.append("preprint_has_published_version")
        r["type_norm"], r["flags"], r["related_id"] = tn, ";".join(flags), related

    with open(a.records, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    cols = ["id", "source_db", "search_date", "title", "authors", "year", "venue", "type", "doi_or_url",
            "stage", "decision", "exclusion_reason", "screener", "second_coder", "agree", "notes"]
    with open(log_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            note = r["flags"] + (f";published_version={r['related_id']}" if r["related_id"] else "")
            w.writerow({"id": r["id"], "source_db": r["sources"], "search_date": a.search_date,
                        "title": r["title"], "authors": r["authors"], "year": r["year"], "venue": r["venue"],
                        "type": r["type_norm"],
                        "doi_or_url": r["doi"] or (f"arXiv:{r['arxiv_id']}" if r["arxiv_id"] else r["oa_url"]),
                        "stage": "title_abstract", "notes": note})
    from collections import Counter
    print("types:", Counter(r["type_norm"] for r in rows).most_common())
    print("flags:", Counter(f for r in rows for f in r["flags"].split(";") if f).most_common())


if __name__ == "__main__":
    main()
