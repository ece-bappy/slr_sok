# Batch 7: the closest prior work's protocol on our data (8 Nov 2026)

Wang, Fok & Thing, *Computers & Security* 113 (2022) 102542, is the closest prior work. They pool roughly balanced flows sampled at random from five public datasets, report stratified 5-fold cross-validation on the pool, and recommend pooled training as the fix for their cross-dataset failure. This batch runs that protocol on our four sources, so the paper can show the two numbers side by side: what their protocol reports, and what a held-out source gives.

`scripts/run_b7.py`, launched by `scripts/launch_batch7.sh` (A2, 8 Nov 19:51–20:07 WITA, log `/data/tls-sok/out/batch7_1951.log`, exit 0). CSVs are in `b7_wang/`.

## Setup
- **Pool, one per seed.** Every source contributes the same number of deduplicated flows per class, so the pool is equal per source and 1:1 overall (`pool.json`):
  - **G1+G2 without timing:** MTA, MCFP, RAID and the HIKARI clean subset, 2,895 flows per class per source (the size of HIKARI's malicious class), 23,160 flows in all.
  - **No G5 (G1–G4):** MTA, MCFP and RAID, 16,572 flows per class per source (MTA's benign class), 99,432 flows. HIKARI has no TLS fields, so it is not in this pool.
- **Splits of the same pool:**
  - **Random:** stratified 5-fold CV, flows assigned to folds at random. This is Wang's protocol.
  - **Grouped:** 5 folds grouped by MTA post, MCFP capture, RAID pcap or HIKARI client host. This is our protocol's grouping.
  - Folds are stratified on source × label, so each fold keeps the pool's mix.
- **Training and thresholds:** inside each training fold, a 15% stratified validation split selects the thresholds (max-F1 and FPR 10⁻³). Training uses a 1:1 sample.
- **Models:** XGBoost defaults, and random forest (Wang's best family) with our fixed hyperparameters. 5 seeds.
- **Metrics:** ROC and PR-AUC on the out-of-fold scores of the whole pool, with 200-sample bootstrap CIs. The same out-of-fold scores are also restricted to each source ("per-source ROC inside the CV"). Threshold metrics are per fold.
- **Held-out source:** the matching leave-one-dataset-out rows from batch 6 (`SUMMARY_b6_lodo.md`, XGBoost, not rerun). Each source there is tested after training only on the *other* sources.

## Results (ROC-AUC, mean over 5 seeds; seed-0 bootstrap 95% CI in brackets where informative)

**G1+G2 without timing** (4 sources)

| Source | Wang protocol: pooled random CV (XGB / RF) | Same pool, grouped CV (XGB / RF) | Held-out source, b6 LODO (XGB) |
|---|---|---|---|
| **Whole pool** | **0.999** [0.999–0.999] / 0.998 | 0.946 ± 0.011 / 0.942 ± 0.006 (mean ± SD over seeds) | – |
| MTA | 0.995 / 0.993 | 0.986 / 0.981 | **0.559** |
| MCFP | 0.997 / 0.992 | 0.988 / 0.984 | 0.906 |
| RAID | 1.000 / 1.000 | 1.000 / 1.000 | 0.538 |
| HIKARI ‡ | 1.000 / 1.000 | 0.899 / 0.913 | 0.132 |

PR-AUC on the whole pool (prevalence 0.50): random 0.999 / 0.998, grouped 0.953 / 0.949.
Threshold metrics, XGB:
- **Random CV:** macro-F1 0.986; TPR 0.92 at a test FPR of 0.09%.
- **Grouped CV:** macro-F1 0.880; TPR 0.74 at a test FPR of 0.35%.

**No G5 (G1–G4)** (3 sources)

| Source | Wang protocol: pooled random CV (XGB / RF) | Same pool, grouped CV (XGB / RF) | Held-out source, b6 LODO (XGB) |
|---|---|---|---|
| **Whole pool** | **1.000** / 1.000 | 1.000 / 0.999 | – |
| MTA | 1.000 / 0.999 | 0.999 / 0.998 | **0.922** (test FPR 0.31 at the validated strict threshold) |
| MCFP | 1.000 / 1.000 | 0.999 / 1.000 | 0.991 |
| RAID | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 |

Threshold metrics, XGB:
- **Random CV:** macro-F1 0.998; TPR 0.997 at a test FPR of 0.08%.
- **Grouped CV:** macro-F1 0.993; TPR 0.99 at a test FPR of 0.56%.

Seed SDs of the out-of-fold ROC are ≤ 0.002, except grouped G1+G2 (whole pool 0.006–0.011, HIKARI 0.02). In grouped G1+G2, per-fold ROC ranges from 0.84 to 1.00. Folds that hold one of HIKARI's two attacker hosts are the low ones.

‡ HIKARI's malicious flows come from two attacker IPs. Grouping by client host makes its grouped row a 2-attacker transfer test, as in E2/E3. Its held-out ROC (below chance) repeats the inversion in `SUMMARY_b6_lodo.md`.

## Findings
1. **Wang's protocol on our data reproduces their kind of number.** Pooled stratified random CV gives ROC 0.998–1.000 and macro-F1 0.98–1.00, for both feature sets and both model families. On these numbers alone, pooled training would look like a solved fix.
2. **Random-split leakage explains only a small part of it.** Grouping the same pool by capture, post or host lowers the pooled ROC from 0.999 to 0.946 with G1+G2. Per source, though, MTA, MCFP and RAID stay at 0.98–1.00. HIKARI falls to 0.90 (two attacker hosts). The rest of the pooled drop comes from scores that are less comparable across sources once folds are grouped. With handshake fields nothing moves (1.000 → 1.000; MTA 0.999).
3. **The held-out source is where it breaks, i.e. the dataset shortcut.** The same MTA flows that score 0.986 (G1+G2) or 0.999 (no G5) when other MTA flows are in training score 0.559 or 0.922 once MTA is held out, with a test FPR of 0.31 at the validated threshold. RAID drops from 1.000 to 0.538 (G1+G2), and HIKARI from 0.90–1.00 to 0.13. Pooled CV, random or grouped, measures how well the model separates environments it has already seen. That is the shortcut the origin probe finds (≥ 0.98 balanced accuracy on every pool, `SUMMARY_b6_lodo.md`).
4. **Suggested wording:** "Under the pooled protocol of Wang et al. (stratified 5-fold CV on a source-balanced pool), our data gives ROC 0.999 (G1+G2 without timing) and 1.000 (G1–G4). Grouping the same pool by capture, post or host barely changes this (0.946 / 1.000; MTA alone 0.986 / 0.999). Holding the source out gives 0.559 / 0.922 on MTA. Pooled training does not fix cross-dataset failure. It hides it, because every test environment is also in training."

## Caveats
- Our four sources are not Wang's five datasets, and our feature groups are not their feature set. The comparison is about the protocol, not a reproduction of their numbers.
- The held-out column comes from batch 6. That pool was capped at 50k flows per class per source and not equalised across sources, so its training pool differs from the one here. It was trained on the other sources only, with XGBoost and 5 seeds.
- Per-source ROC inside the CV ranks flows of one source using a model trained on all sources' folds. It is directly comparable to the held-out column, which ranks the same source's flows.
- Out-of-fold scores are pooled across the five fold models before computing ROC (the usual CV practice). The mean per-fold ROC agrees: random 0.999 / 0.998, grouped 0.967 / 0.965 (G1+G2).
