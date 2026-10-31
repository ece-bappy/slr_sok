"""Turn review/fulltext/recheck_c3.csv into a review workbook for the human decision.

Usage: python scripts/make_recheck_sheet.py [--force]
Adds rule_flag: an LLM 'include' whose TLS evidence rests only on generic or mixed datasets (rulebook R1/R2)
and where the paper did not isolate TLS flows, or whose quotes could not all be verified in the PDF.
Writes review/fulltext/recheck_c3.xlsx (refuses to overwrite without --force: it holds your decisions).
"""
import csv
import re
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "review" / "fulltext" / "recheck_c3.csv"
OUT = ROOT / "review" / "fulltext" / "recheck_c3.xlsx"
MIXED = re.compile(r"(cic-?ids|ids ?201[78]|cse-cic|unsw|nsl-kdd|kdd|ton.?iot|ciciot|cic.?iot|bot-?iot|iot-23|"
                   r"usts?c-?tfc|usts?c-malware|netml|iscx|cic-?andmal|cic-?ddos|kitsune|medbiot)", re.I)
CODES = ["duplicate", "low_venue", "out_of_range", "not_english", "secondary", "off_topic", "non_tls",
         "benign_only", "decryption", "no_ml", "no_eval", "not_main_focus"]
COLS = [("id", 7), ("title", 40), ("pdf", 8), ("llm_suggestion", 10), ("llm_criterion", 10), ("rule_flag", 34),
        ("datasets", 70), ("tls_flows_isolated", 9), ("tls_isolation_quote", 40), ("main_task", 30),
        ("rule_applied", 8), ("llm_reason", 40), ("quotes_verified", 8), ("tls_terms", 22), ("tls_datasets", 22),
        ("generic_benchmarks", 22), ("your_decision", 11), ("your_criterion", 14), ("your_note", 40)]


def flag(r: dict) -> str:
    if r["llm_suggestion"].startswith("(not run"):
        return "no LLM pass (blind-validation candidate): read the dataset section yourself"
    out = []
    if r["llm_suggestion"] == "include":
        tls_ds = re.findall(r"(?:^| \| )([^\[]+) \[tls=yes", r["datasets"])
        if tls_ds and all(MIXED.search(d) for d in tls_ds) and r["tls_flows_isolated"] != "yes":
            out.append("R1/R2: TLS only via generic/mixed datasets, flows not isolated")
        if not tls_ds:
            out.append("no dataset marked TLS")
    n, m = (r["quotes_verified"] or "0/0").split("/")
    if n != m:
        out.append(f"only {n}/{m} quotes verbatim")
    return "; ".join(out)


def main() -> None:
    if OUT.exists() and "--force" not in sys.argv:
        raise SystemExit(f"{OUT} exists (may hold your decisions); pass --force to overwrite")
    rows = list(csv.DictReader(open(SRC, encoding="utf-8-sig")))
    wb = Workbook()
    ws = wb.active
    ws.title = "Recheck"
    for c, (h, wdt) in enumerate(COLS, 1):
        cell = ws.cell(1, c, h)
        cell.font = Font(name="Arial", bold=True)
        cell.fill = PatternFill("solid", start_color="D9E1F2")
        ws.column_dimensions[cell.column_letter].width = wdt
    yellow = PatternFill("solid", start_color="FFF2CC")
    for i, r in enumerate(rows, 2):
        r = {**r, "rule_flag": flag(r), "pdf": "open"}
        for c, (h, _) in enumerate(COLS, 1):
            cell = ws.cell(i, c, r.get(h, ""))
            cell.font = Font(name="Arial", size=9)
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            if h.startswith("your_"):
                cell.fill = yellow
        pdf = ws.cell(i, 3)
        pdf.hyperlink = str(ROOT.parent / "papers" / "core" / f"{r['id']}.pdf")
        pdf.font = Font(name="Arial", size=9, color="0563C1", underline="single")
        ws.row_dimensions[i].height = 110
    last = len(rows) + 1
    dv1 = DataValidation(type="list", formula1='"include,exclude"', allow_blank=True)
    dv2 = DataValidation(type="list", formula1=f'"{",".join(CODES)}"', allow_blank=True)
    ws.add_data_validation(dv1)
    ws.add_data_validation(dv2)
    dv1.add(f"Q2:Q{last}")
    dv2.add(f"R2:R{last}")
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:S{last}"
    wb.save(OUT)
    print(f"{len(rows)} rows -> {OUT}")
    for r in rows:
        f = flag(r)
        if f:
            print(r["id"], r["llm_suggestion"], "|", f)


if __name__ == "__main__":
    main()
