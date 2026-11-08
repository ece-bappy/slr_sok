"""Code the two extra checklist fields (tuning_data, per_tls_version) for the 67 core papers.

Usage:
  python scripts/code_checklist.py OUT.csv --judge gemini [--ids S1,S2]   # Flash Lite via the API
  python scripts/code_checklist.py OUT.csv --judge agy    [--ids S1,S2]   # Gemini 3.8 via agy (file agent)

Rules: review/coding/checklist_rulebook.txt, the same text for both judges. Paper text: the cleaned
agent text (results/sonnet/<id>.txt, made by prepare_for_agent.py; missing ones are created there).
Writes SUGGESTIONS only; a human decides disputes (scripts/compare_checklist.py). Resumable.
"""
import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm_extract import call_gemini, norm, quote_found  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RULES_PATH = ROOT / "review" / "coding" / "checklist_rulebook.txt"
RULES = RULES_PATH.read_text(encoding="utf-8")
TXT = ROOT / "results" / "sonnet"
AGY_DIR = ROOT / "results" / "checklist_agy"
CORE = ROOT / "review" / "coding" / "core_67_papers_verification.csv"
VALUES = {"tuning_data": ["validation", "test", "not_stated"], "per_tls_version": ["yes", "no"]}
SCHEMA = {"type": "object", "properties": {
    f: {"type": "object", "properties": {"value": {"type": "string", "enum": v}, "evidence": {"type": "string"}},
        "required": ["value", "evidence"]} for f, v in VALUES.items()}, "required": list(VALUES)}

GEMINI_PROMPT = """Code one research paper for a systematic review, exactly as a careful human coder would.
Apply this rulebook exactly:

{rules}

Return JSON: {{"tuning_data": {{"value": ..., "evidence": ...}}, "per_tls_version": {{"value": ..., "evidence": ...}}}}.
Evidence must be copied character-for-character from the paper text below.

PAPER TEXT ({pid}):
{text}"""

AGY_PROMPT = """You have NO shell access and must not run commands. Use only file reading and writing.
Task: code two fields of one research paper for a systematic review, exactly as a careful human coder would.
1. Read the rulebook: {rules}
2. Read the paper text: {paper}
3. Write ONE file, {out}, containing only JSON of this form:
{{"tuning_data": {{"value": "validation|test|not_stated", "evidence": "<one verbatim passage>"}},
  "per_tls_version": {{"value": "yes|no", "evidence": "<one verbatim passage>"}}}}
Evidence must be copied character-for-character from the paper text; "" only for not_stated or no.
Do not write any other file."""


def core_ids():
    with open(CORE, encoding="utf-8-sig", newline="") as f:
        return sorted({r["paper_id"]: r["pdf_path"] for r in csv.DictReader(f)}.items())


def paper_text(pid, pdf_rel):
    p = TXT / f"{pid}.txt"
    if not p.exists():
        from prepare_for_agent import prepare_paper
        p.write_text(prepare_paper(str(ROOT.parent / pdf_rel)), encoding="utf-8")
    return p


def ask_gemini(pid, text):
    resp = call_gemini("gemini-3.1-flash-lite", GEMINI_PROMPT.format(rules=RULES, pid=pid, text=text),
                       "high", None, SCHEMA)
    return json.loads(resp.get("response") or "{}")


def ask_agy(pid, paper):
    AGY_DIR.mkdir(parents=True, exist_ok=True)
    out = AGY_DIR / f"{pid}.json"
    if not out.exists():
        prompt = AGY_PROMPT.format(rules=RULES_PATH, paper=paper, out=out)
        subprocess.run(["agy", "-p", prompt.replace('"', '\\"'), "--model", "gemini-3.8-flash-high",
                        "--mode", "accept-edits", "--print-timeout", "900s", "--output-format", "json",
                        "--add-dir", str(ROOT)], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", timeout=1100)
    return json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--judge", choices=["gemini", "agy"], required=True)
    ap.add_argument("--ids", default=None)
    a = ap.parse_args()
    papers = core_ids()
    if a.ids:
        keep = set(a.ids.split(","))
        papers = [p for p in papers if p[0] in keep]
    out = Path(a.out)
    done = {r["paper_id"] for r in csv.DictReader(open(out, encoding="utf-8"))} if out.exists() else set()
    fields = ["paper_id", "judge"] + [f"{f}{s}" for f in VALUES for s in ("", "_evidence", "_quote_found")]
    new = not out.exists()
    with open(out, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        if new:
            w.writeheader()
        for pid, pdf in papers:
            if pid in done:
                continue
            tp = paper_text(pid, pdf)
            text = tp.read_text(encoding="utf-8")
            text_norm = norm(text)
            got = {}
            for attempt in (1, 2):
                try:
                    got = ask_gemini(pid, text) if a.judge == "gemini" else ask_agy(pid, tp)
                except Exception as e:  # quota, timeout, bad JSON: retry once, then skip (resumable)
                    print(f"{pid}: error {e!r}")
                    got = {}
                if all(isinstance(got.get(f), dict) and got[f].get("value") in v for f, v in VALUES.items()):
                    break
                if a.judge == "agy":
                    (AGY_DIR / f"{pid}.json").unlink(missing_ok=True)
                got = {}
            if not got:
                print(f"{pid}: no valid answer, skipped")
                continue
            row = {"paper_id": pid, "judge": a.judge}
            for f in VALUES:
                ev = got[f].get("evidence", "")
                row[f], row[f + "_evidence"] = got[f]["value"], ev
                row[f + "_quote_found"] = bool(ev) and quote_found(ev, text_norm) >= 0.9
            w.writerow(row)
            fh.flush()
            print(f"{pid}: {row['tuning_data']} / {row['per_tls_version']}")


if __name__ == "__main__":
    main()
