# E1–E3 benchmark: RAID 2024 and HIKARI (first run, 1 Nov 2026)

Run on A2: `scripts/build_tables.py` → `scripts/run_benchmark.py`. Per-dataset CSVs are in `raid/` and `hikari/`: per seed, per TLS version, shortcut screen, importance, dedup and data card.

**Protocol**
- **Model:** XGBoost with fixed hyperparameters (1,000 trees max, depth 8, learning rate 0.1) and early stopping on validation. No tuning yet; the deep model comes later.
- **Leakage controls:**
  - Within-class duplicate feature vectors, and vectors that appear in both classes, are removed per feature set before splitting.
  - The majority class is subsampled to 1:1 in training only.
- **Thresholds:** taken from validation only (max macro-F1, and FPR = 10⁻³).
- **Repetition and CIs:** 5 seeds; bootstrap 95% CIs on the test set (200 resamples). Means ± SD over seeds are shown below.
- **Feature sets:** `all` = G1–G5. `g1g2` = flow statistics + first-20-packet sequences. `g1g2_notime` = `g1g2` without inter-arrival and duration features (plan §5.2: timing reflects the capture network).

## Datasets as built

| | RAID 2024 | HIKARI (clean subset) |
|---|---|---|
| Classes | 791,226 Metasploit C2 / 503,087 benign TLS flows | 6,001 attack (brute force, brute-force XML) / 135,044 benign |
| Hosts | C2: **1 client → 1 server** (one Docker pair); benign: 6 clients → 58k servers | attack: **2 client IPs** (one per year); benign: 4,731 clients |
| Time | C2: Apr 2022; benign: Jan 2024 | 2021 (247 attack flows) and 2022 (5,754 attack flows) |
| TLS versions | C2 50/50 TLS 1.2/1.3; benign 45/44% 1.2/1.3, 10.5% no ServerHello | attacks: all TLS 1.3; benign 26% 1.2, 58% 1.3 |
| Features | G1 57, G2 60, G3 45, G4 8, G5 4 | G1/G2 only (user decision 1) |
| Duplicates removed | 199,845 (`all`); 691,324 (`g1g2_notime`: C2 flows repeat) | 7,061 (`g1g2`); 82,407 (`g1g2_notime`) |

**HIKARI labels.** The released label tables (`ALLFLOWMETER_HIKARI2021/2022.csv`) do not match the released pcaps well:
- of 1.84M extracted port-443 flows, 1.63M have no label and 71k have contradictory labels;
- the two large 2022 pcaps are mostly unlabelled;
- the anonymised benign pcaps barely match at all;
- the attacker IPs also originate most of the "benign" flows, so an IP rule cannot recover the labels.

The benchmark uses only flows with exactly one label (user decision: clean subset). That is mostly background and attack traffic from the attack pcaps.

## Results (test set, mean ± SD over 5 seeds)

| Dataset | Features | Exp | PR-AUC | Macro-F1 | Recall malicious | Recall benign | TPR @ val-FPR 10⁻³ |
|---|---|---|---|---|---|---|---|
| RAID | all | E1 random | 1.000 ± 0 | 1.000 ± 0 | 1.000 | 1.000 | 1.000 |
| RAID | all | E2 capture-grouped | 1.000 ± 0 | 1.000 ± 0 | 1.000 | 1.000 | 1.000 |
| RAID | g1g2 | E1 | 1.000 ± 0 | 0.999 ± 0.000 | 0.999 | 0.999 | 1.000 |
| RAID | g1g2 | E2 | 1.000 ± 0 | 0.999 ± 0.000 | 0.999 | 1.000 | 1.000 |
| RAID | g1g2_notime | E1 | 1.000 ± 0 | 0.999 ± 0.000 | 0.998 | 1.000 | 1.000 |
| RAID | g1g2_notime | E2 | 1.000 ± 0 | 0.999 ± 0.000 | 1.000 | 0.998 | 1.000 |
| RAID | any | E3 | infeasible: capture year = class (C2 2022, benign 2024) | | | | |
| HIKARI | g1g2 | E1 random | 0.9998 ± 0.0004 | 0.995 ± 0.002 | 0.980 | 1.000 | 1.000 |
| HIKARI | g1g2 | E2 host-grouped | 0.166 ± 0.099 | 0.506 ± 0.013 | 0.008 | 1.000 | 0.011 |
| HIKARI | g1g2 | E3 2021→2022 | 0.454 ± 0.112 | 0.484 ± 0.000 | 0.000 | 1.000 | 0.002 |
| HIKARI | g1g2_notime | E1 | 0.9999 ± 0.0002 | 0.995 ± 0.001 | 0.996 | 0.999 | 0.996 |
| HIKARI | g1g2_notime | E2 | 0.236 ± 0.092 | 0.509 ± 0.023 | 0.019 | 0.998 | 0.139 |
| HIKARI | g1g2_notime | E3 | 0.902 ± 0.050 | 0.773 ± 0.127 | 0.433 | 1.000 | 0.417 |

Per-TLS-version results are in `*/results_per_tls_version.csv`.
- RAID scores the same on TLS 1.2 and 1.3.
- In HIKARI every attack flow is TLS 1.3, so the TLS 1.2 stratum contains only benign flows; that skew is itself a dataset property to report.

## Leakage and shortcut flags

1. **RAID is separable by the capture environment, not by C2 behaviour.**
   - 25 single features reach training AUC ≥ 0.99 on their own (all 25 the screen lists for `all`): JA3/JA4, ALPN, cipher count, extension flags, SNI presence, and mean inter-arrival time.
   - The top-gain features are the second packet's inter-arrival time (`g2_piat_01`) and the cipher count.
   - Removing timing does not help: without it, FIN-packet counts and packet sizes still give macro-F1 0.999.
   - The capture-grouped E2 cannot expose this, because all 48 C2 captures share one client, one server and one Metasploit setup.
   - **Conclusion:** within RAID, E1 = E2 = "perfect" says nothing about generalisation. RAID is usable only for cross-dataset tests (E4) or with the benign side drawn from another environment.
2. **HIKARI shows the classic collapse.**
   - E1 is near-perfect (PR-AUC ≈ 1.0).
   - E2, with an unseen attacker host, falls to PR-AUC 0.17–0.24 and malicious recall ≈ 1–2%.
   - With only two attacker hosts, E2 always trains on the 2022 attacker and tests on the 2021 one (247 flows), so it is also a reverse-time test.
   - **E3 has a small training set:** it trains on only 210 attack flows (2021).
   - Timing features hurt transfer: E3 PR-AUC is 0.45 with timing and 0.90 without, though recall at the validation threshold stays low (0.43, SD 0.25).
   - The most important feature is `src2dst_rst_packets` (how the attack tool closes connections), which is tool behaviour, not TLS.
3. **Duplicates.** RAID C2 flows repeat heavily: 87% of C2 rows are exact duplicates once timing is removed. Without deduplication, E1 test sets would contain copies of training flows.

## Not yet done
- Hyperparameter tuning (Optuna).
- Other model families (RF, LightGBM, LR) and the deep model (needs PyTorch on A2).
- E4–E9.
- Using HIKARI's TLS features as the E5b shortcut example.
