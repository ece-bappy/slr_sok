"""Build the human final-screening workbook for the A/B records (rules: review/final_screening/rulebook.txt).

Usage: python scripts/make_final_screening_sheet.py [--force]
Writes review/final_screening/final_screening_325.xlsx. Refuses to overwrite an existing workbook
(it holds human decisions) unless --force is given.
"""
import csv
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "review" / "final_screening" / "final_screening_325.xlsx"
CODES = ["duplicate", "low_venue", "out_of_range", "not_english", "secondary", "off_topic", "non_tls",
         "benign_only", "decryption", "no_ml", "no_eval", "not_main_focus"]
FONT = "Arial"
YELLOW = PatternFill("solid", start_color="FFF2CC")
HEAD = PatternFill("solid", start_color="D9E1F2")
THIN = Border(bottom=Side(style="thin", color="BFBFBF"))

COLS = [  # header, width, wrap
    ("no", 5, False), ("bucket", 7, False), ("id", 7, False), ("year", 6, False), ("title", 45, True),
    ("abstract", 80, True), ("venue", 25, True), ("venue_rule", 10, False), ("link", 12, False),
    ("related_id", 9, False), ("gemma", 8, False), ("gemini_strict", 9, False), ("gemini_reason", 35, True),
    ("current_decision", 10, False), ("current_criterion", 13, False),
    ("final_decision", 11, False), ("exclusion_criterion", 15, False), ("my_note", 40, True),
]


def link(r: dict) -> str:
    if r["doi"]:
        return f"https://doi.org/{r['doi']}"
    if r["oa_url"]:
        return r["oa_url"]
    if r["arxiv_id"]:
        return f"https://arxiv.org/abs/{r['arxiv_id']}"
    return f"https://www.semanticscholar.org/paper/{r['s2_id']}" if r["s2_id"] else ""


def main() -> None:
    if OUT.exists() and "--force" not in sys.argv:
        raise SystemExit(f"{OUT} exists (may hold your decisions); pass --force to overwrite")
    recs = {r["id"]: r for r in csv.DictReader(open(ROOT / "review" / "search" / "records.csv", encoding="utf-8"))}
    sug = [r for r in csv.DictReader(open(ROOT / "review" / "screening_llm" / "combined_suggestions.csv",
                                          encoding="utf-8-sig"))
           if r["suggested_bucket"] in ("A_both_include", "B_check")]
    sug.sort(key=lambda r: (r["suggested_bucket"], r["year"], r["id"]))

    wb = Workbook()
    ws = wb.active
    ws.title = "Screening"
    for c, (h, w, _) in enumerate(COLS, 1):
        cell = ws.cell(1, c, h)
        cell.font = Font(name=FONT, bold=True)
        cell.fill = HEAD
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        ws.column_dimensions[cell.column_letter].width = w
    for n, s in enumerate(sug, 1):
        r = recs[s["id"]]
        a_bucket = s["suggested_bucket"] == "A_both_include"
        cur = "include" if a_bucket else s["gemini_strict"]
        abstract = r["abstract"] if r["abstract_source"] != "none" else "(no abstract - open the link)"
        url = link(r)
        vals = [n, "A" if a_bucket else "B", s["id"], int(r["year"]) if r["year"].isdigit() else r["year"],
                r["title"], abstract, r["venue"], s["venue_rule"], "open" if url else "", r["related_id"],
                s["gemma"], s["gemini_strict"], s["gemini_reason"], cur,
                s["gemini_criterion"] if cur == "exclude" else "", "", "", ""]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(n + 1, c, v)
            cell.font = Font(name=FONT, size=9)
            cell.alignment = Alignment(wrap_text=COLS[c - 1][2], vertical="top")
            cell.border = THIN
            if COLS[c - 1][0] in ("final_decision", "exclusion_criterion", "my_note"):
                cell.fill = YELLOW
        if url:
            lc = ws.cell(n + 1, 9)
            lc.hyperlink = url
            lc.font = Font(name=FONT, size=9, color="0563C1", underline="single")
        ws.row_dimensions[n + 1].height = 120
    last = len(sug) + 1
    col = {h: ws.cell(1, i).column_letter for i, (h, _, _) in enumerate(COLS, 1)}

    dv1 = DataValidation(type="list", formula1='"include,exclude"', allow_blank=True)
    dv2 = DataValidation(type="list", formula1=f'"{",".join(CODES)}"', allow_blank=True)
    ws.add_data_validation(dv1)
    ws.add_data_validation(dv2)
    dv1.add(f"{col['final_decision']}2:{col['final_decision']}{last}")
    dv2.add(f"{col['exclusion_criterion']}2:{col['exclusion_criterion']}{last}")
    ws.freeze_panes = "F2"
    ws.auto_filter.ref = f"A1:{col['my_note']}{last}"
    ws.cell(1, 14).comment = Comment("LLM suggestion: A = include (Gemma + strict Gemini); B = strict Gemini's "
                                     "decision. Advice only.", "tls-sok")

    # Summary: live counts of your decisions
    sm = wb.create_sheet("Summary")
    fd, ec, bk = (f"Screening!${col[k]}$2:${col[k]}${last}" for k in ("final_decision", "exclusion_criterion", "bucket"))
    rows = [("Records", f"=COUNTA(Screening!$C$2:$C${last})"),
            ("Decided", f"=COUNTA({fd})"),
            ("Still open", "=B2-B3"),
            ("include", f'=COUNTIF({fd},"include")'),
            ("exclude", f'=COUNTIF({fd},"exclude")'),
            ("exclude without a code (fix)", f'=COUNTIFS({fd},"exclude",{ec},"")'),
            ("include with a code (fix)", f'=COUNTIFS({fd},"include",{ec},"<>")'),
            ("A bucket included", f'=COUNTIFS({bk},"A",{fd},"include")'),
            ("B bucket included", f'=COUNTIFS({bk},"B",{fd},"include")'),
            ("Agreement with current_decision (decided rows)",
             f"=IFERROR(SUMPRODUCT(({fd}<>\"\")*({fd}=Screening!${col['current_decision']}$2:${col['current_decision']}${last}))/B3,0)")]
    sm["A1"], sm["B1"] = "Measure", "Value"
    for i, (k, f) in enumerate(rows, 2):
        sm.cell(i, 1, k)
        sm.cell(i, 2, f)
    sm.cell(len(rows) + 1, 2).number_format = "0.0%"
    base = len(rows) + 3
    sm.cell(base, 1, "Exclusions by code")
    for i, code in enumerate(CODES, base + 1):
        sm.cell(i, 1, code)
        sm.cell(i, 2, f'=COUNTIF({ec},"{code}")')
    for row in sm.iter_rows():
        for c in row:
            c.font = Font(name=FONT, bold=c.row in (1, base))
    sm.column_dimensions["A"].width = 46
    sm.column_dimensions["B"].width = 12

    lg = wb.create_sheet("Legend")
    lines = [
        ("How to use", ""),
        ("Rules", "review/final_screening/rulebook.txt (strict). Read it first."),
        ("Fill in", "Only the yellow columns on Screening: final_decision, exclusion_criterion, my_note."),
        ("final_decision", "include / exclude (drop-down). No maybe: check the paper, else exclude as unresolved."),
        ("exclusion_criterion", "Required for exclude; first code in rulebook section 3 that applies."),
        ("my_note", "Required when you decided from the paper (say where), for 'unresolved', venue overrides, "
                    "duplicates and when you disagree with current_decision."),
        ("link", "Click 'open' to go to the DOI / arXiv / Semantic Scholar page."),
        ("Summary sheet", "Counts update as you type; the two '(fix)' rows should end at 0."),
        ("", ""),
        ("Example row (format only)", ""),
        ("final_decision", "exclude"),
        ("exclusion_criterion", "non_tls"),
        ("my_note", "Only CIC-IDS2017, no TLS flows isolated; LLM said include."),
    ]
    for i, (k, v) in enumerate(lines, 1):
        lg.cell(i, 1, k).font = Font(name=FONT, bold=v == "" and k != "")
        lg.cell(i, 2, v).font = Font(name=FONT)
    lg.column_dimensions["A"].width = 26
    lg.column_dimensions["B"].width = 100

    wb.calculation.fullCalcOnLoad = True  # openpyxl stores no cached values; Excel computes them on open
    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)
    print(f"{len(sug)} records -> {OUT}")


if __name__ == "__main__":
    main()
