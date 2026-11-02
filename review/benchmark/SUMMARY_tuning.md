# XGBoost hyperparameter tuning (2 Nov 2026)

`scripts/tune.py`, launched as the last step of `scripts/launch_batch3.sh` (A2, 2 Nov, 15:56–16:36 WITA, log `/data/tls-sok/out/batch3_1509.log`; exit 0). CSVs, per-trial logs and `best_params.json` are in `tuning/`.

## Protocol
- **Search:** Optuna TPE (seed 0), a fixed budget of **40 trials per setting**.
- **Objective:** PR-AUC on the **source validation set** of the seed-0 split. This is the same set used for early stopping and thresholds. The test set and, for E4, the target dataset are never used.
- **Search space:**
  - max_depth 3–12, learning_rate 0.01–0.3 (log)
  - subsample 0.5–1, colsample_bytree 0.3–1
  - min_child_weight 1–50 (log), reg_lambda 10⁻³–30 (log), reg_alpha 10⁻⁴–10 (log), gamma 0–5
  - 2,000 trees with early stopping after 50 rounds
- **Defaults:** max_depth 8, learning_rate 0.1, subsample 0.8, colsample_bytree 0.8, up to 1,000 trees with early stopping after 30 rounds.
- **Evaluation:** the best parameters are refit on all 5 seeds and scored on test next to the defaults, with the same protocol as the benchmark.

## Results

Each cell gives mean ± SD over 5 seeds, followed by the mean 95% bootstrap CI.

| Setting | Variant | PR-AUC | macro-F1 | TPR / test FPR at val-FPR 10⁻³ |
|---|---|---|---|---|
| MTA all E2 | default | 0.994 ± 0.002 (0.993–0.995) | 0.910 ± 0.004 | 0.878 / 0.0017 |
| | tuned | 0.998 ± 0.000 (0.998–0.999) | 0.913 ± 0.003 | 0.896 / 0.0023 |
| MTA all E3 | default | 0.899 ± 0.005 (0.894–0.904) | 0.763 ± 0.015 | 0.528 / 0.0115 |
| | tuned | **0.949** ± 0.007 (0.945–0.952) | **0.825** ± 0.043 | 0.569 / 0.0209 |
| MTA g1g2_notime E2 | default | 0.995 ± 0.001 (0.994–0.996) | 0.956 ± 0.009 | 0.893 / 0.0024 |
| | tuned | 0.995 ± 0.001 (0.994–0.996) | 0.959 ± 0.007 | 0.905 / 0.0022 |
| MTA g1g2_notime E3 | default | 0.875 ± 0.018 (0.867–0.882) | 0.811 ± 0.018 | 0.450 / 0.0118 |
| | tuned | 0.877 ± 0.003 (0.870–0.885) | 0.816 ± 0.003 | 0.355 / 0.0017 |
| MCFP all E2 | default | 1.000 | 0.954 ± 0.001 | 0.999 / 0.151 |
| | tuned | 1.000 | **0.975** ± 0.007 | 0.999 / **0.079** |
| MCFP g1g2_notime E2 | default | 0.998 ± 0.000 | 0.984 ± 0.001 | 0.952 / 0.0017 |
| | tuned | 0.998 ± 0.000 | 0.986 ± 0.001 | 0.955 / 0.0011 |
| MCFP → MTA g1g2_notime E4 | default | 0.585 ± 0.012 (0.577–0.593) | 0.572 ± 0.022 | 0.494 / 0.343 |
| | tuned | 0.593 ± 0.007 (0.585–0.601) | 0.569 ± 0.013 | 0.566 / 0.419 |
| MTA → MCFP g1g2_notime E4 | default | 0.849 ± 0.006 (0.846–0.853) | 0.821 ± 0.008 | 0.459 / 0.020 |
| | tuned | 0.839 ± 0.011 (0.836–0.843) | 0.810 ± 0.010 | 0.404 / 0.014 |

The best source-validation PR-AUC was 0.996–1.000 in every setting, so validation was almost saturated, including for the two E4 settings that score 0.59 and 0.84 on the target.

## Findings
1. **Tuning does not change any conclusion.** Within-distribution settings (E2) gain ≤ 0.004 PR-AUC. The cross-dataset gap (E4) is unchanged: +0.008 for MCFP → MTA and −0.010 for MTA → MCFP, both within about 1–2 SD. Source validation cannot see target shift, so tuning on it cannot fix shift.
2. **The one large gain is MTA `all` E3: 0.899 → 0.949 PR-AUC, 0.763 → 0.825 macro-F1.**
   - The tuned model uses `colsample_bytree` 0.33 (vs 0.8) and `min_child_weight` 8.4. With each tree seeing a third of the columns, the model can rely less on the JA3/JA4 categorical features.
   - This is consistent with E5a/E9: removing fingerprints entirely gives 0.982. Tuning only partly recovers what dropping G5 achieves.
   - The gain comes with a worse low-FPR operating point (test FPR 0.021 vs 0.012 at the val-10⁻³ threshold).
3. **MCFP all E2 halves its benign false-positive rate after tuning** (test FPR 0.151 → 0.079, macro-F1 0.954 → 0.975), but it is still far worse than the G1/G2-only model (0.0017).
4. **The default parameters were not a weak baseline.** The headline numbers elsewhere (E2–E4, E5a, E8, E9) use the defaults, and this table shows that keeping them understates performance only on MTA `all` E3.

## Caveats
- The search used the seed-0 split only; the other four seeds reuse its best parameters. For E2 this means validation came from different posts or captures than in seeds 1–4, so the tuned parameters are not overfitted to their validation sets.
- For E3 the validation set is the latest 15% of the ≤2022 period. It is temporally closer to the test set than a random validation set would be, but it still contains no post-2022 data.
- 40 trials is a modest budget. With validation PR-AUC at 0.996–1.000 the objective was nearly flat, so more trials would mostly be choosing among ties.
- Only XGBoost was tuned. The other model families (`SUMMARY_models.md`) use their fixed defaults.
