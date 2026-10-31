"""Code papers with an agy agent model (as the results/gemini38 core run did), one paper per agy call.

Usage: python scripts/run_agent_coding.py RUN_DIR PAPER_ID [PAPER_ID ...] [--model gemini-3.8-flash-high]
Expects RUN_DIR/<id>.txt (from prepare_for_agent.py). The agent reads the coding rulebook and the paper text
from disk and writes RUN_DIR/<id>.json in the save_result.py format; the file is then checked with
save_result.validate(). The agent gets no shell access.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from save_result import REQUIRED_FIELDS, validate

ROOT = Path(__file__).resolve().parent.parent

PROMPT = """You have NO shell access and must not run commands. Use only file reading and writing.
Task: code one research paper for a systematic review, exactly as a human coder would.
1. Read the coding rulebook: {rulebook}
2. Read the paper text: {paper}
3. Write ONE file, {out}, containing only JSON of this form:
{{"paper_id": "{pid}", "fields": {{"<field>": {{"value": <value>, "evidence": "<one verbatim passage from the paper>",
"evidence_source": "text|table|figure|none"}}, ...}}}}
Fields, in this order: {fields}.
Value types: datasets_evaluated = list of {{"name": ..., "role": "train|test|train_and_test|unclear", "quote": ...}};
label_source, features_used, feature_groups, fingerprints_used, tls_versions_stated, split_protocols, shortcut_check,
metrics = lists; all other fields = one string. Use only the allowed values given in the rulebook.
Evidence must be copied character-for-character from the paper text (no "...", no paraphrase); use "" with
evidence_source "none" only for none/not_stated/not_applicable answers.
Do not write any other file."""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("ids", nargs="+")
    ap.add_argument("--model", default="gemini-3.8-flash-high")
    a = ap.parse_args()
    run_dir = Path(a.run_dir).resolve()
    rulebook = ROOT / "review" / "coding" / "coding_rulebook.txt"
    for pid in a.ids:
        out = run_dir / f"{pid}.json"
        if out.exists():
            print(f"{pid}: exists, skipped")
            continue
        prompt = PROMPT.format(rulebook=rulebook, paper=run_dir / f"{pid}.txt", out=out, pid=pid,
                               fields=", ".join(REQUIRED_FIELDS))
        for attempt in (1, 2):
            res = subprocess.run(["agy", "-p", prompt.replace('"', '\\"'), "--model", a.model, "--mode", "accept-edits",
                                  "--print-timeout", "1200s", "--output-format", "json", "--add-dir", str(ROOT),
                                  "--add-dir", str(ROOT.parent / "papers")],  # agent may open the PDF itself
                                 cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=1500)
            if out.exists():
                try:
                    data = json.loads(out.read_text(encoding="utf-8"))
                except json.JSONDecodeError as e:
                    print(f"{pid}: invalid JSON ({e}), retrying")
                    out.unlink()
                    continue
                data.update(run="gemini38_validation", model=a.model)
                data["validation_warnings"] = validate(data)
                out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                print(f"{pid}: ok, {len(data['validation_warnings'])} warnings")
                break
            print(f"{pid}: no output (attempt {attempt}): {res.stdout[-300:]} {res.stderr[-300:]}")


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
