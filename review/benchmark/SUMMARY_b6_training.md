# Batch 6 item 6: training-set sensitivity, dedup and class ratio (8 Nov 2026)

`run_b6.py training`, launched in `launch_batch6.sh` (A2, 8 Nov 15:04–15:31 WITA; exit 0). XGBoost, 5 seeds. CSVs are in `b6_training/`.

**Variants:**
- Per-feature-set dedup on (protocol) or off.
- Training class ratio:
  - 1:1 (protocol, majority class subsampled);
  - natural (all training rows);
  - 1:10 benign-heavy (benign = 10 × malicious, subsampling whichever class is needed).
- Settings: MTA E3 with all / no G5; MCFP → MTA without timing, with all / no G5.
- Validation, thresholds and test sets are as in the protocol.

**Note: dedup also changes the test set.**
- On MTA with all features there are almost no duplicates (23 rows), so the MTA E3 test set is the same either way.
- Without timing, MTA has many identical vectors: the E4 test set is 31k flows deduplicated vs 62k not, at a different malicious share. PR-AUC is therefore not comparable across the dedup columns for E4; ROC is.

## Results (mean over 5 seeds)

| Setting, features | Dedup | Ratio | Training rows | PR-AUC | ROC | Macro-F1 | Test FPR @ val 10⁻³ |
|---|---|---|---|---|---|---|---|
| MTA E3, G1–G5 | on | **1:1** | 17.7k | 0.899 | 0.874 | 0.763 | 0.011 |
| | on | natural | 42.0k | 0.911 | 0.887 | 0.756 | 0.012 |
| | on | 1:10 | 9.7k | 0.868 | 0.843 | 0.751 | 0.015 |
| | off | 1:1 / natural / 1:10 | | 0.903 / 0.910 / 0.891 | 0.877 / 0.886 / 0.865 | 0.783 / 0.759 / 0.780 | 0.006–0.013 |
| MTA E3, no G5 | on | **1:1** | 17.7k | **0.984** | 0.985 | **0.835** | 0.002 |
| | on | natural | 42.0k | 0.984 | 0.986 | 0.787 | 0.002 |
| | on | 1:10 | 9.7k | 0.974 | 0.976 | 0.788 | 0.001 |
| | off | 1:1 / natural / 1:10 | | 0.984 / 0.984 / 0.974 | 0.985 / 0.985 / 0.976 | 0.811 / 0.782 / 0.810 | 0.001–0.002 |
| MCFP → MTA, G1–G5 no timing | on | 1:1 / natural / 1:10 | 59k / 86k / 63k | 0.734 / 0.805 / 0.706 | 0.79 / 0.86 / 0.79 | 0.36 | **0.98** |
| | off | 1:1 / natural / 1:10 | 127k / 1.33M / 70k | 0.906 / 0.881 / 0.915 † | 0.81 / 0.78 / 0.83 | 0.45 / 0.60 / 0.45 | **0.98** |
| MCFP → MTA, no G5 no timing | on | 1:1 / natural / 1:10 | 59k / 86k / 63k | 0.808 / 0.811 / 0.818 | 0.85 / 0.85 / 0.86 | 0.64 / 0.61 / **0.77** | 0.52 / 0.56 / 0.44 |
| | off | 1:1 / natural / 1:10 | 127k / 1.33M / 70k | 0.937 / 0.945 / 0.931 † | 0.88 / 0.89 / 0.88 | 0.69 / 0.61 / **0.82** | 0.39 / 0.62 / **0.20** |

† Without dedup the MTA test set keeps its duplicate vectors (62k flows, 73% malicious instead of 31k at 49%), which inflates PR-AUC. Compare ROC.

## Findings
1. **No protocol choice changes a conclusion.** The no-G5 advantage on MTA E3 holds in all six dedup × ratio combinations (+0.07 to +0.11 PR-AUC), and the cross-dataset threshold stays unusable in all of them (test FPR 0.20–0.98).
2. **Dedup matters little for ranking but a lot for reported PR-AUC across datasets.** Removing it raises MCFP → MTA ROC by only +0.01 to +0.04, but PR-AUC by up to +0.13, because duplicated malicious vectors pad the test set. Dedup is the conservative choice, and the protocol keeps it.
3. **The 1:1 balance is not hiding anything.** Natural ratios give the same MTA E3 ranking. On MTA E3 the benign-heavy 1:10 ratio costs 0.01–0.03 PR-AUC, because it trains on fewer rows.
4. **One operating-point effect is worth noting.** For no-G5 across datasets, 1:10 benign-heavy training gives the best threshold (macro-F1 0.77–0.82; test FPR 0.44 / 0.20 instead of 0.52 / 0.39). A benign-heavy training set calibrates the threshold more conservatively, but not enough to be usable.

## Caveats
- One model family (XGBoost). Ratios other than these three were not tried.
- The no-dedup rows still remove nothing from training, so training sizes differ by up to 15× (natural, no dedup: 1.33M rows).
