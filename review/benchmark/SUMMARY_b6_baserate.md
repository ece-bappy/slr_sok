# Batch 6 item 1: realistic base rates (8 Nov 2026)

`run_b6.py baserate`, launched in `launch_batch6.sh` (A2, 8 Nov 15:02–15:04 WITA; exit 0). It reuses the saved 20-seed test predictions of item 2, plus C-Cert DT/RF predictions computed here with the `r24_benchmark.py` setup (20 seeds). CSVs are in `b6_baserate/`.

**Why:** every headline test set has 34–92% malicious flows. A deployed sensor sees far fewer (Arp et al., "Dos and Don'ts", base-rate fallacy).

**How:**
- The benign test flows are **reweighted** so that the malicious share becomes 1%, 0.1% or 0.01%; malicious flows keep weight 1.
- PR-AUC is recomputed with these weights.
- Recall and the false-alarm rate do not depend on prevalence. Precision at the validation-selected thresholds does, and is recomputed.
- Thresholds stay those chosen on validation (max-F1, and FPR 10⁻³).
- "False alarms per 10k benign flows" = test FPR × 10⁴.

## Results (mean over 20 seeds; strict threshold = validation FPR 10⁻³)

| Setting, features | Recall | False alarms per 10k benign | Precision as tested | Precision at 1% | at 0.1% | at 0.01% | PR-AUC at 1% / 0.1% / 0.01% |
|---|---|---|---|---|---|---|---|
| MTA E3, G1–G5 | 0.52 | 101 | 0.98 | 0.41 | 0.08 | 0.01 | 0.50 / 0.32 / 0.22 |
| **MTA E3, no G5** | 0.45 | **22** | 0.99 | **0.68** | **0.18** | 0.02 | 0.61 / 0.32 / 0.23 |
| **MTA E3, Zeek-free (G1–G3)** | 0.33 | **11** | 1.00 | **0.77** | **0.28** | 0.04 | 0.56 / 0.32 / 0.24 |
| MCFP → MTA, G1–G5, no timing | 1.00 | 9,767 | 0.50 | 0.01 | 0.001 | 0.0001 | 0.03 / 0.004 / 0.0005 |
| MCFP → MTA, no G5, no timing | 0.98 | 5,596 | 0.63 | 0.02 | 0.002 | 0.0002 | 0.06 / 0.01 / 0.006 |
| C-Cert RF, MTA E3 (covered flows only) † | 0.46 | 20 | 0.99 | 0.88 | 0.81 | 0.80 | 0.55 / 0.52 / 0.51 |
| C-Cert DT, MTA E3 (covered flows only) † | 0.28 | 0 | 1.00 | 1.00 | 1.00 | 1.00 | 0.52 / 0.51 / 0.51 |
| C-Cert RF, MCFP → MTA (covered flows only) † | 0.42 | 36 | 0.99 | 0.54 | 0.11 | 0.01 | 0.34 / 0.09 / 0.01 |

† C-Cert scores only flows with a certificate size: 45% of MTA flows, and 28% of malicious ones (`SUMMARY_r24.md`). Recall over all malicious MTA flows is therefore ≈ 0.28 × the table value (≈ 0.08–0.13). Its precision is high because the few certificate sizes it flags are almost never seen on covered benign flows in this test set (0–20 false alarms per 10k).

At the validation max-F1 threshold the numbers are worse (`summary.csv`). For example, MTA E3 no G5: recall 0.61, 81 false alarms per 10k, precision 0.44 at 1%.

## Findings
1. **At realistic base rates, alerts are mostly false even for the best temporal model.**
   - MTA E3 without G5: 22 false alarms per 10k benign flows. At a 0.1% malicious share, 18% of alerts are true; at 0.01%, 2%.
   - The hash model (G1–G5) raises 4.6× more false alarms (101 per 10k), so it is 0.08 / 0.01 at 0.1% / 0.01%.
   - The Zeek-free set trades recall for precision: 11 per 10k, so 0.28 at 0.1%.
2. **Cross-dataset models are unusable at any realistic base rate.** Their validated threshold passes 56–98% of benign target flows, so precision equals the base rate (0.02 or worse at 1%).
3. **High PR-AUC on balanced test sets says little about deployment.** The no-G5 model's 0.983 becomes 0.61 at 1% prevalence and 0.32 at 0.1%.
4. **The low-capacity C-Cert has the best precision**, but on a minority of flows: it only sees flows with a certificate size, and catches roughly a tenth of all malicious MTA flows.

## Caveats
- Reweighting assumes the test benign flows are representative of the benign population at the lower base rate. MTA benign is same-host background traffic (see `SUMMARY_b6_hosts.md` for the host-level counterpart).
- Precision at 0.01% rests on a handful of false positives per seed: FPR resolution is about 1.5 per 10k on the 6,696 benign E3 test flows.
