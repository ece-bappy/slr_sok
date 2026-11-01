# E6 early detection (1 Nov 2026)

`run_benchmark.py --sets early_{3,5,10,20}[_notime],all,all_notime` (XGBoost, 5 seeds). CSVs are in `e6_mta/` and `e6_mcfp/`.

**Features at packet N** (`early_features` in `run_benchmark.py`) use only what is visible after the first N packets of the flow, counted including the TCP handshake:
- Sizes, directions and inter-arrival times of packets 1..N, plus per-direction counts, bytes, and size and IAT statistics.
- ClientHello fields (G3 client side, JA3/JA4) only if the ClientHello is at packet ≤ N.
- ServerHello fields (JA3S/JA4S) only if the ServerHello is at packet ≤ N. Certificate fields (G4) only if the Certificate is at packet ≤ N.
- `has_server_hello` is defined as "ServerHello by packet N".

On MTA the ClientHello is packet 4 (median; range 3–14) and the ServerHello packet 6 (range 5–21). So N = 3 is the TCP handshake only; N = 5 adds the ClientHello; N = 10 adds the ServerHello and usually the certificate.

## Results (PR-AUC, mean ± SD over 5 seeds; rows left after dedup in brackets)

| N | MTA E2 | MTA E3 | MCFP E2 |
|---|---|---|---|
| 3 | 0.911 ± 0.007 [3,431 of 62,347] | 0.636 | 0.984 [21,779 of 1.56M] |
| 5 | 0.995 [38,794] | 0.860 | 0.9999 |
| 10 | 0.970 [59,522] | 0.896 | 1.0000 |
| 20 | 0.991 [62,323] | 0.901 | 1.0000 |
| full flow (`all`) | 0.996 | 0.901 | 0.9999 (test FPR 0.15) |
| **without timing** | | | |
| 3 | not evaluable [26 rows] | infeasible | 0.25 ± 0.20 [644] |
| 5 | 0.759 [4,979] | 0.374 | 0.997 |
| 10 | 0.973 [14,142] | 0.782 | 0.963 |
| 20 | 0.997 [28,015] | 0.845 | 0.962 |
| full flow (`all_notime`) | 0.996 [31,002] | 0.858 | 0.9999 |

## Findings

1. **By packet 20, early detection is as good as full-flow detection.** E2 and E3 at N = 20 are within 0.005 PR-AUC of the full flow on MTA, and within 0.01 without timing on E2.
2. **The early jump is the ClientHello, not behaviour.** On MTA, going from N = 3 to N = 5 (ClientHello visible) raises E2 PR-AUC from 0.91 to 0.995. That jump is JA3/JA4 and other ClientHello fields, the same case-specific fingerprints as in E5b and E8.
3. **N = 3 numbers are artefacts and should not be reported as detection.**
   - The first three packets (SYN, SYN-ACK, ACK) are identical in size across classes. Dedup drops every flow whose feature vector occurs in both classes: 87% of MTA flows with timing, 99.8% without timing, and 74% / 99% of MCFP.
   - The remaining scores therefore describe a small, unrepresentative residue.
   - With timing, the residue is separated by the TCP round-trip time, which is an environment signal (sandbox vs user network), not a malware one.
4. **Temporal drift hits early features harder.** MTA E3 at N = 5 without timing reaches only 0.37 PR-AUC, against 0.86 for the full flow without timing.
5. **Operating points are unstable at intermediate N.** MTA E2 macro-F1 is 0.96 at N = 5, 0.73 at N = 10 and 0.66 at N = 20, while PR-AUC stays ≥ 0.97: the max-F1 threshold from validation does not transfer across infection cases. Report TPR at a fixed FPR alongside PR-AUC.

## Caveats
- Dedup drops conflicting vectors, which inflates scores at small N. A full-population version would add the "indistinguishable" share as automatically wrong. That share (bracketed counts) is the honest headline for N ≤ 5.
- MTA E3 at N = 3 without timing is infeasible: only 26 rows survive dedup.
- MCFP inherits its capture-level labels and its 40% no-ServerHello artefact (`SUMMARY_e5b.md`).
