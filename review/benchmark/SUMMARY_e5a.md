# E5a feature-group ablation (2 Nov 2026)

`run_benchmark.py` / `run_e4.py` with XGBoost, 5 seeds, the same protocol as E1–E4: per-set dedup, 1:1 training balance, thresholds from validation only. Launched as part of `scripts/launch_batch3.sh` (A2, started 15:09 WITA on 2 Nov, log `/data/tls-sok/out/batch3_1509.log`); every step exited 0. CSVs are in `e5a_mta/`, `e5a_mcfp/` and `e5a_e4/`.

Groups: G1 NFStream flow statistics, G2 first-20-packet sizes/directions/IATs, G3 handshake fields, G4 certificate, G5 JA3/JA4/JA3S/JA4S. `only_gX` uses that group alone; `loo_gX` uses the other four. The E4 check uses the `_notime` variants (timing features removed from G1/G2), as in `SUMMARY_e4.md`.

Cells give mean ± SD over 5 seeds, followed by the 95% bootstrap CI (the mean of the per-seed CI bounds). Macro-F1 is at the validation max-F1 threshold.

## MTA (E2 post-grouped, E3 temporal ≤2022 → 2023–26)

Reference with all groups: E2 PR-AUC 0.994 / macro-F1 0.910; E3 0.899 / 0.763 (`tuning/`, default parameters).

| Set | #feat | E2 PR-AUC | E2 macro-F1 | E3 PR-AUC | E3 macro-F1 |
|---|---|---|---|---|---|
| only G1 | 57 | 0.955 ± 0.014 (0.952–0.957) | 0.695 ± 0.004 (0.687–0.704) | 0.907 ± 0.008 (0.901–0.912) | 0.818 ± 0.006 (0.810–0.824) |
| only G2 | 60 | 0.991 ± 0.005 (0.990–0.992) | 0.716 ± 0.034 (0.708–0.724) | 0.868 ± 0.010 (0.860–0.874) | 0.774 ± 0.002 (0.767–0.781) |
| only G3 | 45 | 0.803 ± 0.046 (0.747–0.847) | 0.812 ± 0.022 (0.777–0.842) | 0.606 ± 0.024 (0.556–0.656) | 0.693 ± 0.015 (0.668–0.719) |
| only G4 | 8 | 0.960 ± 0.018 (0.933–0.981) | **0.927** ± 0.029 (0.896–0.954) | 0.903 ± 0.004 (0.871–0.931) | **0.837** ± 0.046 (0.804–0.866) |
| only G5 | 4 | 0.578 ± 0.078 (0.472–0.682) | 0.679 ± 0.062 (0.625–0.732) | 0.282 ± 0.074 (0.231–0.336) | 0.504 ± 0.090 (0.478–0.529) |
| loo G1 | 117 | 0.993 ± 0.006 (0.992–0.994) | 0.753 ± 0.154 (0.747–0.760) | 0.900 ± 0.007 (0.895–0.905) | 0.788 ± 0.042 (0.780–0.794) |
| loo G2 | 114 | 0.981 ± 0.010 (0.979–0.983) | 0.704 ± 0.007 (0.696–0.713) | 0.889 ± 0.006 (0.883–0.895) | 0.752 ± 0.007 (0.744–0.759) |
| loo G3 | 129 | 0.994 ± 0.002 (0.993–0.995) | 0.911 ± 0.004 (0.905–0.916) | 0.898 ± 0.007 (0.893–0.903) | 0.768 ± 0.039 (0.760–0.775) |
| loo G4 | 166 | 0.992 ± 0.003 (0.991–0.992) | 0.902 ± 0.008 (0.897–0.907) | 0.893 ± 0.005 (0.887–0.899) | 0.749 ± 0.005 (0.741–0.757) |
| loo G5 | 170 | **1.000** ± 0.000 (0.999–1.000) | **0.981** ± 0.012 (0.979–0.984) | **0.982** ± 0.001 (0.980–0.985) | 0.787 ± 0.023 (0.779–0.794) |

## MCFP (E2 capture-grouped)

Reference with all groups: PR-AUC 1.000, macro-F1 0.954, test FPR 0.15 at the val-FPR-10⁻³ threshold.

| Set | PR-AUC | macro-F1 | Test FPR at val-FPR 10⁻³ |
|---|---|---|---|
| only G1 | 1.000 (1.000–1.000) | **0.992** ± 0.000 (0.991–0.993) | 0.0006 |
| only G2 | 1.000 (1.000–1.000) | 0.981 ± 0.003 (0.980–0.982) | 0.035 |
| only G3 | 0.888 ± 0.008 (0.864–0.911) | 0.917 ± 0.013 (0.900–0.932) | 0.000 |
| only G4 | 0.885 ± 0.011 (0.832–0.934) | 0.922 ± 0.005 (0.898–0.946) | 0.002 |
| only G5 | 0.426 ± 0.075 (0.358–0.507) | 0.377 ± 0.007 (0.328–0.430) | 0.60 |
| loo G1 | 1.000 | 0.980 ± 0.009 (0.979–0.982) | 0.004 |
| loo G2 | 1.000 | 0.938 ± 0.000 (0.936–0.940) | 0.20 |
| loo G3 | 1.000 (0.999–1.000) | 0.899 ± 0.003 (0.896–0.901) | 0.15 |
| loo G4 | 1.000 | 0.954 ± 0.000 (0.953–0.956) | 0.14 |
| loo G5 | 1.000 | 0.988 ± 0.000 (0.987–0.988) | 0.043 |

## Transfer check: E4 MCFP → MTA, no timing

Test prevalence is 47%, so a PR-AUC near 0.47 is chance. Reference: `g1g2_notime` 0.585.

| Set | #feat | PR-AUC | macro-F1 | TPR / test FPR at val-FPR 10⁻³ |
|---|---|---|---|---|
| only G1 | 42 | 0.448 ± 0.008 (0.441–0.456) | 0.445 ± 0.006 (0.439–0.450) | 0.21 / 0.22 |
| only G2 | 40 | **0.677** ± 0.018 (0.669–0.685) | **0.649** ± 0.012 (0.644–0.654) | 0.39 / 0.14 |
| only G3 | 45 | 0.444 ± 0.026 (0.415–0.475) | 0.609 ± 0.037 (0.591–0.626) | 0.06 / 0.03 |
| only G4 | 8 | 0.607 ± 0.017 (0.569–0.643) | 0.590 ± 0.044 (0.564–0.613) | 0.23 / 0.003 |
| only G5 | 4 | 0.178 ± 0.009 (0.160–0.198) | 0.169 ± 0.001 (0.156–0.183) | 0.95 / 0.93 |
| loo G1 | 97 | 0.653 ± 0.083 (0.644–0.662) | 0.339 ± 0.000 (0.335–0.343) | 1.00 / 0.97 |
| loo G2 | 99 | 0.762 ± 0.043 (0.753–0.770) | 0.345 ± 0.000 (0.341–0.348) | 1.00 / 0.97 |
| loo G3 | 94 | 0.567 ± 0.041 (0.559–0.575) | 0.356 ± 0.003 (0.353–0.360) | 1.00 / 0.98 |
| loo G4 | 131 | 0.691 ± 0.040 (0.683–0.699) | 0.355 ± 0.000 (0.351–0.358) | 1.00 / 0.96 |
| loo G5 | 135 | **0.808** ± 0.014 (0.801–0.815) | **0.643** ± 0.071 (0.638–0.648) | 0.98 / 0.52 |

## Findings

1. **Fingerprints (G5) are the liability.**
   - Dropping G5 gives the best model in every MTA setting: E2 1.000 / macro-F1 0.981, and E3 PR-AUC **0.982 vs 0.899** with all groups.
   - It is also the best in the MCFP → MTA transfer (0.808 vs 0.65–0.76 for the other leave-one-out sets).
   - On its own, G5 is weak (MTA E3 0.28, below the 0.48 prevalence) and anti-predictive across datasets (0.18 vs 0.47).
   - This matches E9 (`SUMMARY_e9.md`): most test-period JA3/JA4 values were never seen in training.
2. **No single group is necessary on MTA.** Removing G1, G2, G3 or G4 moves E2 PR-AUC by ≤ 0.013 and E3 by ≤ 0.01. The information is redundant across groups.
3. **The certificate (8 features) is the strongest small group on MTA.** G4 alone reaches E2 0.960 / macro-F1 0.927 and E3 0.903 / 0.837, the best E3 macro-F1 of any set. It is not in TLS 1.3 (see E8), and it may encode case-era hosting habits.
4. **On MCFP, flow statistics alone are perfect** (G1 1.000, macro-F1 0.992, test FPR 0.0006). This is the capture-level shortcut already documented in `SUMMARY_mta_mcfp.md`. Sets that combine G1 with TLS groups give 14–20% benign false positives on unseen Normal captures (all groups 0.15; loo G2/G3/G4 0.14–0.20), against 0.06% for G1 alone.
5. **In cross-dataset transfer, the scores do not survive the validation threshold.**
   - Every 4-group set except loo G5 ranks somewhat (PR-AUC 0.57–0.76), but at the source-validated threshold it flags 96–98% of MTA background (macro-F1 ≈ 0.34).
   - The only sets that keep a usable operating point are small and timing-free: G2 alone (0.677 / 0.649) and loo G5.

## Caveats
- Each set is deduplicated on its own columns, so the test populations differ slightly between rows (most visibly for only G5: 4 categorical columns collapse to distinct value combinations; see `dedup.json`). PR-AUCs should be compared against each row's own prevalence.
- MCFP E2 is near ceiling, so its ablation separates sets mainly through FPR and macro-F1, not PR-AUC.
- Only XGBoost was used. `SUMMARY_models.md` shows that conclusions at the level of feature sets have held across model families so far, but this was not re-checked per group.
- E3 on MCFP is infeasible (no year split), as before.
