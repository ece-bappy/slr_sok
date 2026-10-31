"""Batch runner for agent-based extraction of 63 core papers.

This script prepares each paper's text and saves it to a staging directory,
so the agent can read and code each paper sequentially.

Directory layout (relative to project root D:\\new papers\\tls-sok):
  results/
    sonnet/          <- this run (Claude Sonnet 4.6)
      S3347.txt      <- prepared text (input)
      S3347.json     <- agent extraction output
    gemini38/        <- next run (Gemini 3.8)
    vote/            <- final majority-voted results

Usage:
    python scripts/batch_prepare.py          # prepare all 63 papers
    python scripts/batch_prepare.py --paper S3347  # single paper
"""
import sys
import json
import argparse
from pathlib import Path

SCRIPTS = Path(__file__).parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

from prepare_for_agent import prepare_paper

PDF_DIR = ROOT.parent / "papers" / "core"

# Output dirs
RESULTS_DIR = ROOT / "results"
SONNET_DIR  = RESULTS_DIR / "sonnet"
GEMINI_DIR  = RESULTS_DIR / "gemini38"
VOTE_DIR    = RESULTS_DIR / "vote"

for d in [SONNET_DIR, GEMINI_DIR, VOTE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Papers to verify (63 remaining, from CSV)
import pandas as pd
CSV = ROOT / "review" / "coding" / "core_67_papers_verification.csv"


def get_papers_to_process(run_dir: Path, specific: str = None) -> list[str]:
    df = pd.read_csv(CSV)
    not_verified = df[df["verification_status"] != "verified"]
    paper_ids = not_verified["paper_id"].unique().tolist()
    if specific:
        return [p for p in paper_ids if p == specific]
    # Skip papers already done
    return [p for p in paper_ids if not (run_dir / f"{p}.json").exists()]


def prepare_one(paper_id: str, force: bool = False) -> dict:
    txt_path = SONNET_DIR / f"{paper_id}.txt"
    pdf_path = PDF_DIR / f"{paper_id}.pdf"

    if not pdf_path.exists():
        return {"paper_id": paper_id, "status": "error", "error": f"PDF not found: {pdf_path}"}

    if not txt_path.exists() or force:
        text = prepare_paper(str(pdf_path))
        txt_path.write_text(text, encoding="utf-8")

    chars = len(txt_path.read_text(encoding="utf-8"))
    return {"paper_id": paper_id, "txt_path": str(txt_path), "chars": chars,
            "approx_tokens": chars // 4, "status": "ready"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--paper", default=None, help="Process single paper ID")
    ap.add_argument("--force", action="store_true", help="Re-extract even if .txt exists")
    a = ap.parse_args()

    papers = get_papers_to_process(SONNET_DIR, specific=a.paper)
    print(f"Papers to prepare: {len(papers)}")

    results = []
    for i, pid in enumerate(papers, 1):
        r = prepare_one(pid, force=a.force)
        results.append(r)
        status = r.get("status")
        chars = r.get("chars", 0)
        tokens = r.get("approx_tokens", 0)
        print(f"[{i:02d}/{len(papers)}] {pid}: {status} | {chars:,} chars (~{tokens:,} tokens)")

    total_tokens = sum(r.get("approx_tokens", 0) for r in results)
    print(f"\nTotal: {len(results)} papers, ~{total_tokens:,} tokens")
    print(f"Output dir: {SONNET_DIR}")

if __name__ == "__main__":
    main()
