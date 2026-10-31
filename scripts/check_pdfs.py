"""Check that each downloaded full text is a readable PDF of the right paper.

Usage: python scripts/check_pdfs.py
For every row of review/fulltext/download_list.csv: opens papers/core/<id>.pdf, counts pages and
extractable text, and checks how many of the title's words appear on the first two pages.
Writes review/fulltext/pdf_check.csv; status is ok, check_title (low title match: maybe the wrong
paper, a cover page or a preprint with a different title), no_text (scanned/image PDF) or broken.
"""
import csv
import re
from pathlib import Path

import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT.parent / "papers" / "core"
STOP = {"a", "an", "the", "of", "for", "and", "in", "on", "with", "to", "by", "via", "using", "based", "from", "at"}


def words(s: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP and len(w) > 2}


def main() -> None:
    rows = list(csv.DictReader(open(ROOT / "review" / "fulltext" / "download_list.csv", encoding="utf-8-sig")))
    out = []
    for r in rows:
        p = DEST / f"{r['id']}.pdf"
        rec = {"id": r["id"], "pages": "", "chars": "", "title_match": "", "status": "", "title": r["title"]}
        try:
            doc = fitz.open(p)
            text = "".join(pg.get_text() for pg in doc)
            head = " ".join(doc[i].get_text() for i in range(min(2, len(doc))))
            tw = words(r["title"])
            match = len(tw & words(head)) / len(tw) if tw else 0
            rec.update(pages=len(doc), chars=len(text), title_match=f"{match:.2f}")
            rec["status"] = "no_text" if len(text) < 2000 else ("check_title" if match < 0.7 else "ok")
        except Exception as e:  # unreadable or not a PDF
            rec["status"] = f"broken: {e}"
        out.append(rec)
    with open(ROOT / "review" / "fulltext" / "pdf_check.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    from collections import Counter
    print(Counter(x["status"].split(":")[0] for x in out))
    for x in out:
        if x["status"] != "ok":
            print(x["id"], x["status"], "pages", x["pages"], "match", x["title_match"], "|", x["title"][:80])


if __name__ == "__main__":
    main()
