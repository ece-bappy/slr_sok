"""Full-text re-check of priority-2 core papers against the rulebook (mainly C3: is the traffic TLS?).

Usage: python scripts/recheck_c3.py [--ids S0001,S0002] [--out FILE]
For each paper: (1) a keyword scan of the whole PDF (TLS terms, TLS datasets, generic IDS benchmarks)
with the first page each appears on; (2) one strict Gemini 3.1 Flash Lite pass over the method and
experiment sections with the rulebook's criteria, returning the evaluation datasets and verbatim quotes.
Quotes are checked against the PDF text. Output is a SUGGESTION for the human screener
(review/fulltext/recheck_c3.csv); the human decides. Papers in SKIP_LLM (possible blind-validation
papers) get the keyword scan only.
"""
import argparse
import csv
import json
import re
from pathlib import Path

import fitz  # PyMuPDF

from llm_extract import call_gemini, norm, quote_found
from pdf_sections import extract

ROOT = Path(__file__).resolve().parent.parent
PDFS = ROOT.parent / "papers" / "core"
RULEBOOK = ROOT / "review" / "final_screening" / "rulebook.txt"
SKIP_LLM = {"S2338", "S0205", "S0041", "S1938", "S1954", "S2183"}  # todo_for_me.md validation candidates
CODES = ["off_topic", "secondary", "non_tls", "benign_only", "decryption", "no_ml", "no_eval", "not_main_focus"]
SCAN = {
    "tls_terms": r"\b(TLS|SSL|HTTPS|DoH|DNS[- ]over[- ]HTTPS|QUIC|JA3|JA4|X\.509|ClientHello|ServerHello|handshake|SNI)\b",
    "tls_datasets": r"(CTU-?13|Stratosphere|malware-traffic-analysis|\bMTA\b|CIRA-CIC-DoHBrw|DoHBrw|CESNET|HIKARI|"
                    r"Bot-?IoT-?TLS|DoH-?Tunnel)",
    "generic_benchmarks": r"(CIC-?IDS-?20\d\d|CSE-CIC|UNSW-?NB15|NSL-?KDD|KDD ?99|ToN[_-]IoT|CICIoT|Bot-?IoT|"
                          r"ISCX ?VPN|USTC-?TFC|Edge-?IIoT|CIC-?DDoS)",
}
DATASET = {"type": "OBJECT", "properties": {
    "name": {"type": "STRING"},
    "contains_tls": {"type": "STRING", "enum": ["yes", "no", "unclear"]},
    "has_malicious_class": {"type": "STRING", "enum": ["yes", "no", "unclear"]},
    "quote": {"type": "STRING"}}, "required": ["name", "contains_tls", "has_malicious_class", "quote"]}
SCHEMA = {"type": "OBJECT", "properties": {
    "evaluation_datasets": {"type": "ARRAY", "items": DATASET},
    "tls_flows_isolated": {"type": "STRING", "enum": ["yes", "no", "not_applicable"]},
    "tls_isolation_quote": {"type": "STRING"},
    "main_task": {"type": "STRING"},
    "suggestion": {"type": "STRING", "enum": ["include", "exclude"]},
    "criterion": {"type": "STRING", "enum": ["none"] + CODES},
    "rule_applied": {"type": "STRING"},
    "reason": {"type": "STRING"}},
    "required": ["evaluation_datasets", "tls_flows_isolated", "tls_isolation_quote", "main_task", "suggestion",
                 "criterion", "rule_applied", "reason"]}

PROMPT = """You are re-checking ONE paper for a strict systematic review of machine-learning detection of
malicious TLS/HTTPS traffic. The paper passed title/abstract screening, but its abstract did not show that
the evaluation data is TLS traffic. Use the FULL TEXT below to decide, following the rulebook exactly.

RULEBOOK (criteria, exclusion codes, rulings):
{rules}

TASK
1. List every dataset used to EVALUATE the method (not ones only cited). For each: does it contain TLS/HTTPS/
   SSL/QUIC/DoH traffic (yes/no/unclear), does it have malicious classes (yes/no/unclear), and give ONE
   contiguous verbatim quote from the paper describing it (copy exactly, no "...").
2. If a generic benchmark is used, did the authors isolate TLS/encrypted flows? Quote the passage, or "" if none.
3. State the main task in a few words.
4. Suggest include or exclude under the strict rulebook ("unproven = not met"); criterion is "none" for
   include, else the FIRST applicable code. rule_applied names the rule (e.g. "R1", "R2", "C3"). Reason at
   most 40 words.

PAPER {pid}: {title}
FULL TEXT (related work, conclusion and references removed):
{text}"""


def rules_text() -> str:
    t = RULEBOOK.read_text(encoding="utf-8")
    start = t.index("2. INCLUSION CRITERIA")
    end = t.index("5. SHEET COLUMNS")
    return t[start:end]


def scan(doc: fitz.Document) -> dict:
    out = {}
    pages = [pg.get_text() for pg in doc]
    for key, pat in SCAN.items():
        rx = re.compile(pat, re.I if key != "tls_datasets" else 0)
        hits, first = [], {}
        for n, txt in enumerate(pages, 1):
            for m in rx.finditer(txt):
                w = m.group(0)
                hits.append(w)
                first.setdefault(w.upper(), n)
        out[key] = f"{len(hits)}: " + ", ".join(f"{w} p{p}" for w, p in sorted(first.items(), key=lambda t: t[1])[:8])
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids")
    ap.add_argument("--out", default=str(ROOT / "review" / "fulltext" / "recheck_c3.csv"))
    a = ap.parse_args()
    lst = {r["id"]: r for r in csv.DictReader(open(ROOT / "review" / "fulltext" / "download_list.csv", encoding="utf-8-sig"))}
    ids = a.ids.split(",") if a.ids else [i for i, r in lst.items() if r["priority"] == "2"]
    out = Path(a.out)
    done = {r["id"] for r in csv.DictReader(open(out, encoding="utf-8-sig"))} if out.exists() else set()
    fields = ["id", "title", "tls_terms", "tls_datasets", "generic_benchmarks", "datasets", "tls_flows_isolated",
              "tls_isolation_quote", "main_task", "llm_suggestion", "llm_criterion", "rule_applied", "llm_reason",
              "quotes_verified", "your_decision", "your_criterion", "your_note"]
    new = not out.exists()
    f = open(out, "a", newline="", encoding="utf-8-sig")
    w = csv.DictWriter(f, fieldnames=fields)
    if new:
        w.writeheader()
    rules = rules_text()
    for pid in ids:
        if pid in done:
            continue
        path = PDFS / f"{pid}.pdf"
        with fitz.open(path) as doc:
            row = {"id": pid, "title": lst[pid]["title"], **scan(doc)}
            full_norm = norm(" ".join(pg.get_text() for pg in doc))
        if pid in SKIP_LLM:
            row.update(llm_suggestion="(not run: blind-validation candidate)")
        else:
            text, _ = extract(str(path))
            text = re.sub(r"\s+", " ", text)[:120_000]
            prompt = PROMPT.format(rules=rules, pid=pid, title=lst[pid]["title"], text=text)
            try:
                ans = json.loads(call_gemini("gemini-3.1-flash-lite", prompt, "high", None, SCHEMA)["response"])
            except (Exception, SystemExit) as e:
                print(f"{pid}: failed ({e}); rerun to retry", flush=True)
                continue
            quotes = [d["quote"] for d in ans["evaluation_datasets"]] + [ans["tls_isolation_quote"]]
            scores = [quote_found(q, full_norm) for q in quotes if q.strip()]
            row.update(
                datasets=" | ".join(f"{d['name']} [tls={d['contains_tls']}, malicious={d['has_malicious_class']}]: "
                                    f"\"{d['quote']}\"" for d in ans["evaluation_datasets"]),
                tls_flows_isolated=ans["tls_flows_isolated"], tls_isolation_quote=ans["tls_isolation_quote"],
                main_task=ans["main_task"], llm_suggestion=ans["suggestion"],
                llm_criterion="" if ans["criterion"] == "none" else ans["criterion"],
                rule_applied=ans["rule_applied"], llm_reason=ans["reason"],
                quotes_verified=f"{sum(s >= 0.9 for s in scores)}/{len(scores)}")
        w.writerow(row)
        f.flush()
        print(f"{pid}: {row.get('llm_suggestion')} {row.get('llm_criterion', '')} quotes {row.get('quotes_verified', '')}",
              flush=True)
    f.close()


if __name__ == "__main__":
    main()
