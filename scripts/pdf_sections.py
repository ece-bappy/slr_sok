"""Extract paper text from a PDF and drop sections that add noise for review coding.

Dropped: related work, conclusion, acknowledgments, ethics, references (and anything after
the references except appendices). A dropped section runs until the next heading with the
same or larger font style, so its subsections go with it.

Usage: python scripts/pdf_sections.py PAPER.pdf   (prints a report of kept/dropped sections)
"""
import re
import sys
from collections import Counter

import fitz  # PyMuPDF

DROP = re.compile(
    r"^(\d+(\.\d+)*\.?|[IVX]+\.?)?\s*("
    r"related\s+works?|background\s+and\s+related\s+work|prior\s+work|literature\s+review|"
    r"conclusions?(\s+and\s+future\s+work)?|concluding\s+remarks|summary\s+and\s+conclusions?|"
    r"acknowledge?ments?|ethic(s|al)(\s+considerations)?|"
    r"references|bibliography)\s*$",
    re.I,
)
KEEP_AFTER_REFS = re.compile(r"^([A-Z](\.\d+)*\.?)?\s*(appendix|appendices)\b", re.I)


def _lines(doc: fitz.Document) -> list[dict]:
    out = []
    for page in doc:
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                spans = [s for s in line["spans"] if s["text"].strip()]
                if not spans:
                    continue
                text = "".join(s["text"] for s in spans).strip()
                size = max(s["size"] for s in spans)
                bold = all(s["flags"] & 16 or "Bold" in s["font"] for s in spans)
                out.append({"text": text, "size": round(size, 1), "bold": bold})
    return out


def _merge_numbers(lines: list[dict]) -> list[dict]:
    """Join a lone section number line ("8", "IV.") with the heading line after it."""
    merged, i = [], 0
    while i < len(lines):
        cur = lines[i]
        if (i + 1 < len(lines) and re.fullmatch(r"(\d+(\.\d+)*\.?|[IVX]+\.?)", cur["text"])
                and len(lines[i + 1]["text"]) < 60):
            nxt = dict(lines[i + 1])
            nxt["text"] = f"{cur['text']} {nxt['text']}"
            merged.append(nxt)
            i += 2
            continue
        merged.append(cur)
        i += 1
    return merged


def _is_heading(ln: dict, body: float) -> bool:
    t = ln["text"]
    return len(t) < 70 and not t.endswith(".") and (ln["bold"] or ln["size"] > body + 0.4)


def extract(path: str) -> tuple[str, list[tuple[str, str, int]]]:
    """Return (kept_text, report) where report rows are (action, heading, chars)."""
    with fitz.open(path) as doc:
        lines = _merge_numbers(_lines(doc))
    body = Counter(ln["size"] for ln in lines).most_common(1)[0][0]

    kept, report = [], []
    dropping, drop_style, after_refs = False, None, False
    cur_head, cur_chars = "(start)", 0
    for ln in lines:
        heading = _is_heading(ln, body)
        style = (ln["size"], ln["bold"])
        if heading and DROP.match(ln["text"]):
            report.append(("keep" if not dropping else "drop", cur_head, cur_chars))
            dropping, drop_style, cur_head, cur_chars = True, style, ln["text"], 0
            if re.search(r"references|bibliography", ln["text"], re.I):
                after_refs = True
            continue
        if dropping and heading and ln["size"] >= drop_style[0] and (ln["bold"] or not drop_style[1]):
            # A same-level heading ends the dropped section, unless we are past the references.
            if not after_refs or KEEP_AFTER_REFS.match(ln["text"]):
                report.append(("drop", cur_head, cur_chars))
                dropping, cur_head, cur_chars = False, ln["text"], 0
        if dropping:
            cur_chars += len(ln["text"])
        else:
            kept.append(ln["text"])
            cur_chars += len(ln["text"])
            if heading and len(kept) > 1:
                pass
    report.append(("drop" if dropping else "keep", cur_head, cur_chars))
    return "\n".join(kept), report


if __name__ == "__main__":
    for p in sys.argv[1:]:
        text, rep = extract(p)
        dropped = sum(c for a, _, c in rep if a == "drop")
        print(f"== {p}\n   kept {len(text)} chars, dropped {dropped} chars")
        for action, head, chars in rep:
            if action == "drop":
                print(f"   DROP {head!r} ({chars} chars)")
