"""Strict title/abstract screening pass (exclude as much as defensible) with Gemini or agy.

Usage:
  python scripts/screen_strict.py OUT.csv (--ids S0001,S0002 | --ids-file ids.json | --kept-by GEMMA.csv)
         [--judge gemini|agy] [--batch 20] [--model gemini-3.1-flash-lite]

--kept-by takes Gemma's first-pass output and screens every record Gemma did not exclude.
Writes SUGGESTIONS to OUT.csv (never to screening_log.csv). Resumable: ids already in OUT.csv
are skipped. The same PROMPT is used for every judge so their answers are comparable.
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
CRITERIA = ["off_topic", "non_tls", "benign_only", "decryption", "secondary", "no_ml", "no_eval",
            "not_main_focus", "out_of_range"]

PROMPT = """You are doing a STRICT title/abstract screening pass for a systematic review of machine-learning
DETECTION OF MALICIOUS TLS/HTTPS TRAFFIC. A first, lenient pass kept these records; now exclude every record
that does not clearly qualify. Only clearly qualifying primary studies should remain.

INCLUDE only if the title/abstract shows ALL of:
1. a primary study (new method, system, measurement or benchmark with experiments), not a survey or overview;
2. its MAIN subject is detecting or classifying malicious traffic (malware, botnet, C2, intrusion, attack,
   phishing or malicious servers) in network traffic;
3. that traffic is TLS, HTTPS, SSL or explicitly "encrypted" traffic, analysed without decrypting it, AND the
   evaluation data actually contains such traffic. Calling the work "encrypted traffic detection" is not enough:
   generic IDS benchmarks (UNSW-NB15, CIC-IDS2017/2018, NSL-KDD, KDD99, ToN_IoT, CICIoT...) or VPN/app
   classification datasets (e.g. ISCX VPN-nonVPN) do not count, unless the abstract says the encrypted/TLS
   flows were isolated or a TLS/HTTPS/malware-over-TLS dataset (e.g. CTU, MTA, CIRA-CIC-DoHBrw) is used;
4. the method uses machine learning, deep learning or a learned fingerprint/model;
5. some quantitative evaluation is reported or clearly implied.

EXCLUDE with the FIRST criterion that applies:
- off_topic: not about network-traffic security (images, text, e-mail content, URLs/web pages only, code,
  binaries, hardware, biology...)
- secondary: survey, review, SoK, tutorial, editorial, book, thesis summary, dataset or software release
- non_tls: traffic is plaintext or non-TLS only (HTTP, DNS, IoT/industrial protocols, generic NetFlow/IDS
  benchmarks such as KDD/NSL-KDD/UNSW-NB15 with no TLS/encrypted focus), or only IPsec/VPN/Tor
- benign_only: only identifies benign applications, services, websites, devices or users
- decryption: relies on decrypting or intercepting TLS
- no_ml: no learned model (rules, signatures, plain statistics)
- no_eval: no quantitative evaluation (position paper, proposal, framework description)
- not_main_focus: encrypted malicious traffic is only one minor case in a broader paper (e.g. a generic IDS
  that merely mentions encryption)
- out_of_range: published before 2019

MAYBE only if a single key criterion (usually 3, the traffic type or the evaluation data) is genuinely not
determinable from the title/abstract while the others clearly hold. Do not use maybe for weak or partial
relevance; exclude those.

MISSING ABSTRACT: a missing abstract is NEVER a reason to exclude (never use no_eval for it). Judge from the
title, venue and type: exclude only if the title itself clearly fails a criterion; include if the title
clearly meets criteria 2-4; otherwise maybe.

For every record give a reason of at most 25 words. criterion is "none" unless decision is exclude.
Return one decision per record.

RECORDS:
{records}"""

SCHEMA = {  # Gemini responseSchema (OpenAPI subset)
    "type": "OBJECT",
    "properties": {"decisions": {"type": "ARRAY", "items": {
        "type": "OBJECT",
        "properties": {
            "id": {"type": "STRING"},
            "decision": {"type": "STRING", "enum": ["include", "exclude", "maybe"]},
            "criterion": {"type": "STRING", "enum": ["none"] + CRITERIA},  # Gemini rejects "" in enums
            "reason": {"type": "STRING"},
        },
        "required": ["id", "decision", "criterion", "reason"]}}},
    "required": ["decisions"],
}


def format_record(r: dict) -> str:
    abstract = r["abstract"].strip() if r.get("abstract_source", "search") != "none" else ""
    return (f"[{r['id']}] year={r['year']} type={r.get('type_norm') or r['type'] or 'unknown'} "
            f"venue={r['venue'] or 'unknown'}\nTITLE: {r['title']}\n"
            f"ABSTRACT: {abstract[:2500] or '(no abstract available)'}")


def ask_gemini(prompt: str, model: str) -> list[dict]:
    resp = call_gemini(model, prompt, "high", None, SCHEMA)
    return json.loads(resp.get("response") or "{}").get("decisions", [])


def ask_agy(prompt: str, model: str) -> list[dict]:
    text = ("You have NO shell or file access; answer only. Return ONLY a JSON object "
            '{"decisions": [{"id": ..., "decision": ..., "criterion": ..., "reason": ...}]}.\n\n' + prompt)
    res = subprocess.run(["agy", "-p", text.replace('"', '\\"'), "--model", model, "--print-timeout", "900s",
                          "--output-format", "json"], capture_output=True, text=True, encoding="utf-8", timeout=1200)
    body = json.loads(res.stdout).get("response", "")
    return json.loads(re.search(r"\{.*\}", body, re.S).group(0)).get("decisions", [])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    sel = ap.add_mutually_exclusive_group(required=True)
    sel.add_argument("--ids")
    sel.add_argument("--ids-file")
    sel.add_argument("--kept-by")
    ap.add_argument("--judge", choices=["gemini", "agy"], default="gemini")
    ap.add_argument("--model", default=None, help="default gemini-3.1-flash-lite / gemini-3.8-flash-high (agy)")
    ap.add_argument("--batch", type=int, default=20)
    ap.add_argument("--records", default=str(ROOT / "review" / "search" / "records.csv"))
    a = ap.parse_args()
    model = a.model or ("gemini-3.1-flash-lite" if a.judge == "gemini" else "gemini-3.8-flash-high")

    records = {r["id"]: r for r in csv.DictReader(open(a.records, encoding="utf-8"))}
    if a.ids:
        ids = a.ids.split(",")
    elif a.ids_file:
        ids = json.loads(Path(a.ids_file).read_text())
    else:
        ids = [r["id"] for r in csv.DictReader(open(a.kept_by, encoding="utf-8")) if r["decision"] != "exclude"]

    out = Path(a.out)
    if out.exists():  # drop placeholder rows from failed calls so a resume retries them
        old = list(csv.DictReader(open(out, encoding="utf-8")))
        good = [r for r in old if r["reason"] != "NO VALID ANSWER"]
        if len(good) < len(old):
            with open(out, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(old[0].keys()))
                w.writeheader()
                w.writerows(good)
            print(f"removed {len(old) - len(good)} failed rows; retrying them", flush=True)
    done = {r["id"] for r in csv.DictReader(open(out, encoding="utf-8"))} if out.exists() else set()
    todo = [i for i in ids if i not in done]
    fields = ["id", "decision", "criterion", "reason", "judge"]
    new = not out.exists()
    f = open(out, "a", newline="", encoding="utf-8")
    w = csv.DictWriter(f, fieldnames=fields)
    if new:
        w.writeheader()
    for start in range(0, len(todo), a.batch):
        pending = todo[start : start + a.batch]
        for attempt in range(3):
            prompt = PROMPT.format(records="\n\n".join(format_record(records[i]) for i in pending))
            try:
                got = ask_gemini(prompt, model) if a.judge == "gemini" else ask_agy(prompt, model)
            except (Exception, SystemExit) as e:  # call_gemini raises SystemExit on HTTP errors
                print(f"  attempt {attempt + 1} failed: {e}", flush=True)
                got = []
            got = {d["id"].strip("[] "): d for d in got if isinstance(d, dict) and "id" in d}
            for i in pending:
                d = got.get(i)
                if d and d.get("decision") in ("include", "exclude", "maybe"):
                    w.writerow({"id": i, "decision": d["decision"],
                                "criterion": d.get("criterion", "").replace("none", "") if d["decision"] == "exclude" else "",
                                "reason": d.get("reason", ""), "judge": f"{a.judge}/{model}"})
            f.flush()
            pending = [i for i in pending if i not in got]
            if not pending:
                break
        for i in pending:
            w.writerow({"id": i, "decision": "maybe", "criterion": "", "reason": "NO VALID ANSWER",
                        "judge": f"{a.judge}/{model}"})
        print(f"{min(start + a.batch, len(todo))}/{len(todo)} done", flush=True)
    f.close()


if __name__ == "__main__":
    main()
