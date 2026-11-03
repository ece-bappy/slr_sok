# Unsupervised baselines: Isolation Forest and autoencoder (3 Nov 2026)

`scripts/run_unsup.py` (torch venv; the autoencoder trains on A2's GPU), launched in `launch_batch5.sh` (A2, 3 Nov 15:59–16:10 WITA; exit 0). CSVs are in `unsup/`.

**Protocol:**
- **Training:** benign flows of the training split only (at most 200k rows). No malicious labels are used for training or for thresholds.
- **Thresholds:** the 99th and 99.9th percentiles of the anomaly scores on the benign rows of the validation split, i.e. benign-validation FPR 10⁻² and 10⁻³.
- **Splits, dedup, seeds and CIs:** as for the supervised models.
- **Input:** G1+G2 flow statistics and packet sequence, with timing (`g1g2`) and without (`g1g2_notime`), scaled as for LR.
- **Models:**
  - Isolation Forest: 300 trees.
  - Autoencoder: d → 64 → 16 → 64 → d, MSE, early stopping on benign validation loss.
- **Score:** −score_samples for IF, reconstruction error for the AE.

## Results (mean over 5 seeds)

Columns: ROC-AUC; PR-AUC with its no-skill level (prevalence); and, at the benign-validation-FPR-10⁻² threshold, the test FPR and recall on malicious flows.

| Setting | Input | Prevalence | IF ROC / PR-AUC | AE ROC / PR-AUC [CI] | AE test FPR / malicious recall @ val-FPR 10⁻² | Supervised XGB PR-AUC (same set) |
|---|---|---|---|---|---|---|
| MTA E2 | g1g2 | 0.73 | 0.68 / 0.800 | 0.88 / 0.909 [0.901–0.917] | 0.015 / **0.011** | 0.9995 |
| MTA E2 | no timing | 0.49 | 0.63 / 0.567 | 0.81 / 0.724 [0.704–0.742] | 0.012 / 0.030 | 0.995 |
| MTA E3 | g1g2 | 0.48 | 0.73 / 0.645 | 0.78 / 0.652 [0.640–0.665] | **0.136** / 0.211 | 0.912 |
| MTA E3 | no timing | 0.39 | 0.71 / 0.543 | 0.71 / 0.500 [0.486–0.514] | 0.136 / 0.208 | 0.859 |
| MCFP E2 | g1g2 | 0.92 | 0.86 / 0.969 | 0.94 / 0.988 [0.987–0.988] | 0.004 / 0.013 | 1.000 |
| MCFP E2 | no timing | 0.34 | **0.27** / 0.241 | 0.57 / 0.357 [0.350–0.365] | 0.167 / 0.162 | 0.998 |
| MCFP → MTA | g1g2 | 0.73 | 0.48 / 0.704 | 0.61 / 0.772 [0.767–0.777] | 0.035 / 0.039 | 0.836 (E4 g1g2) |
| MCFP → MTA | no timing | 0.49 | 0.52 / 0.518 | 0.52 / 0.523 [0.515–0.531] | 0.067 / 0.126 | 0.585 |

## Findings

1. **Benign-only anomaly detection does not find this malware.** At a threshold set for 1% benign false positives, the autoencoder flags 1–21% of malicious flows. The Isolation Forest is worse: 0.3–8%, ROC-AUC 0.27–0.86. Malware C2 over TLS is not anomalous in flow statistics: it looks like ordinary short HTTPS sessions.
2. **PR-AUC flatters them where prevalence is high.** MTA E2 0.91 and MCFP E2 0.99 sit on test sets with 73% and 92% malicious flows. The ROC and the recall at the operating point give the real picture.
3. **Drift breaks the benign-only threshold too.** On MTA E3 the test FPR at the validated 1% threshold is 13.6%: newer benign traffic is "anomalous" relative to 2019–2022 benign traffic. Without timing on MCFP, the IF ranks malicious flows as *more normal* than benign ones (ROC 0.27).
4. **Every unsupervised setting is far below the supervised models on the same splits.** The cross-dataset conclusion (E4) is unchanged: both are at chance without timing.

## Caveats
- One architecture and default settings per method; not tuned.
- The anomaly models see only G1/G2 (no TLS fields); with TLS fields they would face the same fingerprint drift as the supervised models (`SUMMARY_e9.md`).
- "Benign" in MTA is same-host background traffic from infected sandboxes; a cleaner enterprise baseline could change the false-positive side.
