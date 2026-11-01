# E4 cross-dataset benchmark (1 Nov 2026)

`scripts/run_e4.py` on A2. All CSVs are in `e4/`.

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
| MTA bg → MTA bg (control, unseen posts) | g1g2_notime | 53% | 0.993 | 0.992 | 0.944 | 0.973 | 0.826 / 0.001 |
| | g1g2 | 73% | 0.995 | 0.990 | 0.890 | 0.969 | 0.866 / 0.005 |
| | all | 73% | 0.985 | 0.968 | 0.846 | 0.977 | 0.772 / 0.002 |
| MTA ctu → MTA bg | g1g2_notime | 53% | 0.886 | 0.897 | 0.987 | **0.244** | 0.996 / **0.908** |
| | g1g2 | 73% | 0.954 | 0.896 | 0.997 | 0.122 | 1.000 / 0.974 |
| | all | 73% | 0.968 | 0.924 | 0.945 | 0.233 | 1.000 / 0.983 |
| MTA bg → MTA ctu | g1g2_notime | 7% | 0.908 | 0.974 | 0.944 | 0.856 | 0.826 / 0.012 |
| | g1g2 | 14% | 0.896 | 0.952 | 0.890 | 0.801 | 0.866 / 0.050 |
| | all | 14% | 0.865 | 0.877 | 0.846 | 0.773 | 0.772 / 0.014 |
| MCFP → MTA | g1g2_notime | 49% | 0.581 | 0.612 | 0.679 | 0.481 | 0.494 / 0.341 |
| | g1g2 | 72% | 0.825 | 0.658 | 0.210 | 0.916 | 0.389 / 0.195 |
| | all | 72% | 0.838 | 0.764 | 0.999 | **0.023** | 0.999 / **0.977** |
| MTA → MCFP | g1g2_notime | 34% | 0.851 | 0.894 | 0.769 | 0.873 | 0.546 / 0.029 |
| | g1g2 | 92% | 0.988 | 0.900 | 0.869 | 0.853 | 0.472 / 0.055 |
| | all | 92% | 0.981 | 0.856 | 0.668 | 0.849 | 0.050 / 0.005 |
| RAID → MTA | g1g2_notime | 49% | 0.635 | 0.697 | **0.000** | 1.000 | 0.220 / 0.109 |
| | g1g2 | 72% | 0.703 | 0.472 | 0.028 | 0.900 | 0.061 / 0.210 |
| | all | 72% | 0.879 | 0.812 | 0.001 | 0.999 | 0.992 / 0.378 |
| RAID → MCFP | g1g2_notime | 34% | 0.648 | 0.783 | **0.000** | 1.000 | 0.393 / 0.072 |
| | g1g2 | 92% | 0.988 | 0.902 | 0.322 | 0.979 | 0.790 / 0.048 |
| | all | 92% | 0.999 | 0.990 | 0.297 | 0.998 | 0.998 / 0.035 |

Per-TLS-version results are in `e4/results_per_tls_version.csv`.

## Findings

1. **Within-dataset scores do not transfer.**
   - Without timing, MCFP → MTA reaches ROC-AUC 0.61 and MTA → MCFP 0.89. The same models score ≥ 0.997 PR-AUC in E1/E2.
   - The validation thresholds fail on the target: at the source's 10⁻³ FPR threshold, the test FPR is 0.03–0.98.
2. **A single-tool C2 dataset teaches nothing about real C2.**
   - Trained on RAID (Metasploit C2 vs scripted browsing), the max-F1 threshold catches 0–3% of MTA or MCFP malicious flows.
   - Where the RAID ranking looks good (RAID → MCFP with fingerprints, ROC-AUC 0.99), it ranks "not a modern 2024 browser" above "modern browser". MCFP malware is 40% TLS 1.0 from 2013–18, so that ranking only reflects era and client stack.
3. **The benign side decides what the model learns (negative swap).**
   - The control (MTA background on both sides, unseen posts) reaches ROC-AUC 0.99 and malicious recall 0.94.
   - Trained against CTU-Normal browsing instead, the model still catches MTA malware (recall 0.945–0.997), but it also flags 76–88% of the same hosts' background flows. At the strict threshold, 91–98% are flagged. It has learned "not 2017 CTU-Normal traffic", not "malware".
   - The reverse direction (train on MTA background, test against CTU-Normal) degrades less: ROC-AUC 0.88–0.97, FPR 1–5% at the strict threshold.
   - Benign data from a different environment or era is therefore a dominant, often hidden, confound. Papers that pair malware pcaps with benign traffic from a separate capture measure environment separation.
4. **Fingerprint features (`all`) make transfer more brittle, not less.**
   - MCFP → MTA with JA3/JA4 flags 98% of MTA background as malicious.
   - MTA → MCFP with `all` has the lowest TPR at the strict threshold (0.05).

## Caveats
- MTA negatives are same-host background, not verified benign. MCFP labels are weak and capture-level (see `SUMMARY_mta_mcfp.md`).
- The feature sets differ in dedup size (g1g2_notime keeps far fewer rows), so prevalence differs across rows of the table.
- Fixed hyperparameters, no tuning; a single model family.
