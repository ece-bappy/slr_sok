"""Title-only screening of records without an abstract, using agy (Antigravity CLI) as the judge.

Usage: python scripts/screen_titles_agy.py OUT.csv [--batch 20] [--model gemini-3.8-flash-high]

Selects records in review/search/records.csv with abstract_source == none that mention
TLS/HTTPS/SSL/encryption in the title (no_tls_term not flagged), sends them to agy in batches,
and writes SUGGESTIONS to OUT.csv (never to screening_log.csv). Resumable: ids already in OUT.csv
are skipped.
"""
import argparse
import csv
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PROMPT = """You have NO shell or file access in this session; do not try to run commands or edit files. Answer only.

You are screening records for a systematic review of MACHINE-LEARNING DETECTION OF MALICIOUS TLS/HTTPS
TRAFFIC. Only the TITLE (plus year, venue and type) is available; there is no abstract.

Decide for each record:
- include: the title clearly describes detecting or classifying malicious / malware / botnet / C2 /
  intrusion / attack traffic in TLS, HTTPS, SSL or encrypted network traffic with a learned method.
- exclude: the title clearly shows it is out of scope. Use one criterion: off_topic (not network-traffic
  security), non_tls (only plaintext or non-TLS protocols, or IPsec/VPN only), benign_only (classifies
  benign apps/services/websites only), decryption (needs TLS interception), secondary (survey, review,
  editorial, book, dataset or software release only), no_ml, out_of_range (before 2019).
- maybe: anything else. With only a title, choose maybe whenever relevance cannot be ruled out.

Return ONLY a JSON array, one object per record, in the same order:
[{{"id": "S0001", "decision": "include|exclude|maybe", "criterion": "", "reason": "max 20 words"}}]
criterion is "" unless decision is exclude.

RECORDS:
{records}"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--batch", type=int, default=20)
    ap.add_argument("--model", default="gemini-3.8-flash-high")
    a = ap.parse_args()

    rows = [r for r in csv.DictReader(open(ROOT / "review" / "search" / "records.csv", encoding="utf-8"))
            if r["abstract_source"] == "none" and "no_tls_term" not in r["flags"]]
    out = Path(a.out)
    done = {r["id"] for r in csv.DictReader(open(out, encoding="utf-8"))} if out.exists() else set()
    todo = [r for r in rows if r["id"] not in done]
    print(f"{len(rows)} title-only records, {len(todo)} to judge")
    fields = ["id", "title", "decision", "criterion", "reason", "judge"]
    new = not out.exists()
    f = open(out, "a", newline="", encoding="utf-8")
    w = csv.DictWriter(f, fieldnames=fields)
    if new:
        w.writeheader()

    for i in range(0, len(todo), a.batch):
        batch = todo[i : i + a.batch]
        recs = "\n".join(f"[{r['id']}] year={r['year']} type={r['type_norm']} venue={r['venue'] or 'unknown'} "
                         f"TITLE: {r['title']}" for r in batch)
        prompt = PROMPT.format(records=recs)
        # PowerShell/Windows argument quoting mangles bare double quotes; escape them for agy.
        res = subprocess.run(["agy", "-p", prompt.replace('"', '\\"'), "--model", a.model,
                              "--print-timeout", "600s", "--output-format", "json"],
                             capture_output=True, text=True, encoding="utf-8", timeout=900)
        try:
            meta = json.loads(res.stdout)
            text = meta.get("response", "")
            arr = json.loads(re.search(r"\[.*\]", text, re.S).group(0))
            got = {d["id"].strip("[] "): d for d in arr if isinstance(d, dict) and "id" in d}
        except Exception as e:  # keep going; unanswered records become maybe below
            print(f"  batch {i // a.batch + 1}: could not parse agy output ({e}); stderr: {res.stderr[:300]}")
            got = {}
        for r in batch:
            d = got.get(r["id"])
            if d and d.get("decision") in ("include", "exclude", "maybe"):
                w.writerow({"id": r["id"], "title": r["title"], "decision": d["decision"],
                            "criterion": d.get("criterion", "") if d["decision"] == "exclude" else "",
                            "reason": d.get("reason", ""), "judge": f"agy/{a.model}"})
            else:
                w.writerow({"id": r["id"], "title": r["title"], "decision": "maybe", "criterion": "",
                            "reason": "AGY GAVE NO VALID ANSWER", "judge": f"agy/{a.model}"})
        f.flush()
        print(f"  batch {i // a.batch + 1}: {len(got)}/{len(batch)} answered")
    f.close()


if __name__ == "__main__":
    main()
