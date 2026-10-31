"""Prepare a paper's text for direct agent (LLM-as-coder) extraction.

Strategy:
  - Body text: drop Related Work, Conclusion, Acknowledgements (pdf_sections.py)
  - Tables: keep all (results/datasets often in tables)
  - References section: dropped as prose, BUT:
      * All bare URLs found in the kept body are included
      * Any reference [N] cited in a sentence containing artifact/availability words
        is resolved and its URL included (handles "available at [47]")
      * Repository URLs from all references are listed (for code/data_released)
  - Output: structured plain text block optimised for agent reading

Usage:
    python scripts/prepare_for_agent.py PAPER.pdf [--out OUT.txt]
    Returns: cleaned text string (also importable as prepare_paper(path) -> str)
"""
import re
import sys
import unicodedata
from pathlib import Path

# Add scripts dir to path so we can reuse project modules
sys.path.insert(0, str(Path(__file__).parent))

import fitz  # PyMuPDF
from pdf_sections import extract as extract_sections
from artifact_links import find_links
from pdf_prep import Paper, clean, _tables, _references

NOT_RELEASED = re.compile(
    r"(upon|on)\s+(reasonable\s+)?request|will\s+be\s+(made\s+)?(publicly\s+)?(available|released)|"
    r"available\s+(from\s+the\s+authors?|on\s+demand)", re.I
)

MAX_CHARS = 120_000  # generous ceiling; most papers <60k after pruning


def prepare_paper(pdf_path: str) -> str:
    """
    Return a clean, token-efficient text block for agent extraction.
    Sections dropped: Related Work, Conclusion, Acknowledgements, References prose.
    Sections kept: everything else + tables + resolved artifact links.
    """
    path = str(pdf_path)

    # --- 1. Full PDF text (for link/reference scanning) ---
    with fitz.open(path) as doc:
        full_raw = "\n".join(page.get_text() for page in doc)
        tables_md = _tables(doc)

    full = clean(unicodedata.normalize("NFKC", full_raw))
    refs = _references(full)

    # --- 2. Body text with dropped sections ---
    body_raw, report = extract_sections(path)
    body = clean(unicodedata.normalize("NFKC", body_raw))

    # --- 3. Artifact links (URLs + resolved [N] citations) ---
    paper = Paper(path=path, body=body, tables=tables_md, full=full, refs=refs, parts=[body])
    link_data = find_links(paper)
    links = link_data.get("links", [])
    not_released = link_data.get("not_released_statements", [])

    # --- 4. Format links section ---
    link_lines = []
    if links:
        for lk in links:
            ctx = lk.get("context", "").replace("\n", " ").strip()[:200]
            link_lines.append(f"  [{lk['found_in']}] {lk['url']}\n    CONTEXT: {ctx}")
    if not_released:
        for s in not_released:
            link_lines.append(f"  [NOT-RELEASED STATEMENT] {s[:200]}")

    # --- 5. Section drop report (compact) ---
    drop_report = "; ".join(
        f"DROPPED:{h!r}" for act, h, c in report if act == "drop" and c > 50
    )

    # --- 6. Assemble final text ---
    parts = []
    parts.append("=" * 70)
    parts.append(f"PAPER: {Path(path).stem}")
    parts.append(f"Sections removed: {drop_report or 'none detected'}")
    parts.append("=" * 70)
    parts.append("")
    parts.append(body[:MAX_CHARS])

    if tables_md.strip():
        parts.append("")
        parts.append("--- TABLES (extracted from PDF) ---")
        parts.append(tables_md[:20_000])

    if link_lines:
        parts.append("")
        parts.append("--- ARTIFACT LINKS & AVAILABILITY (found in paper) ---")
        parts.extend(link_lines)

    return "\n".join(parts)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    text = prepare_paper(a.pdf)
    print(f"Chars: {len(text)}, approx tokens: {len(text)//4}")
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
        print(f"Written to {a.out}")
    else:
        print(text[:3000])
        print("... [truncated, use --out to save full text]")
