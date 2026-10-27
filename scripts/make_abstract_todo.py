"""Write a short list of missing-abstract records worth looking up by hand.

Usage: python scripts/make_abstract_todo.py
The shortlist is a title-only judgement (Claude, 2026-10-27) over the 470 records with no abstract:
records whose title suggests malicious + encrypted/TLS/DoH traffic, where the LLM screens either
excluded them or could not decide without an abstract. Writes review/search/missing_abstracts_TODO.csv
with a clickable link per record and an empty `abstract` column for the human to fill in; feed it back
with scripts/merge_manual_abstracts.py.
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "review" / "search" / "missing_abstracts_TODO.csv"

# priority 1: title names malicious traffic AND encrypted/TLS/DoH; priority 2: one of the two is clear
SHORTLIST = {
    "S2778": (1, "malware in encrypted traffic; Gemma excluded it with no abstract"),
    "S2576": (1, "malware identification from encrypted IIoT traffic"),
    "S1774": (1, "phishing detection in encrypted TLS traffic"),
    "S0217": (1, "C2 channel detection"),
    "S0230": (1, "malicious traffic in web connections"),
    "S1191": (1, "SSL renegotiation DoS (THC-SSL-DoS) with ML"),
    "S1217": (1, "DoH traffic detection and categorisation (malicious DoH?)"),
    "S1717": (1, "DoH tunnel tool traffic identification"),
    "S1682": (1, "adversarial attacks on DoH tunnel detectors (robustness of ML detectors)"),
    "S2221": (1, "DoH traffic detection, excluded as benign-only without an abstract"),
    "S3014": (1, "DoH traffic classification with DL, excluded as not main focus"),
    "S3120": (1, "DoH vulnerability detection with ML, excluded as off-topic"),
    "S0334": (2, "malicious traffic detection; encryption unknown"),
    "S0366": (2, "early malicious-traffic detection; encryption unknown"),
    "S1451": (2, "malicious web session detection; HTTPS unknown"),
    "S1208": (2, "application-layer DDoS; HTTPS unknown"),
    "S2577": (2, "malicious traffic detection; excluded as non-TLS without an abstract"),
    "S1748": (2, "malware traffic classification (dataset may contain TLS)"),
    "S1607": (2, "mixed network traffic detection; excluded as non-TLS without an abstract"),
    "S2753": (2, "NIDS for contemporary (encrypted?) traffic"),
    "S1778": (2, "DGA detection in DoH; excluded as decryption, may be metadata only"),
    "S1675": (2, "threat-adaptive DoH network; excluded as off-topic"),
    "S0490": (2, "encrypted IoT traffic classification; malicious classes?"),
    "S0747": (2, "encrypted IoT traffic classification; malicious classes?"),
    "S0939": (2, "encrypted traffic classification; malicious classes?"),
    "S0557": (2, "encrypted traffic analysis; malicious classes?"),
    "S1887": (2, "encrypted traffic analysis; malicious classes?"),
    "S1972": (2, "encrypted traffic analysis; malicious classes?"),
    "S0485": (2, "backdoors in encrypted traffic classifiers; malicious-traffic task?"),
    "S2706": (2, "evading encrypted traffic classifiers; malicious-traffic task?"),
    "S3420": (2, "encrypted traffic inspection system; ML?"),
}


def link(r: dict) -> str:
    if r["doi"]:
        return f"https://doi.org/{r['doi']}"
    if r["oa_url"]:
        return r["oa_url"]
    return f"https://www.semanticscholar.org/paper/{r['s2_id']}"


def main() -> None:
    rec = {r["id"]: r for r in csv.DictReader(open(ROOT / "review" / "search" / "records.csv", encoding="utf-8"))}
    d = ROOT / "review" / "screening_llm"
    gemma = {r["id"]: r for r in csv.DictReader(open(d / "gemma_nothink_all.csv", encoding="utf-8"))}
    strict = {r["id"]: r for r in csv.DictReader(open(d / "gemini_strict_all.csv", encoding="utf-8"))}
    rows = []
    for i, (prio, why) in SHORTLIST.items():
        r = rec[i]
        assert r["abstract_source"] == "none", i
        s = strict.get(i, {})
        url = link(r)
        rows.append({"priority": prio, "id": i, "url": url, "open_link": f'=HYPERLINK("{url}","open")',
                     "title": r["title"], "year": r["year"], "venue": r["venue"],
                     "llm_now": f"gemma {gemma[i]['decision']} / gemini {s.get('decision', '-')} {s.get('criterion', '')}".strip(),
                     "why_flagged": why, "abstract": "", "note": ""})
    rows.sort(key=lambda x: (x["priority"], x["id"]))
    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} records -> {OUT}")


if __name__ == "__main__":
    main()
