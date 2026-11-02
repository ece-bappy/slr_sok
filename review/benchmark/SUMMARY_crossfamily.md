# Cross-family check of the fingerprint (G5) result (2 Nov 2026)

`scripts/launch_batch4.sh` on A2 (2 Nov 19:37–20:32 WITA, log `/data/tls-sok/out/batch4_1937.log`; all steps exited 0). Same protocol as E3, E4 and E9: 5 seeds, per-set dedup, 1:1 balance, validation-only thresholds, fixed hyperparameters per family. CSVs are in `cf_mta_<model>/`, `cf_e4_<model>/` and `cf_e9_<model>/`; the XGBoost E9 rows are in `e9/`. Figure: `figures/fig_c_fingerprints.pdf`.

**Question:** does "fingerprints hurt generalisation" hold for every model family, or only for XGBoost?

**Feature sets compared:**
- `all` (G1–G5) against `loo_g5` / `no_fp` (G1–G4, no fingerprints; the same columns under two names).
- `g1g2g3` (Zeek-free, see `SUMMARY_e7.md`) is shown for reference.

**Fingerprint encodings per family:**
- XGBoost: native categorical splits that partition the categories.
- LightGBM: native categorical, with its default smoothing and per-category minimum counts.
- RF: integer codes from the training categories (unseen = missing).
- LR: one-hot of the 30 most frequent training values per fingerprint column (all other values = all-zero).

**CNN:** not applicable. The 1D-CNN takes only the G2 packet sequence, so it never sees fingerprints. Its fingerprint-free reference is MTA E3 0.891 with timing and 0.788 without (`deep/`).

Cells give PR-AUC mean ± SD [mean 95% bootstrap CI]; macro-F1 is at the validation max-F1 threshold. "Test FPR" is at the validation-FPR-10⁻³ threshold.

## 1. Temporal drift: MTA ≤2022 → 2023–26 (E3 split)

| Model | all (G1–G5) | no fingerprints (G1–G4) | Δ PR-AUC | Macro-F1 all → no-fp | Test FPR all → no-fp |
|---|---|---|---|---|---|
| XGBoost | 0.901 ± 0.006 [0.896–0.906] | **0.982** ± 0.001 [0.980–0.985] | **+0.081** | 0.777 → 0.787 | 0.012 → 0.002 |
| LightGBM | 0.960 ± 0.006 [0.956–0.963] | **0.983** ± 0.001 [0.981–0.985] | **+0.023** | 0.771 → 0.844 | 0.015 → 0.003 |
| RF | 0.944 ± 0.009 [0.940–0.948] | **0.973** ± 0.002 [0.971–0.976] | **+0.029** | 0.770 → 0.841 | 0.008 → 0.001 |
| LR | 0.932 ± 0.002 [0.928–0.937] | 0.932 ± 0.004 [0.927–0.937] | 0.000 | 0.827 → 0.840 | 0.031 → 0.032 |

E9, with JA3 and JA4 added separately (G1–G4 + each; same split):

| Model | no fp | +JA3/JA3S | +JA4/JA4S | +both |
|---|---|---|---|---|
| XGBoost | **0.982** | 0.894 | 0.895 | 0.901 |
| LightGBM | **0.983** | 0.966 | 0.964 | 0.954 |
| RF | **0.973** | 0.967 | 0.967 | 0.948 |
| LR | 0.932 | 0.930 | 0.932 | 0.932 |

## 2. Cross-dataset: MCFP → MTA

E4 (test = all MTA, 47–49% malicious):

| Model | all | no fp | Δ | Macro-F1 all → no-fp | all, no timing | no fp, no timing | Δ | Macro-F1 (no timing) |
|---|---|---|---|---|---|---|---|---|
| XGBoost | 0.844 [0.840–0.849] | **0.931** [0.928–0.934] | **+0.087** | 0.448 → **0.815** | 0.734 | **0.808** | **+0.074** | 0.355 → 0.643 |
| LightGBM | 0.852 [0.848–0.856] | 0.866 [0.862–0.869] | +0.014 | 0.525 → 0.696 | 0.669 | 0.671 | +0.002 | 0.368 → 0.492 |
| RF | 0.949 [0.947–0.952] | 0.940 [0.937–0.943] | −0.009 | 0.676 → 0.713 | 0.834 | 0.832 | −0.002 | 0.807 → 0.777 |
| LR | 0.748 [0.744–0.752] | 0.745 [0.741–0.750] | −0.003 | 0.542 → 0.472 | 0.768 | **0.792** | +0.024 | 0.685 → 0.636 |

E9, combined time and dataset shift (MCFP → MTA 2023–26, with timing):

| Model | no fp | +JA3 | +JA4 | +both | Macro-F1 no fp → both |
|---|---|---|---|---|---|
| XGBoost | **0.794** [0.781–0.806] | 0.716 | 0.710 | 0.665 | 0.776 → 0.324 |
| LightGBM | 0.699 [0.687–0.712] | 0.679 | 0.703 | 0.677 | 0.643 → 0.414 |
| RF | 0.831 [0.821–0.842] | **0.861** | 0.859 | 0.853 | 0.609 → 0.564 |
| LR | 0.538 [0.528–0.550] | 0.539 | 0.533 | 0.535 | 0.569 → 0.587 |

## Findings

1. **Under temporal drift, fingerprints hurt every tree family and never help.**
   - Dropping G5 raises E3 PR-AUC for XGBoost (+0.081), LightGBM (+0.023) and RF (+0.029). The CIs do not overlap.
   - Macro-F1 also rises (+0.01 to +0.07), and the test FPR falls 5–8×.
   - For LR it makes no difference (0.932 either way).
   - Adding JA3 or JA4 to G1–G4 lowers PR-AUC for every tree family; LR is unchanged.
2. **The size of the penalty depends on how freely a model can memorise individual hash values.**
   - XGBoost's partition splits can isolate any set of hashes and lose the most.
   - LightGBM's smoothed categorical splits and RF's integer codes lose less.
   - LR sees only the 30 most frequent values, so new hashes contribute nothing and the fingerprints are neutral.
   - Corollary: XGBoost's lower `all` E3 score (0.901 vs 0.94–0.96 for the other trees) is itself mostly the fingerprint effect. Without G5 all three tree families agree (0.973–0.983).
3. **Across datasets, the effect is model-dependent, not universal.**
   - XGBoost gains a lot from dropping G5: +0.07 to +0.13 PR-AUC, and macro-F1 0.45 → 0.82 on E4.
   - LightGBM gains a little; it still gains clearly in macro-F1 (+0.12 to +0.23).
   - For RF the PR-AUC change is about zero or slightly negative: −0.009 on E4; on E9, +JA3 0.861 vs 0.831 with no fingerprints.
   - LR is mixed: +0.024 without timing, −0.003 with timing.
   - In every family the cross-dataset operating point is poor either way (test FPR 0.03–0.98), so fingerprints are not what makes transfer fail.

## Suggested wording for the paper

"Under temporal drift, adding JA3/JA4 fingerprints lowers accuracy for every tree-based model (PR-AUC −0.02 to −0.08, FPR up 5–8×) and has no effect on logistic regression. About half of later-period flows carry a fingerprint never seen in training. Across datasets the effect depends on the model: strongly negative for XGBoost, small for LightGBM, and none for RF and LR. Cross-dataset transfer fails with or without fingerprints."

That is, claim "fingerprints hurt generalisation" for **temporal** generalisation (all families: negative or neutral), not as a universal cross-dataset statement.

## Caveats
- Fixed hyperparameters per family. Tuning XGBoost (`SUMMARY_tuning.md`) recovers part of its E3 gap (0.949 with `colsample_bytree` 0.33), consistent with finding 2.
- The fingerprint penalty for LR is bounded by its top-30 one-hot encoding, a design choice. A hashed or frequency encoding could behave differently.
- The MTA background is sandbox-host traffic (see `SUMMARY_e9.md`). An enterprise background could have a more stable fingerprint mix.
- RF on MCFP → MTA ranks better with fingerprints (0.86) but has a worse operating point (macro-F1 0.56 vs 0.61; test FPR about 0.5 either way).
