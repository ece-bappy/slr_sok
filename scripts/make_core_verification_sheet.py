"""Build and incrementally update the 67-Paper Core Set Verification Sheet (plan.md §4, Task 8).

Generates:
  - review/coding/core_67_papers_verification.csv
  - review/coding/core_67_papers_verification.xlsx

Features:
  - Populates LLM draft values, verbatim quotes, quote matches, votes, and review flags from papers/llm_core/
  - Pre-populates the 4 validation papers already verified by the user in Task 6 (blind_validation_sheet.csv)
  - Preserves any existing human edits in previous versions of the sheet
  - Categorizes status: 'verified', 'ready_for_review', or 'pending_extraction'
"""
import csv
import json
from pathlib import Path
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT.parent

CORE_RANKS = ROOT / "review" / "ranks" / "core_ranks.csv"
RECORDS_CSV = ROOT / "review" / "search" / "records.csv"
BLIND_VALIDATION = ROOT / "review" / "coding" / "blind_validation_sheet.csv"
LLM_CORE_DIR = BASE / "papers" / "llm_core"

OUT_CSV = ROOT / "review" / "coding" / "core_67_papers_verification.csv"
OUT_XLSX = ROOT / "review" / "coding" / "core_67_papers_verification.xlsx"

FIELDS_ORDER = [
    ("datasets_evaluated", "data sources as named in the paper with role train/test/train_and_test for each"),
    ("label_source", "sandbox|blocklist_cert|blocklist_ja3|ids_alerts|dataset_provided|manual|generated|other (list)"),
    ("label_feature_overlap", "yes|no|unclear|not_applicable"),
    ("features_used", "short phrases (list)"),
    ("feature_groups", "G1|G2|G3|G4|G5 (list)"),
    ("cert_fields_read", "yes|no|not_applicable"),
    ("fingerprints_used", "none|JA3|JA3S|JA4|JA4S|other (list)"),
    ("tls_versions_stated", "1.0|1.1|1.2|1.3|not_stated (list)"),
    ("ech_considered", "yes|no"),
    ("model_family", "short text"),
    ("split_protocols", "random|stratified_random|per_packet|host_grouped|temporal|cross_dataset|not_applicable (list)"),
    ("main_split", "one of the split values"),
    ("easy_vs_hard_reported", "yes|no|not_applicable"),
    ("shortcut_check", "none|identifier_removal|ablation|probe|other (list)"),
    ("metrics", "list"),
    ("granularity", "packet|flow|session|host"),
    ("first_n_packets", "N + unit, or whole flow"),
    ("cost_reported", "none|inference_only|end_to_end"),
    ("hardware", "timing hardware or none"),
    ("code_released", "yes|no"),
    ("data_released", "yes|no"),
]

def format_val(val):
    if isinstance(val, list):
        if all(isinstance(x, dict) for x in val):
            return "; ".join(f"{x.get('canonical') or x.get('name')} ({x.get('role', 'train_and_test')})" for x in val)
        return "; ".join(str(x) for x in val)
    return str(val) if val is not None else ""

def main():
    rec = {r["id"]: r for r in csv.DictReader(open(RECORDS_CSV, encoding="utf-8"))}
    core = [r for r in csv.DictReader(open(CORE_RANKS, encoding="utf-8")) if r.get("rule_A_strict") == "yes"]
    core.sort(key=lambda x: (x["year"], x["id"]))

    # Load existing human validation from Task 6
    human_val = {}
    if BLIND_VALIDATION.exists():
        for r in csv.DictReader(open(BLIND_VALIDATION, encoding="utf-8")):
            if r.get("paper_id") and r.get("field"):
                human_val[(r["paper_id"], r["field"])] = r

    # Load any existing edits from previous sheet to preserve human work
    existing_edits = {}
    if OUT_CSV.exists():
        for r in csv.DictReader(open(OUT_CSV, encoding="utf-8-sig")):
            k = (r["paper_id"], r["field"])
            existing_edits[k] = {
                "verified_value": r.get("verified_value", ""),
                "agree": r.get("agree", ""),
                "user_page": r.get("user_page", ""),
                "user_quote": r.get("user_quote", ""),
                "user_note": r.get("user_note", ""),
                "verification_status": r.get("verification_status", "")
            }

    rows = []
    for c in core:
        pid = c["id"]
        r = rec.get(pid, {})
        year = c["year"]
        kind = c["kind"]
        venue = c["venue"]
        title = r.get("title", "")
        pdf_path = f"papers/core/{pid}.pdf"

        # Check for voted LLM extraction
        voted_file = LLM_CORE_DIR / f"{pid}__v2vote.json"
        llm_data = {}
        if voted_file.exists():
            try:
                llm_data = json.loads(voted_file.read_text(encoding="utf-8")).get("fields", {})
            except Exception as e:
                print(f"Error reading {voted_file}: {e}")

        for field, allowed in FIELDS_ORDER:
            k = (pid, field)
            f_data = llm_data.get(field, {})
            
            raw_val = f_data.get("value")
            llm_val = format_val(raw_val) if raw_val is not None else ""
            evidence = str(f_data.get("evidence", ""))
            source = str(f_data.get("evidence_source", ""))
            q_match = f_data.get("quote_match")
            match_str = f"{q_match:.3f}" if isinstance(q_match, (int, float)) else ""
            flags = "; ".join(f_data.get("review_flags", []))
            votes = str(f_data.get("votes", ""))

            # Default status
            status = "ready_for_review" if voted_file.exists() else "pending_extraction"
            ver_val = llm_val
            agree = ""
            user_page = ""
            user_quote = ""
            user_note = ""

            # Check if user already coded this in Task 6 blind validation
            if k in human_val:
                hv = human_val[k]
                ver_val = hv.get("your_value", "")
                user_page = hv.get("page", "")
                user_quote = hv.get("quote", "")
                user_note = hv.get("note", "")
                agree = "yes" if ver_val.strip().lower() == llm_val.strip().lower() else "discrepancy_resolved"
                status = "verified"

            # Check if user previously edited this in an earlier run of the sheet
            elif k in existing_edits and existing_edits[k]["verified_value"]:
                ed = existing_edits[k]
                ver_val = ed["verified_value"]
                agree = ed["agree"]
                user_page = ed["user_page"]
                user_quote = ed["user_quote"]
                user_note = ed["user_note"]
                status = ed["verification_status"] or "verified"

            rows.append({
                "paper_id": pid,
                "year": year,
                "kind": kind,
                "venue": venue,
                "title": title,
                "pdf_path": pdf_path,
                "field": field,
                "allowed_values": allowed,
                "llm_draft_value": llm_val,
                "llm_evidence_quote": evidence,
                "evidence_source": source,
                "quote_match": match_str,
                "review_flags": flags,
                "votes": votes,
                "verified_value": ver_val,
                "agree": agree,
                "user_page": user_page,
                "user_quote": user_quote,
                "user_note": user_note,
                "verification_status": status
            })

    # Write CSV
    fieldnames = [
        "paper_id", "year", "kind", "venue", "title", "pdf_path", "field", "allowed_values",
        "llm_draft_value", "llm_evidence_quote", "evidence_source", "quote_match", "review_flags", "votes",
        "verified_value", "agree", "user_page", "user_quote", "user_note", "verification_status"
    ]
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {OUT_CSV}")

    # Write XLSX
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Core67_Verification"

    header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    verified_fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid") # light green
    ready_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")    # light yellow
    flagged_fill = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")  # light orange
    pending_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")  # light gray
    border_thin = Side(border_style="thin", color="D9D9D9")
    border = Border(left=border_thin, right=border_thin, top=border_thin, bottom=border_thin)

    ws.append(fieldnames)
    for col_num in range(1, len(fieldnames) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for row_idx, r in enumerate(rows, 2):
        row_data = [r[col] for col in fieldnames]
        ws.append(row_data)
        status = r["verification_status"]
        flags = r["review_flags"]
        
        for col_idx in range(1, len(fieldnames) + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.border = border
            cell.font = Font(name="Calibri", size=10)
            
            # Fill color based on status and user input columns
            fname = fieldnames[col_idx - 1]
            if fname in ["verified_value", "agree", "user_page", "user_quote", "user_note"]:
                if status == "verified":
                    cell.fill = verified_fill
                else:
                    cell.fill = PatternFill(start_color="EBF1F5", end_color="EBF1F5", fill_type="solid") # subtle blue-gray input highlight
            else:
                if status == "verified":
                    cell.fill = verified_fill
                elif flags:
                    cell.fill = flagged_fill
                elif status == "ready_for_review":
                    cell.fill = ready_fill
                else:
                    cell.fill = pending_fill

            if fname in ["paper_id", "year", "kind", "evidence_source", "quote_match", "votes", "agree", "user_page", "verification_status"]:
                cell.alignment = Alignment(horizontal="center", vertical="top")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)

    col_widths = {
        "A": 10, # paper_id
        "B": 8,  # year
        "C": 12, # kind
        "D": 22, # venue
        "E": 30, # title
        "F": 22, # pdf_path
        "G": 20, # field
        "H": 30, # allowed_values
        "I": 25, # llm_draft_value
        "J": 40, # llm_evidence_quote
        "K": 12, # evidence_source
        "L": 12, # quote_match
        "M": 20, # review_flags
        "N": 8,  # votes
        "O": 25, # verified_value
        "P": 10, # agree
        "Q": 10, # user_page
        "R": 40, # user_quote
        "S": 25, # user_note
        "T": 18, # verification_status
    }
    for col_letter, width in col_widths.items():
        ws.column_dimensions[col_letter].width = width

    ws.freeze_panes = "G2"
    wb.save(OUT_XLSX)
    print(f"Wrote formatted Excel workbook to {OUT_XLSX}")

if __name__ == "__main__":
    main()
