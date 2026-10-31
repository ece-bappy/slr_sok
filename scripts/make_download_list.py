"""Full-text download list for the provisional Option-A core set (top-tier venue or top 10% cited per year).

Usage: python scripts/make_download_list.py
Reads the included records from review/final_screening/final_screening_325.xlsx and writes
review/fulltext/download_list.csv, one row per paper with where to get it and a priority:
  1  certain top-tier venue (or top 10% cited) and no re-check flag        -> download now
  2  certain tier, but the strict re-check may exclude it (see recheck_flag) -> read the paper's
     dataset section first; download only if it stays included
  3  venue rank uncertain until the official CORE / SJR lists are checked   -> wait
source = open_access: Claude fetches it from the open-access link; manual: download by hand
(Zotero Connector, one at a time) and save as papers/core/<id>.pdf.
Venue ranks here are PROVISIONAL (from memory of CORE 2023 / SJR), to be replaced by the official lists.
"""
import csv
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "review" / "fulltext" / "download_list.csv"

SURE = {"conf/raid", "conf/www", "conf/asiaccs", "conf/infocom", "journals/tifs", "journals/cn", "journals/iotj",
        "journals/eswa", "journals/jnca", "journals/tnsm", "journals/compsec", "journals/kbs", "journals/tvt",
        "journals/tnse", "journals/ton", "journals/tit", "journals/tsc", "journals/isci", "journals/comcom",
        "journals/ojcomps"}
SURE_NAMES = re.compile(r"^(IEEE Transactions on Information Forensics|IEEE Transactions on Dependable|Computer Networks$|"
                        r"IEEE Internet of Things Journal|Computers & Security|Information Fusion|IEEE Transactions on "
                        r"Computational Social|IEEE Conference on Computer Communications$|IEEE Open Journal of the "
                        r"Communications)")
UNSURE = {"journals/access", "conf/trustcom", "conf/lcn", "conf/iwqos", "conf/dsaa", "journals/cluster",
          "journals/istr", "journals/cybersec", "journals/fcsc", "journals/ojcs"}
UNSURE_NAMES = re.compile(r"^(PLoS ONE|Scientific Reports|ICT Express|High-Confidence Computing|IEEE Access)")
TLS = re.compile(r"\b(tls|ssl|https|doh|dns.over.https|quic|ja3|ja4|x\.?509|certificates?|handshakes?|sni)\b", re.I)
GENERIC = re.compile(r"(cic-?ids|cse-cic|unsw|nsl-kdd|kdd|ton.iot|ciciot|bot-iot|iscx.?vpn|ustc-tfc|edge-iiot)", re.I)
TLS_DATA = re.compile(r"(ctu|stratosphere|malware.traffic.analysis|\bmta\b|doh.?brw|cesnet|hikari|cira)", re.I)


def tier(dblp: str, name: str) -> str:
    pre = "/".join(dblp.split("/")[:2]) if dblp else ""
    if pre == "conf/infocom" and "Workshops" in name:
        return ""
    if pre in SURE or SURE_NAMES.search(name):
        return "certain"
    if pre in UNSURE or UNSURE_NAMES.search(name):
        return "uncertain"
    return ""


def main() -> None:
    ws = load_workbook(ROOT / "review" / "final_screening" / "final_screening_325.xlsx")["Screening"]
    head = [c.value for c in ws[1]]
    inc = [dict(zip(head, [c.value for c in r])) for r in ws.iter_rows(min_row=2)]
    inc = [r for r in inc if r["final_decision"] == "include"]
    rec = {r["id"]: r for r in csv.DictReader(open(ROOT / "review" / "search" / "records.csv", encoding="utf-8"))}
    ven = {r["id"]: r for r in csv.DictReader(open(ROOT / "review" / "search" / "venue_check.csv", encoding="utf-8"))}

    by_year = defaultdict(list)
    for r in inc:
        by_year[r["year"]].append(r["id"])
    top10 = set()
    for ids in by_year.values():
        ids.sort(key=lambda i: -int(rec[i]["cited_by"] or 0))
        top10.update(ids[: math.ceil(len(ids) * 0.10)])

    rows = []
    for r in inc:
        i, R, V = r["id"], rec[r["id"]], ven[r["id"]]
        name = V["oa_source"] or R["venue"]
        t = tier(V["dblp_key"], name)
        if not t and i not in top10:
            continue
        text = f"{r['title']} {r['abstract']}"
        flag = ("generic IDS benchmark, no TLS dataset named" if GENERIC.search(text) and not TLS_DATA.search(text)
                else "only 'encrypted', no TLS/HTTPS/DoH term" if not TLS.search(text) else "")
        reason = ", ".join(x for x in [f"{t} top-tier venue" if t else "", "top 10% cited in its year" if i in top10 else ""] if x)
        prio = 3 if t == "uncertain" and i not in top10 else (2 if flag else 1)
        free = R["oa_url"] or (f"https://arxiv.org/abs/{R['arxiv_id']}" if R["arxiv_id"] else "")
        rows.append({"priority": prio, "id": i, "source": "open_access" if free else "manual",
                     "doi_link": f"https://doi.org/{R['doi']}" if R["doi"] else "", "open_access_link": free,
                     "save_as": f"papers/core/{i}.pdf", "title": R["title"], "year": R["year"], "venue": name,
                     "cited_by": R["cited_by"], "why_core": reason, "recheck_flag": flag,
                     "downloaded": "", "note": ""})
    rows.sort(key=lambda x: (x["priority"], x["source"] != "manual", x["id"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} papers -> {OUT}")
    print(sorted(Counter((x["priority"], x["source"]) for x in rows).items()))


if __name__ == "__main__":
    main()
