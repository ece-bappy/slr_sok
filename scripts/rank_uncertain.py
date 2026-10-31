"""Settle the venue rank of the uncertain (priority 3) core papers with the official lists.

Usage: python scripts/rank_uncertain.py
Conferences: CORE 2023 (review/ranks/core2023.csv, exported from portal.core.edu.au) matched by DBLP
venue acronym or by title. Journals: Scimago best quartile from review/ranks/scimago_<year>.csv files
when present (downloaded by hand from scimagojr.com; Cloudflare blocks scripts), matched by journal
title, using the publication year or the latest year available.
Prints each paper's official rank and writes review/ranks/uncertain_ranks.csv.
"""
import csv
import re
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent.parent
RANKS = ROOT / "review" / "ranks"


def norm(s: str) -> str:
    s = (s or "").lower().replace("&", " and ")
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", s).split())


def load_core() -> tuple[dict, dict]:
    by_acr, by_title = {}, {}
    for row in csv.reader(open(RANKS / "core2023.csv", encoding="utf-8", errors="replace")):
        _id, title, acr, _src, rank = row[:5]
        by_acr.setdefault(acr.lower(), (rank, title, acr))
        by_title[norm(title)] = (rank, title, acr)
    return by_acr, by_title


def load_sjr() -> dict:
    """normalised journal title -> {year: best quartile}"""
    out = {}
    for p in sorted(RANKS.glob("scimago*.csv")):  # scimago_2024.csv or Scimago's own "scimagojr 2024.csv"
        year = int(re.search(r"(\d{4})", p.name).group(1))
        for r in csv.DictReader(open(p, encoding="utf-8-sig", errors="replace"), delimiter=";"):
            out.setdefault(norm(r.get("Title", "")), {})[year] = r.get("SJR Best Quartile", "")
    return out


def sjr_quartile(sjr: dict, venue: str, year: int) -> tuple[str, str]:
    """Quartile in the publication year, or the latest year available if the paper is newer."""
    years = sjr.get(norm(venue))
    if not years:
        return "not in Scimago files", ""
    y = year if year in years else max(y for y in years if y <= year) if any(y <= year for y in years) else max(years)
    return years[y], f"SJR {y} best quartile"


def main() -> None:
    core_acr, core_title = load_core()
    sjr = load_sjr()
    ws = load_workbook(ROOT / "review" / "final_screening" / "final_screening_325.xlsx")["Screening"]
    h = [c.value for c in ws[1]]
    dec = {r[2].value: dict(zip(h, [c.value for c in r])) for r in ws.iter_rows(min_row=2)}
    lst = [r for r in csv.DictReader(open(ROOT / "review" / "fulltext" / "download_list.csv", encoding="utf-8-sig"))
           if r["priority"] == "3" and dec[r["id"]]["final_decision"] == "include"]
    ven = {r["id"]: r for r in csv.DictReader(open(ROOT / "review" / "search" / "venue_check.csv", encoding="utf-8"))}
    rows = []
    for r in lst:
        v = ven[r["id"]]
        key = v["dblp_key"]
        kind = "conference" if key.startswith("conf/") or "conference" in v["oa_source_type"] else "journal"
        rank, matched = "", ""
        if kind == "conference":
            acr = key.split("/")[1] if key.startswith("conf/") else ""
            hit = core_acr.get(acr) or core_title.get(norm(r["venue"]))
            if hit:
                rank, matched = hit[0], f"CORE2023 {hit[2]}: {hit[1]}"
            else:
                rank = "not in CORE2023"
        elif not sjr:
            rank = "needs Scimago"
        else:
            rank, matched = sjr_quartile(sjr, v["oa_source"] or r["venue"], int(r["year"]))
        ok = rank in ("A*", "A") or rank == "Q1"
        rows.append({"id": r["id"], "year": r["year"], "kind": kind, "venue": r["venue"], "dblp": key,
                     "official_rank": rank, "matched": matched,
                     "top_tier": "yes" if ok else ("pending" if rank == "needs Scimago" else "no")})
    with open(RANKS / "uncertain_ranks.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    for x in rows:
        print(x["id"], x["year"], x["kind"], "|", x["venue"][:55], "|", x["official_rank"], "|", x["matched"][:60])


if __name__ == "__main__":
    main()
