"""Title/abstract pre-screening with a local Ollama model (Gemma).

Usage:
  python scripts/screen_llm.py OUT.csv [--ids S0001,S0002 | --ids-file ids.json | --all]
         [--batch 10] [--think] [--model gemma4:26b] [--host http://172.16.0.239:11434]

Reads records from review/search/merged.csv and writes SUGGESTIONS to OUT.csv
(id, decision, criterion, reason, ...). It never writes to screening_log.csv: every
decision there is made by a human. Records already in OUT.csv are skipped, so a long run can
be resumed. Decisions are biased towards "maybe": a wrong exclusion loses a paper for good,
a wrong inclusion only costs a minute at full-text stage.
"""
import argparse
import csv
import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CRITERIA = ["off_topic", "non_tls", "benign_only", "decryption", "secondary", "no_ml", "no_eval", "out_of_range"]

PROMPT = """You are screening titles and abstracts for a systematic review of MACHINE-LEARNING DETECTION OF
MALICIOUS TLS/HTTPS TRAFFIC. For each record decide include, exclude or maybe.

INCLUDE when the record plausibly meets ALL of:
- detects or classifies malicious, malware, botnet, command-and-control, intrusion or attack traffic;
- in TLS, HTTPS, SSL or "encrypted" network traffic (protocol not named still counts), without decrypting it;
- with a machine-learning, deep-learning or learned-fingerprint method and some quantitative evaluation.

EXCLUDE only when the title/abstract clearly shows one of these criteria:
- off_topic: not about network traffic security at all (e.g. images, text, e-mail content, biology, hardware)
- non_tls: only plaintext or non-TLS traffic (e.g. HTTP, DNS, IoT/industrial protocols) or only non-TLS
  encryption such as IPsec/VPN tunnels, with no TLS/HTTPS/encrypted-traffic results
- benign_only: only classifies benign applications, services, websites, devices or users (no malicious class)
- decryption: requires decrypting or intercepting TLS (man-in-the-middle, SSL inspection)
- secondary: survey, review, SoK, tutorial, editorial, erratum, retraction notice, book, or a record that is
  only a dataset or software release without detection experiments (record type is given as type=...)
- no_ml: no learned model (only rules, signatures, statistics without learning)
- no_eval: proposal or position paper without quantitative results
- out_of_range: published before 2019

MAYBE whenever you are unsure, the abstract is missing or too short, or the record is borderline
(e.g. encrypted traffic but unclear whether malicious, or a dataset paper with detection experiments).
When in doubt between exclude and maybe, choose maybe.

EVERY record needs a reason of at most 25 words, including include and maybe decisions (say what makes it
relevant or what is unclear). For include and maybe, leave criterion empty ("").

RECORDS:
{records}"""

SCHEMA = {
    "type": "object",
    "properties": {
        "decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "decision": {"type": "string", "enum": ["include", "exclude", "maybe"]},
                    "criterion": {"type": "string", "enum": [""] + CRITERIA},
                    "reason": {"type": "string"},
                },
                "required": ["id", "decision", "criterion", "reason"],
            },
        }
    },
    "required": ["decisions"],
}


def format_record(r: dict) -> str:
    abstract = r["abstract"].strip() if r.get("abstract_source", "search") != "none" else ""
    rtype = r.get("type_norm") or r["type"] or "unknown"
    return (f"[{r['id']}] year={r['year']} type={rtype} venue={r['venue'] or 'unknown'}\n"
            f"TITLE: {r['title']}\nABSTRACT: {abstract[:2500] or '(no abstract available)'}")


def call(host: str, model: str, prompt: str, think: bool) -> tuple[dict, dict]:
    options = {"temperature": 1.0, "top_k": 64, "top_p": 0.95} if think else {"temperature": 0}
    options["num_ctx"] = int(-(-(len(prompt) / 3.3 + (8000 if think else 2000)) // 2048) * 2048)
    body = {"model": model, "prompt": prompt, "stream": False, "format": SCHEMA, "think": think,
            "options": options}
    req = urllib.request.Request(f"{host}/api/generate", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        resp = json.loads(r.read())
    return json.loads(resp.get("response") or "{}"), resp


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    sel = ap.add_mutually_exclusive_group(required=True)
    sel.add_argument("--ids")
    sel.add_argument("--ids-file")
    sel.add_argument("--all", action="store_true")
    ap.add_argument("--batch", type=int, default=10)
    ap.add_argument("--think", action="store_true")
    ap.add_argument("--model", default="gemma4:26b")
    ap.add_argument("--host", default="http://172.16.0.239:11434")
    enriched = ROOT / "review" / "search" / "records.csv"  # abstracts filled + type_norm
    ap.add_argument("--merged", default=str(enriched if enriched.exists() else ROOT / "review" / "search" / "merged.csv"))
    a = ap.parse_args()

    records = {r["id"]: r for r in csv.DictReader(open(a.merged, encoding="utf-8"))}
    print(f"reading records from {a.merged}")
    if a.ids:
        ids = a.ids.split(",")
    elif a.ids_file:
        ids = json.loads(Path(a.ids_file).read_text())
    else:
        ids = list(records)

    out = Path(a.out)
    fields = ["id", "decision", "criterion", "reason", "model", "think", "batch_seconds"]
    done = set()
    if out.exists():
        done = {r["id"] for r in csv.DictReader(open(out, encoding="utf-8"))}
    todo = [i for i in ids if i not in done]
    new_file = not out.exists()
    f = open(out, "a", newline="", encoding="utf-8")
    w = csv.DictWriter(f, fieldnames=fields)
    if new_file:
        w.writeheader()

    for start in range(0, len(todo), a.batch):
        batch = todo[start : start + a.batch]
        pending = list(batch)
        for attempt in range(3):  # re-ask for records the model skipped or mangled
            prompt = PROMPT.format(records="\n\n".join(format_record(records[i]) for i in pending))
            t0 = time.time()
            ans, _ = call(a.host, a.model, prompt, a.think)
            secs = round(time.time() - t0, 1)
            got = {d["id"].strip("[] "): d for d in ans.get("decisions", []) if isinstance(d, dict)}
            for i in pending:
                if i in got:
                    d = got[i]
                    w.writerow({"id": i, "decision": d["decision"],
                                "criterion": d["criterion"] if d["decision"] == "exclude" else "",
                                "reason": d["reason"], "model": a.model, "think": a.think, "batch_seconds": secs})
            f.flush()
            pending = [i for i in pending if i not in got]
            if not pending:
                break
        for i in pending:
            w.writerow({"id": i, "decision": "maybe", "criterion": "", "reason": "MODEL GAVE NO ANSWER",
                        "model": a.model, "think": a.think, "batch_seconds": ""})
        print(f"{min(start + a.batch, len(todo))}/{len(todo)} records, last batch {secs}s, unanswered {len(pending)}")
    f.close()


if __name__ == "__main__":
    main()
