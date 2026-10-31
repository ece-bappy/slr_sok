"""Batch runner for 67 core papers extraction with 3 runs + majority voting (plan.md §4, Task 8).

Usage:
  python scripts/run_core_batch.py [--max-papers N] [--model MODEL] [--thinking LEVEL]

Features:
  - Iterates through the 67 core papers in order
  - Automatically skips runs/papers already completed in papers/llm_core/
  - Runs majority vote (vote_v2.py) as soon as all 3 runs for a paper complete
  - Updates review/coding/core_67_papers_verification.xlsx incrementally
  - Exits cleanly if daily quota is reached
"""
import argparse
import csv
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT.parent
SCRIPTS = ROOT / "scripts"

CORE_RANKS = ROOT / "review" / "ranks" / "core_ranks.csv"
PDF_DIR = BASE / "papers" / "core"
OUT_DIR = BASE / "papers" / "llm_core"
OUT_DIR.mkdir(parents=True, exist_ok=True)

RUNS = [1, 2, 3]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-papers", type=int, default=0, help="Maximum new papers to process (0 = all)")
    parser.add_argument("--model", default="gemini-3.1-flash-lite")
    parser.add_argument("--thinking-level", default="high")
    args = parser.parse_args()

    core = [r for r in csv.DictReader(open(CORE_RANKS, encoding="utf-8")) if r.get("rule_A_strict") == "yes"]
    core.sort(key=lambda x: (x["year"], x["id"]))

    papers_to_do = []
    for c in core:
        pid = c["id"]
        pdf_path = PDF_DIR / f"{pid}.pdf"
        if not pdf_path.exists():
            print(f"Warning: PDF missing for {pid}: {pdf_path}")
            continue
        voted_file = OUT_DIR / f"{pid}__v2vote.json"
        runs_done = [OUT_DIR / f"{pid}__v2_r{r}.json" for r in RUNS]
        if not voted_file.exists() or not all(p.exists() for p in runs_done):
            papers_to_do.append((pid, pdf_path))

    total_core = len(core)
    already_voted = total_core - len(papers_to_do)
    print(f"Core papers total: {total_core} | Already voted: {already_voted} | To extract: {len(papers_to_do)}")

    if args.max_papers > 0:
        papers_to_do = papers_to_do[:args.max_papers]
        print(f"Limiting to first {len(papers_to_do)} papers this batch.")

    if not papers_to_do:
        print("All papers already extracted and voted!")
        return

    processed_papers = 0
    for p_idx, (pid, pdf_path) in enumerate(papers_to_do, 1):
        print(f"\n=======================================================", flush=True)
        print(f"[{p_idx}/{len(papers_to_do)}] Core Paper {pid} ({pdf_path.name})", flush=True)
        print(f"=======================================================", flush=True)

        paper_error = False
        for r in RUNS:
            out_file = OUT_DIR / f"{pid}__v2_r{r}.json"
            if out_file.exists():
                print(f"  Run {r}: SKIP ({out_file.name} already exists)", flush=True)
                continue

            print(f"  Run {r}: START at {time.strftime('%H:%M:%S')} -> {out_file.name}", flush=True)
            cmd = [
                sys.executable, "-u",
                str(SCRIPTS / "extract_v2.py"),
                str(pdf_path),
                str(out_file),
                "--model", args.model,
                "--thinking-level", args.thinking_level
            ]
            t0 = time.time()
            res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
            dur = round(time.time() - t0, 1)

            if res.returncode == 0:
                print(f"  Run {r}: DONE in {dur}s", flush=True)
                for line in res.stdout.strip().splitlines():
                    if line.startswith("{"):
                        print(f"    {line}", flush=True)
            else:
                print(f"  Run {r}: ERROR (code {res.returncode}) after {dur}s", flush=True)
                print(f"STDOUT:\n{res.stdout}", flush=True)
                print(f"STDERR:\n{res.stderr}", flush=True)
                paper_error = True
                if "quota" in res.stderr.lower() or "resource_exhausted" in res.stderr.lower() or "429" in res.stderr:
                    print("Quota exhaustion detected. Halting batch runner gracefully.", flush=True)
                    return
                break

        if not paper_error:
            # Check if all 3 runs exist to vote
            all_runs = [OUT_DIR / f"{pid}__v2_r{r}.json" for r in RUNS]
            if all(p.exists() for p in all_runs):
                print(f"  Voting across 3 runs for {pid}...", flush=True)
                vote_cmd = [
                    sys.executable, "-u",
                    str(SCRIPTS / "vote_v2.py"),
                    str(OUT_DIR),
                    "v2",
                    "v2vote"
                ]
                subprocess.run(vote_cmd, check=True)
                
                # Update verification sheet incrementally
                print(f"  Updating verification sheet...", flush=True)
                sheet_cmd = [
                    sys.executable, "-u",
                    str(SCRIPTS / "make_core_verification_sheet.py")
                ]
                subprocess.run(sheet_cmd, check=True)
                processed_papers += 1

    print(f"\nBatch finished! Processed {processed_papers} papers.", flush=True)

if __name__ == "__main__":
    main()
