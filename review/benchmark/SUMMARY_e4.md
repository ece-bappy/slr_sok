# E4 cross-dataset benchmark (1 Nov 2026; MTA rows rerun after the IP-lookup fix)

`scripts/run_e4.py` on A2. All CSVs are in `e4/`. Other model families on the `g1g2_notime` pairs are in `SUMMARY_models.md`.

**Protocol.** Same as E1–E3 (XGBoost with fixed hyperparameters, per-table dedup per feature set, 1:1 training balance, 5 seeds), with two differences:
- Validation is a 15% stratified sample of the **training source**, so early stopping and both thresholds (max-F1 and FPR = 10⁻³) never see the target.
- Feature columns are the intersection of the source and target tables.

No test feature vector appears in the training rows, except 12 rows in RAID → MCFP.

**Pairings.**
- Whole dataset → whole dataset: MCFP ↔ MTA, RAID → MTA and RAID → MCFP.
- Negative swap on MTA: MTA infection cases (posts) are split 70/30 per seed, and the malicious flows of the test posts are always the test positives.
  - `ctu>bg`: train with CTU-Normal as negatives, test against MTA same-host background.
  - `bg>ctu`: the reverse.
  - `bg>bg`: control, with MTA background on both sides.

**Reading the numbers.** The malicious share of the test sets ranges from 7% to 92%, so PR-AUC baselines differ. Read PR-AUC next to the "pos" column, and prefer ROC-AUC and the operating-point columns for comparisons. "Test FPR" is measured at the threshold the source validation set put at FPR 10⁻³; a large value means that threshold did not transfer.

## Results (mean over 5 seeds)

| Train → test | Features | Test pos | PR-AUC | ROC-AUC | Recall mal (max-F1 thr) | Recall neg | TPR / test FPR at val-FPR 10⁻³ |
|---|---|---|---|---|---|---|---|
| MTA bg → MTA bg (control, unseen posts) | g1g2_notime | 49% | 0.994 | 0.993 | 0.963 | 0.967 | 0.829 / 0.001 |
| | g1g2 | 75% | 0.998 | 0.995 | 0.921 | 0.977 | 0.885 / 0.002 |
| | all | 75% | 0.994 | 0.984 | 0.908 | 0.974 | 0.846 / 0.005 |
| MTA ctu → MTA bg | g1g2_notime | 49% | 0.881 | 0.895 | 0.991 | **0.120** | 0.995 / **0.924** |
| | g1g2 | 75% | 0.962 | 0.907 | 0.996 | 0.138 | 1.000 / 0.978 |
| | all | 75% | 0.975 | 0.935 | 0.980 | 0.321 | 1.000 / 0.984 |
| MTA bg → MTA ctu | g1g2_notime | 7% | 0.891 | 0.973 | 0.963 | 0.809 | 0.829 / 0.021 |
| | g1g2 | 16% | 0.932 | 0.972 | 0.921 | 0.845 | 0.885 / 0.034 |
| | all | 16% | 0.927 | 0.938 | 0.908 | 0.820 | 0.846 / 0.001 |
| MCFP → MTA | g1g2_notime | 49% | 0.585 | 0.610 | 0.679 | 0.478 | 0.494 / 0.343 |
| | g1g2 | 73% | 0.836 | 0.661 | 0.210 | 0.922 | 0.389 / 0.189 |
| | all | 73% | 0.844 | 0.766 | 0.999 | **0.024** | 0.999 / **0.976** |
| MTA → MCFP | g1g2_notime | 34% | 0.849 | 0.895 | 0.770 | 0.873 | 0.459 / 0.020 |
| | g1g2 | 92% | 0.987 | 0.894 | 0.877 | 0.843 | 0.334 / 0.038 |
| | all | 92% | 0.981 | 0.855 | 0.804 | 0.731 | 0.129 / 0.003 |
| RAID → MTA | g1g2_notime | 49% | 0.637 | 0.692 | **0.000** | 1.000 | 0.220 / 0.111 |
| | g1g2 | 73% | 0.709 | 0.460 | 0.028 | 0.897 | 0.061 / 0.217 |
| | all | 73% | 0.892 | 0.825 | 0.001 | 0.999 | 0.992 / 0.347 |
| RAID → MCFP | g1g2_notime | 34% | 0.648 | 0.783 | **0.000** | 1.000 | 0.393 / 0.072 |
| | g1g2 | 92% | 0.988 | 0.902 | 0.322 | 0.979 | 0.790 / 0.048 |
| | all | 92% | 0.999 | 0.990 | 0.297 | 0.998 | 0.998 / 0.035 |

Per-TLS-version results are in `e4/results_per_tls_version.csv`.

## Changes after the IP-lookup fix

Every pair involving MTA was rerun on the rebuilt MTA table, which has 845 fewer background flows (`SUMMARY_mta_mcfp.md`); RAID → MCFP is unchanged. The ranking metrics barely moved. The operating points on the negative-swap rows moved the most:

| Pair | Features | Metric | Before | After |
|---|---|---|---|---|
| ctu → bg | g1g2_notime | recall background | 0.244 | 0.120 |
| ctu → bg | all | recall background | 0.233 | 0.321 |
| bg → ctu | all | ROC-AUC | 0.877 | 0.938 |
| bg → ctu | g1g2_notime | recall CTU-Normal | 0.856 | 0.809 |
| bg → bg | all | ROC-AUC / recall malicious | 0.968 / 0.846 | 0.984 / 0.908 |
| MTA → MCFP | all | recall malicious / recall negative | 0.668 / 0.849 | 0.804 / 0.731 |
| MTA → MCFP | g1g2, g1g2_notime | TPR at val-FPR 10⁻³ | 0.472, 0.546 | 0.334, 0.459 |

The max-F1 operating points on these rows move by ±0.1 between runs, so treat them as unstable. Use ROC-AUC and the strict-threshold columns as the headline. Findings 1–4 below hold with the new numbers.

## Findings

1. **Within-dataset scores do not transfer.**
   - Without timing, MCFP → MTA reaches ROC-AUC 0.61 and MTA → MCFP 0.90. The same models score ≥ 0.994 PR-AUC in E1/E2.
   - The validation thresholds fail on the target: at the source's 10⁻³ FPR threshold, the test FPR is 0.003–0.98 across the whole-dataset pairs. MTA → MCFP keeps a low FPR only by giving up recall (TPR 0.13–0.46).
2. **A single-tool C2 dataset teaches nothing about real C2.**
   - Trained on RAID (Metasploit C2 vs scripted browsing), the max-F1 threshold catches 0–3% of MTA or MCFP malicious flows.
   - Where the RAID ranking looks good (RAID → MCFP with fingerprints, ROC-AUC 0.99), it ranks "not a modern 2024 browser" above "modern browser". MCFP malware is 40% TLS 1.0 from 2013–18, so that ranking only reflects era and client stack.
3. **The benign side decides what the model learns (negative swap).**
   - The control (MTA background on both sides, unseen posts) reaches ROC-AUC 0.98–0.995 and malicious recall 0.91–0.96.
   - Trained against CTU-Normal browsing instead, the model still catches MTA malware (recall 0.98–0.996), but it also flags 68–88% of the same hosts' background flows. At the strict threshold, 92–98% are flagged. It has learned "not 2017 CTU-Normal traffic", not "malware".
   - The reverse direction (train on MTA background, test against CTU-Normal) degrades less: ROC-AUC 0.94–0.97, FPR 0.1–3% at the strict threshold.
   - Benign data from a different environment or era is therefore a dominant, often hidden, confound. Papers that pair malware pcaps with benign traffic from a separate capture measure environment separation.
4. **Fingerprint features (`all`) make transfer more brittle, not less.**
   - MCFP → MTA with JA3/JA4 flags 98% of MTA background as malicious.
   - MTA → MCFP with `all` has the lowest TPR at the strict threshold (0.13).

## Caveats
- MTA negatives are same-host background, not verified benign. MCFP labels are weak and capture-level (see `SUMMARY_mta_mcfp.md`).
- The feature sets differ in dedup size (g1g2_notime keeps far fewer rows), so prevalence differs across rows of the table.
- Fixed hyperparameters, no tuning. LightGBM, RF, LR and a 1D-CNN are in `SUMMARY_models.md`.
