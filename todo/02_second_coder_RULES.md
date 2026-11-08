# Task 2: adjudicate the second-coder disagreements

**Status:** you confirmed the second coder was a colleague coding blind (8 Nov). κ is computed: see `review/coding/kappa_report.md`, produced by `scripts/kappa_second_coder.py`.

| Measure | Result |
|---|---|
| Single-choice fields (10) | 82% agreement; per-field κ mean 0.51, median 0.56 |
| List fields (6), pooled yes/no decisions | κ 0.77 |
| Weakest fields | cert_fields_read κ 0.11, label_feature_overlap −0.17, shortcut_check 0.41, main_split 0.43 |

Low κ next to high agreement (e.g. easy_vs_hard_reported: 12/14 but κ 0.00) is the usual artefact when one answer dominates. It is not necessarily poor reliability.

**cert_fields_read is a rulebook ambiguity, not a disagreement.** All 7 cases are "no" (you) vs "not_applicable" (colleague) on papers that use no certificate information. The rulebook allows both readings ("no = … or not used"; "not_applicable = no certificate information at all"). Both give the same visibility tier. Merged, the field agrees 14/14.

## What to do

**File:** `review/coding/second_coder_disagreements.csv`, 106 rows: 25 single-choice, 34 list, 47 free-text. Have each paper's PDF open (`pdf` column).

For each row fill:
- `adjudicated_value`: the correct value per the coding rulebook, decided from the paper.
- `who_was_right`: `coder1`, `coder2`, `both` (same meaning, different wording; the usual outcome for free text) or `neither`.
- `note`: why, especially for `coder1` errors and rulebook ambiguities.

Rules:
1. Decide from the paper and `rulebooks/coding_rulebook.txt`, not from who usually knows best. Where `coder1` was wrong, the verified coding gets corrected.
2. Free text: `both` if the two answers describe the same set (different wording or detail level is fine). Only real content differences count.
3. Keep κ as computed. κ is reported **before** adjudication; adjudication only fixes the final dataset.
4. `cert_fields_read` is settled: you chose on 8 Nov to merge `not_applicable` into `no`.
   - Rule R1 is added to section 6 of the rulebook.
   - The 27 verified values and the LLM definitions are recoded.
   - The 7 rows in the sheet are pre-filled ("both").
   - The paper reports the field's κ both ways: 0.11 as coded, 1.00 merged.

That leaves 99 rows to adjudicate, about 2–3 hours. Then tell Claude "adjudication done". Claude applies the corrections to the verified coding and records the rulebook change.
