# Batch 6 item 1: realistic base rates (8 Nov 2026)

`run_b6.py baserate`, launched in `launch_batch6.sh` (A2, 8 Nov 15:02–15:04 WITA; exit 0). It reuses the saved 20-seed test predictions of item 2, plus C-Cert DT/RF predictions computed here with the `r24_benchmark.py` setup (20 seeds). CSVs are in `b6_baserate/`.

**Why:** every headline test set has 34–92% malicious flows. A deployed sensor sees far fewer (Arp et al., "Dos and Don'ts", base-rate fallacy).

**How:**
- The benign test flows are **reweighted** so that the malicious share becomes 1%, 0.1% or 0.01%; malicious flows keep weight 1.
- PR-AUC is recomputed with these weights.
- Recall and the false-alarm rate do not depend on prevalence. Precision at the validation-selected thresholds does, and is recomputed.
- Thresholds stay those chosen on validation (max-F1, and FPR 10⁻³).
- "False alarms per 10k benign flows" = test FPR × 10⁴.

## Results (20 seeds; strict threshold = validation FPR 10⁻³)

**Basis of the precision columns (corrected 8 Nov after Main's check).**
- Precision is **pooled over seeds**: π·R / (π·R + FPR·(1 − π)), with R the mean recall and FPR the mean false-positive rate over the 20 seeds, computed on the same test flows and at the same threshold as the recall and false-alarm columns.
- The first version of this table averaged per-seed precisions instead. That overstates precision whenever false alarms are concentrated in a few seeds. It mattered most for C-Cert RF on MTA E3: 16 of 20 seeds have zero false alarms (precision 1.0) and 4 seeds have 28–152 per 10k. The mean of per-seed precisions was 0.88 / 0.81 / 0.80, but the pooled values are 0.70 / 0.19 / 0.02. The G1–G5 row was also inflated (0.41 / 0.08 / 0.01 → 0.34 / 0.05 / 0.005).
- The per-seed medians and the number of zero-false-alarm seeds are in `pooled_precision.csv`.

| Setting, features | Recall R | False alarms per 10k benign (FPR × 10⁴) | Seeds with 0 false alarms | Pooled precision at 1% | at 0.1% | at 0.01% |
|---|---|---|---|---|---|---|
| MTA E3, G1–G5 | 0.52 | 101 | 0 / 20 | 0.34 | 0.05 | 0.005 |
| **MTA E3, no G5** | 0.45 | **22** | 0 / 20 | **0.67** | **0.17** | 0.02 |
| **MTA E3, Zeek-free (G1–G3)** | 0.33 | **11** | 0 / 20 | **0.76** | **0.24** | 0.03 |
| MCFP → MTA, G1–G5, no timing | 1.00 | 9,767 | 0 / 20 | 0.010 | 0.001 | 0.0001 |
| MCFP → MTA, no G5, no timing | 0.98 | 5,596 | 0 / 20 | 0.017 | 0.002 | 0.0002 |
| C-Cert RF, MTA E3 (covered flows only) † | 0.46 | 20 | **16 / 20** | 0.70 | 0.19 | 0.02 |
| C-Cert DT, MTA E3 (covered flows only) † | 0.28 | 0 | 20 / 20 | 1.00 ‡ | 1.00 ‡ | 1.00 ‡ |
| C-Cert RF, MCFP → MTA (covered flows only) † | 0.42 | 36 | 0 / 20 | 0.54 | 0.10 | 0.01 |

Weighted PR-AUC (reweighted test set, mean over seeds) at 1% / 0.1% / 0.01%: G1–G5 0.50 / 0.32 / 0.22; no G5 0.61 / 0.32 / 0.23; Zeek-free 0.56 / 0.32 / 0.24; cross-dataset ≤ 0.06 / 0.01 / 0.006.

† C-Cert scores only flows with a certificate size: 45% of MTA flows, and 28% of malicious ones (`SUMMARY_r24.md`). Its recall over *all* malicious MTA flows is therefore ≈ 0.28 × the table value (≈ 0.08–0.13). Its false-alarm column is on covered benign flows.

‡ The C-Cert DT flags no covered benign test flow in any seed. Its precision is 1.0 only within the test set's resolution: the 95% upper bound on its FPR is 3 / 5,786 covered benign test flows ≈ 5.2 per 10k, which still gives ≥ 0.35 at 0.1% and ≥ 0.05 at 0.01%.

At the validation max-F1 threshold the numbers are worse (`summary.csv`). For example, MTA E3 no G5: recall 0.61, 81 false alarms per 10k, pooled precision ≈ 0.43 at 1%.

## Findings
1. **At realistic base rates, alerts are mostly false even for the best temporal model.**
   - MTA E3 without G5: 22 false alarms per 10k benign flows. At a 0.1% malicious share, 17% of alerts are true; at 0.01%, 2%.
   - The hash model (G1–G5) raises 4.6× more false alarms (101 per 10k), so it is 0.05 / 0.005 at 0.1% / 0.01%.
   - The Zeek-free set trades recall for precision: 11 per 10k, so 0.24 at 0.1%.
2. **Cross-dataset models are unusable at any realistic base rate.** Their validated threshold passes 56–98% of benign target flows, so precision equals the base rate (0.02 or worse at 1%).
3. **High PR-AUC on balanced test sets says little about deployment.** The no-G5 model's 0.983 becomes 0.61 at 1% prevalence and 0.32 at 0.1%.
4. **C-Cert is no exception once precision is pooled.** C-Cert RF reaches 0.70 / 0.19 / 0.02, about the same as the no-G5 model, but its false alarms come in bursts (4 of 20 seeds). It covers a minority of flows and catches roughly a tenth of all malicious MTA flows. Only the depth-1 C-Cert DT has no observed false alarm, at recall 0.28 on covered flows (≈ 0.08 overall).

## Caveats
- Reweighting assumes the test benign flows are representative of the benign population at the lower base rate. MTA benign is same-host background traffic (see `SUMMARY_b6_hosts.md` for the host-level counterpart).
- Precision at 0.01% rests on a handful of false positives per seed: FPR resolution is about 1.5 per 10k on the 6,696 benign E3 test flows.
