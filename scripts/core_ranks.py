"""Official venue ranks for every still-included paper of the provisional core set (download_list.csv).

Usage: python scripts/core_ranks.py
Conferences: CORE 2023 rank. Journals: Scimago best quartile and the best quartile among Computer
Science categories, in the publication year (nearest available year otherwise). Also marks the top
10% most-cited included papers per year. Writes review/ranks/core_ranks.csv with two rule variants:
  rule_A        CORE A*/A, or SJR best quartile Q1, or top 10% cited in its year
  rule_A_strict CORE A*/A, or Q1 in a Computer Science category, or top 10% cited in its year
"""
import csv
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

from openpyxl import load_workbook

from rank_uncertain import RANKS, load_core, norm

ROOT = Path(__file__).resolve().parent.parent


def load_sjr() -> dict:
    """normalised title -> {year: (best quartile, best CS-category quartile)}"""
    out = {}
    for p in sorted(RANKS.glob("scimago*.csv")):
        year = int(re.search(r"(\d{4})", p.name).group(1))
        for r in csv.DictReader(open(p, encoding="utf-8-sig", errors="replace"), delimiter=";"):
            cs = [q for cat, q in re.findall(r"([^;]+?) \((Q\d)\)", r.get("Categories", ""))
                  if "comput" in cat.lower() or "information systems" in cat.lower() or "software" in cat.lower()]
            out.setdefault(norm(r.get("Title", "")), {})[year] = (r.get("SJR Best Quartile", ""), min(cs) if cs else "")
    return out


def main() -> None:
    core_acr, core_title = load_core()
    sjr = load_sjr()
    ws = load_workbook(ROOT / "review" / "final_screening" / "final_screening_325.xlsx")["Screening"]
    h = [c.value for c in ws[1]]
    dec = {r[2].value: dict(zip(h, [c.value for c in r])) for r in ws.iter_rows(min_row=2)}
    rec = {r["id"]: r for r in csv.DictReader(open(ROOT / "review" / "search" / "records.csv", encoding="utf-8"))}
    ven = {r["id"]: r for r in csv.DictReader(open(ROOT / "review" / "search" / "venue_check.csv", encoding="utf-8"))}

    included = [i for i, d in dec.items() if d["final_decision"] == "include"]
    by_year = defaultdict(list)
    for i in included:
        by_year[rec[i]["year"]].append(i)
    top10 = set()
    for ids in by_year.values():
        ids.sort(key=lambda i: -int(rec[i]["cited_by"] or 0))
        top10.update(ids[: math.ceil(len(ids) * 0.10)])

    lst = [r for r in csv.DictReader(open(ROOT / "review" / "fulltext" / "download_list.csv", encoding="utf-8-sig"))
           if dec[r["id"]]["final_decision"] == "include"]
    rows = []
    for r in lst:
        v, year = ven[r["id"]], int(r["year"])
        key, name = v["dblp_key"], v["oa_source"] or r["venue"]
        kind = "conference" if key.startswith("conf/") or v["oa_source_type"] == "conference" else "journal"
        core, best, cs, src = "", "", "", ""
        if kind == "conference":
            hit = core_acr.get(key.split("/")[1].lower() if key.startswith("conf/") else "") or core_title.get(norm(r["venue"]))
            core, src = (hit[0], f"CORE2023 {hit[2]}") if hit else ("not ranked", "CORE2023")
        else:
            years = sjr.get(norm(name))
            if years:
                y = min(years, key=lambda k: (abs(k - year), -k))
                best, cs = years[y]
                src = f"SJR {y}"
            else:
                best = "not in Scimago"
        t = r["id"] in top10
        rows.append({"id": r["id"], "year": year, "kind": kind, "venue": name, "core": core, "sjr_best": best,
                     "sjr_cs": cs, "source": src, "top10_cited": "yes" if t else "",
                     "rule_A": "yes" if core in ("A*", "A") or best == "Q1" or t else "",
                     "rule_A_strict": "yes" if core in ("A*", "A") or cs == "Q1" or t else ""})
    with open(RANKS / "core_ranks.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} still-included core candidates")
    print("rule_A:", sum(x["rule_A"] == "yes" for x in rows), "| rule_A_strict:", sum(x["rule_A_strict"] == "yes" for x in rows))
    print("conference ranks:", Counter(x["core"] for x in rows if x["kind"] == "conference"))
    print("journal best:", Counter(x["sjr_best"] for x in rows if x["kind"] == "journal"),
          "| CS-category:", Counter(x["sjr_cs"] for x in rows if x["kind"] == "journal"))
    for x in rows:
        if x["rule_A"] != "yes" or x["rule_A_strict"] != "yes":
            print(x["id"], x["year"], x["kind"], "|", x["venue"][:50], "|", x["core"] or f"{x['sjr_best']}/{x['sjr_cs']}",
                  "| A" if x["rule_A"] else "| -", "strict" if x["rule_A_strict"] else "-")


if __name__ == "__main__":
    main()
