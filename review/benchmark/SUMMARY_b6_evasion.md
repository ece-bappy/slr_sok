# Batch 6 item 8: simple evasion sensitivity on MTA E3 (8 Nov 2026, corrected rerun)

`run_b6.py evasion`, rerun as step `b6_evasion_v2` in `launch_batch6d.sh` (A2, 8 Nov 14:40–14:44 WITA; exit 0). XGBoost, 5 seeds. CSVs are in `b6_evasion/`.

> **Correction.** The first run (8 Nov 14:24, commit be3c98d) padded every packet, including pure ACKs, which overstated the attack. The numbers below use the corrected rule and replace it.

**Setup:**
- MTA E3 (≤2022 → 2023–26). Models are trained on clean data; only the **malicious test flows** are perturbed.
- Feature sets: `all` (G1–G5), `loo_g5` (G1–G4), `g1g2` (sizes, directions, timing: the ECH tier).

**Perturbation rules (recorded):**
- **Record padding of k ∈ {16, 64, 256} bytes:**
  - Only data-carrying packets grow: G2 frame size > 66 B (54/60/66-B frames are pure ACKs, 55% of G2 packets), capped at a full 1,514-B frame.
  - G1 byte counts grow by k per PSH packet (≈ data segments) per direction.
  - G1 max size grows by k (capped); mean size is recomputed; min size (an ACK) is unchanged.
  - Padding is rounded to whole bytes. This is uniform per data packet, an upper bound on cheap padding.
- **IAT jitter:** every timing feature of a malicious flow (G2 inter-arrival times, G1 IAT statistics and durations) is multiplied by one per-flow factor, log-uniform in [0.5, 2].
- G3, G4 and G5 are unchanged by both. Record padding does not alter the ClientHello.

## Results (mean over 5 seeds; SD ≤ 0.02)

| Attack on malicious test flows | PR-AUC, G1–G5 | PR-AUC, no G5 | PR-AUC, G1+G2 | Malicious recall @ val max-F1: G1–G5 / no G5 / G1+G2 |
|---|---|---|---|---|
| none | 0.901 | 0.982 | 0.912 | 0.59 / 0.59 / 0.72 |
| pad 16 B | 0.900 | 0.982 | 0.904 | 0.58 / 0.59 / 0.70 |
| pad 64 B | 0.900 | 0.982 | 0.854 | 0.58 / 0.59 / 0.54 |
| pad 256 B | 0.897 | 0.981 | **0.838** | 0.57 / 0.55 / **0.51** |
| IAT jitter ×0.5–2 | 0.901 | 0.982 | 0.918 | 0.59 / 0.61 / 0.74 |

Benign recall is unchanged by construction (0.97 / 0.99 / 0.91).

## Findings
1. **Size padding mainly hurts the size/timing-only model.** G1+G2, the view left under ECH, loses 0.07 PR-AUC and 29% of its detections at 256-B padding. With handshake fields the model barely moves (no G5: −0.001), because G3/G4 are unaffected by record padding.
2. **Timing jitter has no effect** on any model (±0.006).
3. **Robustness and visibility pull in opposite directions.** The padding-robust feature set needs handshake visibility, which ECH removes. Item 10 (`SUMMARY_b6_padech.md`) tests padding against the ECH tier directly, including a defender who trains with padding.

## Caveats
- A fixed, uniform perturbation; no adaptive attacker or optimisation against the model.
- Applied to features, not packets: real padding changes TLS record sizes, and packet sizes follow only roughly (segmentation, MTU).
- MTA E3 only, XGBoost only.
