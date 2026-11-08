# Batch 6 item 2: 20 seeds and paired tests for the headline fingerprint contrasts (8 Nov 2026)

`run_b6.py seeds`, launched in `launch_batch6.sh` (A2, 8 Nov 13:36–15:02 WITA; exit 0). CSVs are in `b6_seeds/`. Test predictions for every run are kept on A2 in `/data/tls-sok/b6pred/`; item 1 reuses them.

**Why:** on some rows the seed SD exceeded the bootstrap CI, so 5 seeds could not support a significance claim.

**What:**
- 20 seeds for each headline row, same protocol as before.
- Paired Wilcoxon signed-rank test over seeds for every with- vs without-fingerprint contrast. "Wins" = the number of the 20 seeds in which the model without G5 scored higher.

## Results (mean ± SD over 20 seeds)

| Setting | Model | PR-AUC with G5 | PR-AUC without G5 | Δ (wins / 20; p) | Macro-F1 with → without (p) |
|---|---|---|---|---|---|
| MTA E3 | XGB | 0.901 ± 0.007 | **0.983** ± 0.002 | +0.082 (20; p < 10⁻⁵) | 0.769 → 0.796 (p = 0.007) |
| MTA E3 | LightGBM | 0.956 ± 0.007 | **0.982** ± 0.001 | +0.026 (20; p < 10⁻⁵) | 0.771 → 0.806 (p = 10⁻⁴) |
| MTA E3 | RF | 0.941 ± 0.006 | **0.972** ± 0.002 | +0.031 (20; p < 10⁻⁵) | 0.767 → 0.848 (p < 10⁻⁵) |
| MCFP → MTA, no timing | XGB | 0.741 ± 0.056 | **0.803** ± 0.025 | +0.062 (16; p = 2·10⁻⁴) | 0.355 → **0.623** (p < 10⁻⁵) |
| MCFP → MTA, no timing | LightGBM | 0.665 ± 0.071 | 0.661 ± 0.042 | −0.004 (9; p = 1.0) | 0.373 → 0.486 (p < 10⁻⁵) |
| MCFP → MTA, no timing | RF | 0.840 ± 0.026 | 0.848 ± 0.028 | +0.008 (12; p = 0.35) | 0.793 → 0.777 (p = 0.29) |
| MCFP → MTA, with timing | XGB | 0.869 ± 0.040 | **0.926** ± 0.011 | +0.057 (19; p < 10⁻⁵) | 0.448 → **0.803** (p < 10⁻⁵) |
| MCFP → MTA, with timing | LightGBM | 0.867 ± 0.044 | 0.874 ± 0.043 | +0.007 (10; p = 0.55) | 0.527 → 0.715 (p < 10⁻⁵) |
| MCFP → MTA, with timing | RF | **0.949** ± 0.007 | 0.941 ± 0.011 | −0.008 (4; p = 0.007) | 0.652 → 0.717 (p = 4·10⁻⁴) |
| E9 MTA ≤2022 → 2023–26 | XGB, +JA3 / +JA4 / +both vs none | 0.900 / 0.898 / 0.901 | **0.983** | +0.083 / +0.085 / +0.082 (20 each; p < 10⁻⁵) | 0.760–0.765 → 0.811 (p ≤ 2·10⁻⁴) |
| E9 MCFP → MTA 2023–26 | XGB, +JA3 / +JA4 / +both vs none | 0.748 / 0.742 / 0.692 | **0.795** | +0.047 / +0.053 / +0.103 (17–20; p ≤ 10⁻⁴) | 0.324 → 0.773 (p < 10⁻⁵) |

Zeek-free set on MTA E3 (XGB): 0.971 ± 0.004 PR-AUC, macro-F1 0.824.

## Findings
1. **The temporal penalty is significant for every tree family.** On MTA E3, dropping G5 wins in 20 of 20 seeds for XGB, LightGBM and RF (p < 10⁻⁵), on PR-AUC and on macro-F1. Adding JA3, JA4 or both to G1–G4 loses in all 20 seeds.
2. **Across datasets, the effect on ranking is model-dependent; the effect on the operating point is not.**
   - PR-AUC: significant for XGB only. LightGBM shows no difference; RF with timing is slightly better *with* G5 (−0.008, p = 0.007).
   - Macro-F1 at the validated threshold improves without G5 in 5 of the 6 cross-dataset rows (p < 10⁻³), by up to +0.36. The exception is RF without timing, where there is no difference.
   - Hash features mostly break the threshold, not the ranking.
3. **Seed variation is large across datasets** (SD up to 0.07 PR-AUC), which is why 5 seeds were not enough there. The temporal rows are tight (SD ≤ 0.007).
4. These numbers confirm and replace the 5-seed values in `SUMMARY_crossfamily.md` and `SUMMARY_e9.md`. The direction is unchanged everywhere.

## Caveats
- Seeds vary model randomness and the training subsample; the E3 and E4 splits themselves are fixed (by time, or by dataset).
- Wilcoxon over 20 paired seeds; no multiple-comparison correction across the 30 tests. With p < 10⁻⁴ for every row described as significant, a correction would not change the conclusions.
