"""Suggest map labels (task, study_type, model_class) for the 291 included papers.

Usage:
  python scripts/label_map.py OUT.csv [--judge gemini|agy] [--batch 15] [--model ...] [--ids S1,S2]

The rules are review/coding/map_label_rulebook.txt, embedded verbatim in the prompt, so every
judge sees the same text. Writes SUGGESTIONS only; a human decides disputed rows
(scripts/compare_map_labels.py builds the review sheet). Resumable: ids already in OUT.csv are skipped.
"""
import argparse
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm_extract import call_gemini  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RULES = (ROOT / "review" / "coding" / "map_label_rulebook.txt").read_text(encoding="utf-8")
SHEET = ROOT / "review" / "final_screening" / "final_screening_325.xlsx"
TASKS = ["c2_botnet", "doh_tunnel", "web_attack", "dos", "malicious_server", "malware", "multi_attack",
         "anomaly", "other"]
STUDY = ["detection", "evasion", "evaluation", "system"]
MODELS = ["classical_ml", "deep_learning", "transformer", "llm", "graph", "hybrid", "unclear"]

PROMPT = """You label papers for the systematic map of a review on machine-learning detection of malicious
TLS/HTTPS traffic. Every paper below is already included in the review. Apply the rulebook exactly.

{rules}

Return one object per record with id, task, study_type, model_class and reason.

RECORDS:
{records}"""

SCHEMA = {
    "type": "OBJECT",
    "properties": {"labels": {"type": "ARRAY", "items": {
        "type": "OBJECT",
        "properties": {
            "id": {"type": "STRING"},
            "task": {"type": "STRING", "enum": TASKS},
            "study_type": {"type": "STRING", "enum": STUDY},
            "model_class": {"type": "STRING", "enum": MODELS},
            "reason": {"type": "STRING"},
        },
        "required": ["id", "task", "study_type", "model_class", "reason"]}}},
    "required": ["labels"],
}


def included() -> dict:
    import openpyxl
    rows = list(openpyxl.load_workbook(SHEET, read_only=True)["Screening"].iter_rows(values_only=True))
    h = rows[0]
    out = {}
    for r in rows[1:]:
        d = dict(zip(h, r))
        if d["final_decision"] == "include":
            out[d["id"]] = d
    return out


def fmt(d: dict) -> str:
    return (f"[{d['id']}] year={d['year']} venue={d['venue'] or 'unknown'}\nTITLE: {d['title']}\n"
            f"ABSTRACT: {str(d['abstract'] or '').strip()[:2500]}")


def ask_gemini(prompt: str, model: str) -> list:
    resp = call_gemini(model, prompt, "high", None, SCHEMA)
    return json.loads(resp.get("response") or "{}").get("labels", [])


def ask_agy(prompt: str, model: str) -> list:
    text = ("You have NO shell or file access; answer only. Return ONLY a JSON object "
            '{"labels": [{"id": ..., "task": ..., "study_type": ..., "model_class": ..., "reason": ...}]}.\n\n'
            + prompt)
    res = subprocess.run(["agy", "-p", text.replace('"', '\\"'), "--model", model, "--print-timeout", "300s",
                          "--output-format", "json"], capture_output=True, text=True, encoding="utf-8", timeout=420)
    body = json.loads(res.stdout).get("response", "")
    return json.loads(re.search(r"\{.*\}", body, re.S).group(0)).get("labels", [])


def valid(d: dict) -> bool:
    return d.get("task") in TASKS and d.get("study_type") in STUDY and d.get("model_class") in MODELS


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--judge", choices=["gemini", "agy"], default="gemini")
    ap.add_argument("--model", default=None)
    ap.add_argument("--batch", type=int, default=15)
    ap.add_argument("--ids", default=None)
    a = ap.parse_args()
    model = a.model or ("gemini-3.1-flash-lite" if a.judge == "gemini" else "gemini-3.8-flash-high")

    recs = included()
    ids = a.ids.split(",") if a.ids else sorted(recs)
    out = Path(a.out)
    done = {r["id"] for r in csv.DictReader(open(out, encoding="utf-8"))} if out.exists() else set()
    todo = [i for i in ids if i not in done]
    fields = ["id", "task", "study_type", "model_class", "reason", "judge"]
    new = not out.exists()
    f = open(out, "a", newline="", encoding="utf-8")
    w = csv.DictWriter(f, fieldnames=fields)
    if new:
        w.writeheader()
    for start in range(0, len(todo), a.batch):
        pending = todo[start: start + a.batch]
        for attempt in range(3):
            prompt = PROMPT.format(rules=RULES, records="\n\n".join(fmt(recs[i]) for i in pending))
            try:
                got = ask_gemini(prompt, model) if a.judge == "gemini" else ask_agy(prompt, model)
            except (Exception, SystemExit) as e:  # call_gemini raises SystemExit on HTTP errors
                print(f"  attempt {attempt + 1} failed: {e}", flush=True)
                got = []
            got = {d["id"].strip("[] "): d for d in got if isinstance(d, dict) and "id" in d and valid(d)}
            for i in pending:
                if i in got:
                    d = got[i]
                    w.writerow({"id": i, "task": d["task"], "study_type": d["study_type"],
                                "model_class": d["model_class"], "reason": d.get("reason", ""),
                                "judge": f"{a.judge}/{model}"})
            f.flush()
            pending = [i for i in pending if i not in got]
            if not pending:
                break
        if pending:
            print(f"  no valid answer for {pending}; rerun to retry", flush=True)
        print(f"{min(start + a.batch, len(todo))}/{len(todo)} done", flush=True)
    f.close()


if __name__ == "__main__":
    main()
