# Batch 6 item 3: rolling-origin temporal evaluation on MTA (8 Nov 2026)

`run_b6.py rolling`, launched in `launch_batch6.sh` (A2, 8 Nov 13:36–13:45 WITA; exit 0). CSVs are in `b6_rolling/`. Figure: `figures/fig_f_rolling.pdf`.

**Setup:**
- For every test year Y from 2020 to 2026, XGBoost (defaults) is trained on MTA traffic from earlier years only.
- Three training windows:
  - all years up to Y−1 ("expanding");
  - the last 2 years (Y−2, Y−1);
  - the last year only (Y−1).
- Validation is the latest 15% of the training window by time; thresholds come from validation only.
- Feature sets: `all` (G1–G5) and `loo_g5` (G1–G4, no fingerprints), each deduplicated on its own columns. 5 seeds.
- Training rows per window: 1.4k for 2020 (2019 only) up to 51k for 2026 expanding (`results_per_seed.csv`, `n_train_rows`).

## Results (PR-AUC mean ± SD over 5 seeds; ROC-AUC in brackets)

| Test year (test flows, malicious share) | G1–G5, expanding | G1–G5, last 2 y | G1–G5, last 1 y | No G5, expanding | No G5, last 2 y | No G5, last 1 y |
|---|---|---|---|---|---|---|
| 2020 (4,479; 58%) | 0.906 ± 0.020 (0.87) | = expanding | = expanding | 0.877 ± 0.010 (0.84) | = | = |
| 2021 (20,486; 83%) | 0.986 (0.94) | 0.986 | 0.988 | **0.995** (0.98) | 0.995 | 0.997 |
| 2022 (22,832; 85%) | 1.000 (0.998) | 0.999 | 0.999 | 1.000 (1.000) | 1.000 | 1.000 |
| 2023 (8,027; 49%) | 0.922 ± 0.002 (0.90) | 0.926 | 0.952 | **0.992** ± 0.001 (0.99) | 0.993 | 0.978 |
| 2024 (1,207; 49%) | 0.804 ± 0.057 (0.80) | 0.829 | 0.839 | **0.935** ± 0.004 (0.94) | 0.954 | 0.955 |
| 2025 (1,413; 16%) | 0.395 ± 0.040 (0.80) | 0.422 | 0.447 | **0.672** ± 0.041 (0.90) | 0.749 | 0.718 |
| 2026 (2,235; 63%) | **0.606 ± 0.070 (0.41)** | 0.988 | 0.933 | **0.970** ± 0.011 (0.96) | 0.996 | 0.993 |

## Findings

1. **The fingerprint penalty is not an artefact of one temporal cut.**
   - Without G5 the expanding-window model is at least as good as with G5 in every test year from 2021 to 2026, and the gap widens with distance from the training data: +0.07 in 2023, +0.13 in 2024, +0.28 in 2025, +0.36 in 2026.
   - The only exception is 2020, where training is 2019 alone (1.4k rows).
2. **The 2026 failure.** The model trained on everything up to 2025 ranks 2026 traffic *worse than chance* with fingerprints (ROC-AUC 0.41, PR-AUC 0.61 against a 0.63 prevalence). Without fingerprints it scores 0.97.
3. **Retraining cadence matters mostly for the fingerprint model.**
   - Training on only the last 2 years recovers the G5 model in 2026 (0.606 → 0.988) and helps a little elsewhere (+0.004 to +0.05).
   - The no-G5 model gains less from recency (−0.01 to +0.08; the 1-year window is slightly worse in 2023) and is already near its best with all past years.
   - Fingerprint models need frequent retraining; flow-statistics and handshake models age more slowly.
4. **2025 is hard for everyone** (PR-AUC 0.40–0.75 against a 0.16 prevalence; ROC 0.74–0.90). Its test set is small (230 malicious flows), with a different family mix (`b6_family` will show which). It is not a pipeline error: ROC stays at 0.8–0.9.

## Why the G5 model fails on 2026 (`b6_post2026/`)

Setup: XGBoost on G1–G5, trained on all past years, test 2026 (2,235 flows); scores averaged over 5 seeds. The ROC-AUC of the averaged score is **0.35** (the per-seed mean is 0.41). Without G5 it is **0.96**.

| Group | Flows (malicious) | Mean score: malicious / benign | ROC within the group | ROC of the rest if this group is left out |
|---|---|---|---|---|
| Post 2026/01/14 (Lumma) | 1,481 (1,248) | 0.39 / 0.32 | 0.65 | 0.42 |
| Post 2026/10/02 | 116 (5) | 0.43 / 0.52 | 0.11 | 0.40 |
| Every other single post | 1–80 | – | 12 of the 19 posts with both classes are below 0.5 | 0.33–0.37 |
| Family Lumma / ClickFix / unknown / two-family titles | 1,610 / 83 / 309 / 103 | 0.39/0.35, 0.43/0.51, 0.48/0.50, 0.41/0.50 | 0.55, 0.22, 0.35, 0.34 | 0.43, 0.38, 0.41, 0.37 |

- **Not a few posts.** Leaving out any single post, or any single family, keeps ROC below 0.5 (at most 0.43). The inversion is spread across the year.
- **Mechanism.** 79% of benign and 91% of malicious 2026 flows have a client JA3/JA4 never seen in 2019–2025 training. Among those unseen flows, benign traffic scores *higher* than malicious (mean 0.48 vs 0.41), while seen-hash flows score about the same (0.23 vs 0.25–0.26; `unseen_by_class.csv`). The fingerprint model's treatment of new hashes is what inverts the ranking. Item 3c (the seen-in-training flag in the rolling setup) tests this directly.

## 3c: the same curve with the item-4 fingerprint encodings (`b6_rolling_enc/`, XGBoost, 5 seeds)

Same rows for every encoding (dedup on G1–G5). PR-AUC with all past years; ROC in brackets for the late years:

| Test year | (a) hash categorical | (b) training frequency | (c) seen-in-training flag | (e) no fingerprints |
|---|---|---|---|---|
| 2020 | 0.906 | 0.887 | 0.876 | 0.877 |
| 2021 | 0.986 | 0.996 | 0.996 | 0.995 |
| 2022 | 1.000 | 1.000 | 1.000 | 1.000 |
| 2023 | 0.922 | 0.988 | 0.993 | 0.992 |
| 2024 | 0.804 (0.80) | 0.923 (0.91) | 0.938 (0.94) | 0.935 (0.94) |
| 2025 | 0.395 (0.80) | 0.583 (0.80) | 0.681 (0.90) | 0.672 (0.90) |
| 2026 | **0.606 (0.41)** | 0.836 (0.81) | **0.970 (0.96)** | **0.970 (0.96)** |

- **The seen-in-training flag tracks the no-fingerprint curve within 0.01 in every year**, with all past years or the last 2 years (`summary.csv`). Knowing whether a hash is new adds nothing; the drift comes from using the *hash value itself* as a feature.
- Frequency encoding lies in between and also degrades with time (2026: 0.836). It still encodes hash identity, through its training count.
- This supports the item-4 wording for the paper: *raw hashes as features age badly*, rather than "fingerprints hurt".

## Caveats
- 2024 and 2025 have small test sets (1.2–1.4k flows). Their SDs (up to 0.07) cover seed variation only, not test-set sampling. Bootstrap CIs are in `results_per_seed.csv`.
- For 2020, all windows are identical (only 2019 precedes it). For 2021, the 2-year and expanding windows are identical.
- MTA year = the date of the post; the background traffic in each year comes from the same sandbox posts.
