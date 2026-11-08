# Your to-do list (as of 8 Nov 2026)

Everything here needs a human decision. The experiments need nothing from you.
Work through the tasks in order. When one is done, tell Claude the phrase in the "Done → say" column.

| # | Task | Rulebook | File to fill | Time | Done → say |
|---|---|---|---|---|---|
| 1 | **DONE 8 Nov** (7e8ce8b, `review/coding/validation_report.md`). Grade 20 free-text extraction answers | `01_free_text_grading_RULES.md` | `01_free_text_grading.csv` | 30–45 min | "grading done" |
| 2 | **DONE 8 Nov** (17 verified values changed, `review/coding/adjudication_changes.csv`). Adjudicate 106 second-coder disagreements (κ already computed) | `02_second_coder_RULES.md` | `review/coding/second_coder_disagreements.csv` | 2–3 h | "adjudication done" |
| 3 | **DONE 8 Nov** (confirmed, not redone; `review/final_screening/SPOT_CHECK.md`). Confirm or redo the PRISMA spot-check | `03_prisma_spot_check_RULES.md` (+ `rulebooks/screening_rulebook.txt`) | `review/final_screening/spot_check_120.csv` | 2 min, or 2–3 h if redone | "spot-check confirmed" |
| 4 | **DONE 8 Nov** (`scripts/merge_registry_check.py`; 0 unmapped names). Verify 9 registry entries; map 26 dataset names | `04_dataset_registry_RULES.md` | `04a_registry_check.csv`, `04b_unmapped_datasets.csv` | 60–90 min | "registry done" |
| 5 | **DONE 8 Nov** (exclude, non_tls; matches the strict pass, not in the core set). Decide S1103 | `05_S1103_decision.md` | the same file | 2 min | "S1103: include / exclude / maybe" |
| 6 | Optional and housekeeping | `06_optional.md` | none | 5 min | as listed there |

None of the tasks needs another person now. The second coder was confirmed as a colleague on 8 Nov.

## Rulebooks

The `rulebooks/` folder holds copies of the project rulebooks so everything is in one place:

- `coding_rulebook.txt`: field definitions for full-text coding (tasks 1 and 2)
- `rulebooktask9.txt`: the second coder's guide (task 2)
- `screening_rulebook.txt`: the strict title/abstract screening rules (tasks 3 and 5)

The originals in `review/coding/` and `review/final_screening/` are the authoritative versions. If you change a rule, change the original and tell Claude.

## Ground rules for every task

- Decide from the paper or the dataset's own page, not from the LLM's answer.
- Where you aren't sure, write `unsure` and a short note rather than guessing. Claude will flag it for discussion.
- Don't rename columns or files. Claude reads them by name.
