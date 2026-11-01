# Model robustness: XGBoost vs LightGBM, Random Forest, Logistic Regression and a 1D-CNN (1 Nov 2026)

These runs repeat the E2/E3/E4 headline settings with other model families. The protocol is unchanged: per-table dedup, 1:1 training balance, validation-only thresholds, 5 seeds.
- Tree models and LR come from `run_benchmark.py --model` and `run_e4.py --model`. Results are in `{mta,hikari,mcfp}_{lgbm,rf,lr}/` and `e4_{lgbm,rf,lr}/`. XGBoost reference numbers are in `mta/`, `hikari/`, `mcfp/` and `e4/`.
- Fixed hyperparameters, no tuning:
  - LightGBM: same budget as XGBoost, with early stopping on validation.
  - RF: 300 trees, categories as integer codes.
  - LR: signed log1p, median imputation with missing-value flags, z-score, one-hot of the top 30 categories.
- The deep model is `scripts/run_deep.py`, a 1D-CNN on the first 20 packets (signed size, direction, log inter-arrival; `_notime` drops the IAT channel). It trains on A2's GPU, in a PyTorch venv on /data installed without root. Results are in `deep/` and `e4_deep/`. It sees G2 only, which is the TLS 1.3 + ECH tier, with no flow statistics.

## Within-dataset (PR-AUC, mean over 5 seeds)

| Dataset | Features | Exp | XGB | LightGBM | RF | LR | CNN (G2 only) |
|---|---|---|---|---|---|---|---|
| MTA | all | E2 | 0.996 | 0.999 | 0.999 | 0.997 | – |
| MTA | all | E3 | 0.901 | **0.960** | 0.944 | 0.932 | – |
| MTA | g1g2_notime | E2 | 0.995 | 0.995 | 0.994 | 0.953 | 0.976 |
| MTA | g1g2_notime | E3 | 0.859 | 0.867 | 0.883 | 0.823 | 0.788 |
| MTA | g1g2 (CNN: with IAT) | E2 / E3 | 0.9995 / 0.912 | – | – | – | 0.962 / 0.891 |
| HIKARI | g1g2_notime | E2 | 0.236 (ROC 0.965) | 0.153 | **0.617** | 0.185 | 0.017 (ROC 0.77) |
| HIKARI | g1g2_notime | E3 | 0.902 | 0.853 | 0.875 | 0.500 | 0.010 |
| MCFP | all | E2 | 0.9999 (recall neg 0.85) | 1.000 (0.87) | 1.000 (0.85) | 0.959 (0.86) | – |
| MCFP | g1g2_notime | E2 | 0.998 | 0.999 | 0.991 | 0.850 | 0.814 |
| RAID | G2 | E2 | 1.000 | – | – | – | 1.000 |

## E4 cross-dataset, `g1g2_notime` (ROC-AUC, mean over 5 seeds)

| Train → test | XGB | LightGBM | RF | LR | CNN notime | CNN with IAT |
|---|---|---|---|---|---|---|
| MCFP → MTA | 0.610 | 0.601 | 0.475 | 0.502 | 0.530 | 0.645 |
| MTA → MCFP | 0.895 | 0.902 | 0.841 | 0.597 | 0.690 | 0.752 |
| RAID → MTA | 0.692 | 0.615 | 0.677 | 0.496 | 0.656 | 0.402 |
| RAID → MCFP | 0.783 | 0.775 | 0.743 | 0.508 | 0.615 | 0.859 |
| MTA ctu → bg (recall background) | 0.895 (0.12) | 0.905 (0.07) | 0.934 (0.17) | 0.849 (0.74) | 0.855 (0.74) | 0.858 (0.35) |
| MTA bg → ctu | 0.973 | 0.975 | 0.952 | 0.852 | 0.866 | 0.935 |
| MTA bg → bg (control) | 0.993 | 0.994 | 0.989 | 0.946 | 0.965 | 0.975 |

## Findings

1. **The E4 conclusions hold for every model family.**
   - No model transfers MCFP → MTA (ROC 0.48–0.65). The RAID-trained models catch little real malware.
   - The control (bg → bg) beats the swapped-negative setting for all six models.
   - The ctu → bg benign recall is model-dependent (0.07–0.74), but it never approaches the control's 0.97.
2. **Model choice moves the temporal and grouped numbers by up to ±0.06 PR-AUC, and the HIKARI E2 number by far more.**
   - MTA E3 `all` ranges from 0.90 (XGB) to 0.96 (LightGBM).
   - HIKARI E2 PR-AUC ranges from 0.15 to 0.62, with ROC ≈ 0.95–0.98 for all four tabular models. That task has 2 attacker hosts and extreme imbalance, so its PR-AUC is unstable.
   - Single-model leaderboards in this area are therefore not comparable within ±0.05.
3. **Fixed-threshold transfer is where models differ most.** LR's TPR at val-FPR 10⁻³ is ≈ 0.02 on MTA `g1g2_notime` E2 and E3 (trees on E2: 0.84–0.89): its score distribution does not separate the extreme tail.
4. **The CNN on raw packet sequences is not better than trees on flow statistics.** On MTA and MCFP it is 0.02–0.18 PR-AUC below XGBoost and does no better in E4. It needs the IAT channel more than the trees do (MCFP E2: 0.9997 with IAT vs 0.814 without).

## Open issue: CNN on HIKARI

With the IAT channel, the CNN scores below chance on HIKARI (ROC 0.12–0.26 on E2 in all five seeds; 0.20–0.41 on E3). It trains for 15–30 epochs on 9,742 balanced rows. The input has no NaNs, and the same code behaves normally on MTA, MCFP and RAID. HIKARI's malicious flows have a mean second-packet IAT of 1.4 ms, against 212 ms for benign. The likely cause is a client-group shift in timing, where held-out attacker clients invert the pattern, but this is not verified. Treat the HIKARI CNN row as a failure, not as evidence about deep models.

## Caveats
- No hyperparameter tuning for any family, and one CNN architecture only. The point is spread across reasonable defaults, not the best attainable score.
- The CNN sees 20 packets; the tree models with `g1g2` also see whole-flow statistics (G1).
