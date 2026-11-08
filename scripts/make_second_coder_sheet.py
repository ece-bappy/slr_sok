"""Build the blind coding sheet for the second coder on 14 random core papers (plan.md §4, Task 9).

Generates:
  - review/coding/second_coder_14_papers.csv
  - review/coding/second_coder_14_papers.xlsx
"""
import csv
import random
from pathlib import Path
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT.parent

CORE_RANKS = ROOT / "review" / "ranks" / "core_ranks.csv"
RECORDS_CSV = ROOT / "review" / "search" / "records.csv"
BLIND_TEMPLATE = ROOT / "review" / "coding" / "blind_validation_sheet.csv"

OUT_CSV = ROOT / "review" / "coding" / "second_coder_14_papers.csv"
OUT_XLSX = ROOT / "review" / "coding" / "second_coder_14_papers.xlsx"

FIELDS_ORDER = [
    ("datasets_evaluated", "data sources as named in the paper with role train/test/train_and_test for each"),
    ("label_source", "sandbox|blocklist_cert|blocklist_ja3|ids_alerts|dataset_provided|manual|generated|other (list)"),
    ("label_feature_overlap", "yes|no|unclear|not_applicable"),
    ("features_used", "short phrases (list)"),
    ("feature_groups", "G1|G2|G3|G4|G5 (list)"),
    ("cert_fields_read", "yes|no"),
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

def main():
    rec = {r["id"]: r for r in csv.DictReader(open(RECORDS_CSV, encoding="utf-8"))}
    core = [r for r in csv.DictReader(open(CORE_RANKS, encoding="utf-8")) if r.get("rule_A_strict") == "yes"]
    
    # 14 reproducible random papers with fixed seed 42
    random.seed(42)
    sample = sorted(random.sample(core, 14), key=lambda x: (x["year"], x["id"]))
    
    rows = []
    
    # Add example row first
    rows.append({
        "sample_id": "EXAMPLE",
        "paper_id": "(format only)",
        "year": "2024",
        "venue": "RAID",
        "title": "Example demonstration row: how to code a field",
        "pdf_file": "papers/core/EXAMPLE.pdf",
        "field": "feature_groups",
        "allowed_values": "G1|G2|G3|G4|G5 (list)",
        "your_value": "G2; G4",
        "page": "p7",
        "quote": "For the first experiment, we train classifiers on sequences of TLS records sizes, directions and types.",
        "note": "certificate size is inferred from record length, not parsed directly"
    })
    
    for idx, s in enumerate(sample, 1):
        pid = s["id"]
        r = rec[pid]
        sample_id = f"C{idx:02d}"
        year = s["year"]
        venue = s["venue"]
        title = r.get("title", "")
        pdf_file = f"papers/core/{pid}.pdf"
        
        for field, allowed in FIELDS_ORDER:
            rows.append({
                "sample_id": sample_id,
                "paper_id": pid,
                "year": year,
                "venue": venue,
                "title": title,
                "pdf_file": pdf_file,
                "field": field,
                "allowed_values": allowed,
                "your_value": "",
                "page": "",
                "quote": "",
                "note": ""
            })
            
    # Write CSV
    fieldnames = ["sample_id", "paper_id", "year", "venue", "title", "pdf_file", "field", "allowed_values", "your_value", "page", "quote", "note"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {OUT_CSV}")
    
    # Write XLSX with styling
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "SecondCoder_14"
    
    header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    example_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
    input_fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
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
        is_example = (r["sample_id"] == "EXAMPLE")
        for col_idx in range(1, len(fieldnames) + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.border = border
            cell.font = Font(name="Calibri", size=10)
            if is_example:
                cell.fill = example_fill
            elif fieldnames[col_idx - 1] in ["your_value", "page", "quote", "note"]:
                cell.fill = input_fill
            if fieldnames[col_idx - 1] in ["sample_id", "paper_id", "year", "page"]:
                cell.alignment = Alignment(horizontal="center", vertical="top")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
                
    # Column widths
    col_widths = {
        "A": 12, # sample_id
        "B": 12, # paper_id
        "C": 8,  # year
        "D": 25, # venue
        "E": 35, # title
        "F": 25, # pdf_file
        "G": 22, # field
        "H": 35, # allowed_values
        "I": 25, # your_value
        "J": 10, # page
        "K": 45, # quote
        "L": 30  # note
    }
    for col_letter, width in col_widths.items():
        ws.column_dimensions[col_letter].width = width
        
    ws.freeze_panes = "A2"
    wb.save(OUT_XLSX)
    print(f"Wrote formatted Excel workbook to {OUT_XLSX}")

if __name__ == "__main__":
    main()
