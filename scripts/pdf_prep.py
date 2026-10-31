"""Prepare a paper PDF for LLM coding (plan.md §4, extraction input rules 2-4).

prepare(path) returns a Paper with:
  body        cleaned method/data/experiment text (pdf_sections drops related work, conclusion,
              acknowledgements and references; keeps ethics, availability statements, appendices)
  tables      every table PyMuPDF finds, as Markdown with its page number
  full        cleaned text of the whole PDF incl. references (for quote checks and link scans)
  refs        {number: reference entry} parsed from the reference list (numbered styles only)
  parts       body+tables split into chunks of at most MAX_CHARS (normally one part)
Cleaning: NFKC (expands ligatures such as ﬁ ﬀ ﬃ), joins words hyphenated across lines, collapses
spaces. The same cleaning is applied to quotes before they are checked.
"""
import re
import unicodedata
from dataclasses import dataclass, field

import fitz  # PyMuPDF

from pdf_sections import extract as extract_sections

MAX_CHARS = 300_000  # ~75k tokens; longer papers are split into parts and logged
MAX_TABLE_CHARS = 40_000


def clean(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"([a-z])-\s*\n\s*([a-z])", r"\1\2", s)  # hyphenated line breaks (lowercase only)
    s = re.sub(r"[ \t ]+", " ", s)
    return re.sub(r"\n\s*\n+", "\n", s)


@dataclass
class Paper:
    path: str
    body: str
    tables: str
    full: str
    refs: dict
    parts: list = field(default_factory=list)
    log: list = field(default_factory=list)


def _tables(doc: fitz.Document) -> str:
    out, total = [], 0
    for pno, page in enumerate(doc, 1):
        try:
            found = page.find_tables()
        except Exception:  # table finder can fail on odd pages; text is still in the body
            continue
        for t in found.tables:
            md = clean(t.to_markdown() or "")
            if md.count("|") < 6:  # not a real table
                continue
            block = f"[Table on page {pno}]\n{md}"
            if total + len(block) > MAX_TABLE_CHARS:
                return "\n\n".join(out + ["[further tables omitted: limit reached]"])
            out.append(block)
            total += len(block)
    return "\n\n".join(out)


def _references(full: str) -> dict:
    """Numbered reference entries: '[12] ...' or '12. ...' at line start after the last References heading."""
    heads = list(re.finditer(r"\n\s*(references|bibliography)\s*\n", full, re.I))
    if not heads:
        return {}
    tail = full[heads[-1].end():]
    entries = {}
    for m in re.finditer(r"(?m)^\s*\[(\d{1,3})\]\s*(.+?)(?=^\s*\[\d{1,3}\]|\Z)", tail, re.S):
        entries[int(m.group(1))] = " ".join(m.group(2).split())
    if len(entries) < 3:  # try "12. Author" numbering
        entries = {}
        for m in re.finditer(r"(?m)^\s*(\d{1,3})\.\s+(.+?)(?=^\s*\d{1,3}\.\s|\Z)", tail, re.S):
            entries[int(m.group(1))] = " ".join(m.group(2).split())
    return entries


def prepare(path: str) -> Paper:
    with fitz.open(path) as doc:
        full = clean("\n".join(page.get_text() for page in doc))
        tables = _tables(doc)
    body_raw, report = extract_sections(path)
    body = clean(body_raw)
    p = Paper(path=path, body=body, tables=tables, full=full, refs=_references(full))
    p.log.append(f"sections dropped: {[h for act, h, _ in report if act == 'drop']}")
    text = body + ("\n\nTABLES (extracted from the PDF):\n" + tables if tables else "")
    if len(text) <= MAX_CHARS:
        p.parts = [text]
    else:
        p.parts = [text[i : i + MAX_CHARS] for i in range(0, len(text), MAX_CHARS)]
        p.log.append(f"input split into {len(p.parts)} parts ({len(text)} chars)")
    return p


if __name__ == "__main__":
    import sys

    for f in sys.argv[1:]:
        p = prepare(f)
        print(f"== {f}: body {len(p.body)} chars, tables {len(p.tables)} chars, refs {len(p.refs)}, "
              f"parts {len(p.parts)}")
        for line in p.log:
            print("  ", line)
