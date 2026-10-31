"""Copy the full-text re-check decisions (recheck_c3.xlsx) into final_screening_325.xlsx.

Usage: python scripts/apply_recheck.py
For each re-checked paper sets final_decision; for an exclude whose your_criterion is empty but which
agrees with the LLM, uses the LLM criterion. my_note gets a "full-text re-check" entry (your own note
if you wrote one, else the agreed LLM reason). Prints every change.
"""
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent.parent
RECHECK = ROOT / "review" / "fulltext" / "recheck_c3.xlsx"
MAIN = ROOT / "review" / "final_screening" / "final_screening_325.xlsx"


def main() -> None:
    rs = load_workbook(RECHECK)["Recheck"]
    rh = [c.value for c in rs[1]]
    dec = {}
    for row in rs.iter_rows(min_row=2):
        d = dict(zip(rh, [c.value for c in row]))
        if not d["your_decision"]:
            continue
        crit = d["your_criterion"] or (d["llm_criterion"] if d["your_decision"] == d["llm_suggestion"] else "")
        if d["your_decision"] == "exclude" and not crit:
            raise SystemExit(f"{d['id']}: exclude without a criterion; fill your_criterion in {RECHECK.name}")
        note = d["your_note"] or (f"agreed with LLM: {d['llm_reason']}" if d["llm_reason"] else "checked in full text")
        dec[d["id"]] = (d["your_decision"], crit if d["your_decision"] == "exclude" else None, note)

    wb = load_workbook(MAIN)
    ws = wb["Screening"]
    h = {c.value: i for i, c in enumerate(ws[1])}
    changed = 0
    for row in ws.iter_rows(min_row=2):
        pid = row[h["id"]].value
        if pid not in dec:
            continue
        d, crit, note = dec[pid]
        old = row[h["final_decision"]].value
        row[h["final_decision"]].value = d
        row[h["exclusion_criterion"]].value = crit
        prev = (row[h["my_note"]].value or "").split(" | full-text re-check:")[0]
        prev = "" if prev.startswith("full-text re-check:") else prev  # rerun-safe
        row[h["my_note"]].value = f"{prev} | full-text re-check: {note}" if prev else f"full-text re-check: {note}"
        if old != d:
            changed += 1
            print(f"{pid}: {old} -> {d} {crit or ''}")
    wb.calculation.fullCalcOnLoad = True  # openpyxl drops Excel's cached values; recompute the Summary on open
    wb.save(MAIN)
    print(f"{len(dec)} re-checked papers written, {changed} decisions changed")


if __name__ == "__main__":
    main()
