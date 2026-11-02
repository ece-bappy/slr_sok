# E9 fingerprint drift (2 Nov 2026)

`scripts/run_e9.py` with XGBoost, 5 seeds, the same protocol as E3: per-set dedup, 1:1 training balance, thresholds from validation only. Launched in `scripts/launch_batch3.sh` (A2, 2 Nov 15:09 WITA, log `/data/tls-sok/out/batch3_1509.log`; exit 0). CSVs are in `e9/`.

**Question:** do JA3 or JA4 fingerprints help or hurt when the test traffic comes from a later period? All other features stay fixed.

**Scenarios** (test = MTA 2023–26 in both cases; 12,882 flows, 48% malicious):
- `mta_old>mta_new`: train on MTA ≤2022 (the E3 split); validation = the latest 15% of the training period.
- `mcfp>mta_new`: train on MCFP (2013–2018 captures, 15% stratified validation set). This is a combined time and dataset shift.

**Feature sets:**
- `no_fp` = G1–G4.
- `fp_ja3` = G1–G4 + JA3, JA3S; `fp_ja4` = G1–G4 + JA4, JA4S; `fp_both` = G1–G4 + all four.
- Fingerprint-only: `only_ja3` (JA3 + JA3S), `only_ja4` (JA4 + JA4S), `only_ja3c` / `only_ja4c` (client hash only).

Columns are limited to those present in both datasets. Cells give mean ± SD over 5 seeds, with the mean 95% bootstrap CI in brackets.

## Results

| Set | MTA ≤2022 → 2023–26 PR-AUC | macro-F1 | MCFP → MTA 2023–26 PR-AUC | macro-F1 (test FPR at val-FPR 10⁻³) |
|---|---|---|---|---|
| no_fp | **0.982** ± 0.001 (0.980–0.985) | **0.787** ± 0.023 (0.779–0.794) | **0.794** ± 0.009 (0.781–0.806) | **0.776** ± 0.026 (0.25) |
| fp_ja3 | 0.894 ± 0.005 (0.888–0.899) | 0.761 ± 0.006 (0.753–0.768) | 0.716 ± 0.030 (0.704–0.728) | 0.324 (1.00) |
| fp_ja4 | 0.895 ± 0.006 (0.890–0.901) | 0.760 ± 0.013 (0.751–0.767) | 0.710 ± 0.020 (0.698–0.722) | 0.324 (1.00) |
| fp_both | 0.901 ± 0.003 (0.895–0.906) | 0.767 ± 0.014 (0.760–0.775) | 0.665 ± 0.042 (0.652–0.677) | 0.324 (1.00) |
| only_ja3 † | 0.278 ± 0.037 (0.235–0.329) | 0.560 ± 0.044 | 0.155 ± 0.044 (0.132–0.182) | 0.129 |
| only_ja4 † | 0.498 ± 0.027 (0.411–0.592) | 0.605 ± 0.011 | 0.345 ± 0.009 (0.281–0.414) | 0.255 |
| only_ja3c † | 0.122 (= prevalence; ROC 0.5) | 0.109 | 0.122 (= prevalence) | 0.109 |
| only_ja4c † | 0.533 (= prevalence; ROC 0.5) | 0.348 | 0.533 (= prevalence) | 0.348 |

† Fingerprint-only sets are deduplicated on their own 1–2 columns, so each row is a distinct fingerprint value or value pair, not a flow. Their test sets are small (only_ja3 1,418; only_ja4 278; only_ja3c 1,211; only_ja4c 45), and their prevalence differs from the 48% of the flow-level sets. The only_ja3c and only_ja4c test sets have no values in common with training, so the model outputs a constant and PR-AUC equals prevalence.

## Unseen fingerprints

Counts are on the MTA 2023–26 test set at flow level (the `fp_*` sets, seed 0), against the training rows before balancing.

| Fingerprint | Distinct test values | Never seen in MTA ≤2022 | Test flows with an unseen value (mal / bg) | Never seen in MCFP |
|---|---|---|---|---|
| JA3 (client) | 1,245 | **1,230 (98.8%)** | 6,837 / 12,882 = **53%** (2,958 / 3,879) | 1,245 (100%), all flows |
| JA4 (client) | 85 | 69 (81%) | 6,667 = **52%** (2,936 / 3,731) | 85 (100%), all flows |
| JA3S (server) | 151 | 62 (41%) | 820 = 6% (281 / 539) | 111 (74%), 8,685 flows = 67% |
| JA4S (server) | 165 | 69 (42%) | 839 = 7% (297 / 542) | 125 (76%), 9,189 flows = 71% |

## Findings

1. **Adding any fingerprint hurts under temporal drift.**
   - On MTA ≤2022 → 2023–26, PR-AUC falls from 0.982 (no fingerprints) to 0.894–0.901 (JA3, JA4 or both); macro-F1 falls from 0.787 to 0.760–0.767.
   - JA4 is no more robust than JA3 here (0.895 vs 0.894), even though it has 15× fewer distinct values.
2. **Half of the later-period flows carry a client fingerprint never seen in training**, for both JA3 (53%) and JA4 (52%). This affects both classes: 48% of malicious and 58% of background flows for JA3. The model learns "this exact hash was malicious up to 2022" and that does not carry forward. Server fingerprints are more stable (6–7% of flows unseen).
3. **Under combined time and dataset shift (MCFP → MTA 2023–26), every client fingerprint is new.**
   - With fingerprints, the source-validated threshold flags 100% of test flows as malicious (macro-F1 0.324). Without them it keeps an operating point (macro-F1 0.776; test FPR 0.25, still far above the 10⁻³ target).
   - PR-AUC also drops: 0.794 → 0.665–0.716.
4. **Fingerprints alone do not detect new malware.** Fingerprint-only models score at or below prevalence on the later period: JA3 0.28, JA4 0.50 on distinct value pairs, and exactly prevalence on client-only hashes.

## Caveats
- The MTA background is "same-pcap, popular-domain" traffic (see `mta/data_card.json`), so its fingerprint mix follows the browsers and OSes of the infected-host sandboxes. Real enterprise background would have a different, and possibly more stable, JA3/JA4 distribution.
- The MCFP scenario mixes time drift with dataset shift; the MTA-only scenario is the cleaner drift measurement.
- XGBoost encodes fingerprints as categorical features; unseen categories go down the default branch. Other encodings (hashing, frequency, or embedding of JA4 parts) were not tried. JA4's structured sub-fields (cipher count, extension count, ALPN) are not split out here; G3 already carries similar handshake fields.
- Unseen counts are from seed 0. The temporal split is deterministic, so they do not vary by seed for `mta_old>mta_new`.
