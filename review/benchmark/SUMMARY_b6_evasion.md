# Batch 6 item 8: simple evasion sensitivity on MTA E3 (8 Nov 2026)

`run_b6.py evasion`, launched in `launch_batch6.sh` (A2, 8 Nov 14:24–14:28 WITA; exit 0). XGBoost, 5 seeds. CSVs are in `b6_evasion/`.

**Setup:**
- MTA E3 (≤2022 → 2023–26). Models are trained on clean data. Only the **malicious test flows** are perturbed; benign test flows are untouched.
- Feature sets: `all` (G1–G5), `loo_g5` (G1–G4), `g1g2` (sizes, directions, timing only: the ECH tier).

**Perturbations (rules recorded):**
- **Padding k ∈ {16, 64, 256} bytes** on every packet of a malicious flow:
  - G2 packet sizes get +k;
  - G1 byte counts get +k × packets per direction;
  - G1 min/mean/max packet sizes get +k (std unchanged).
  - This is uniform padding, an upper bound on what a C2 author could do cheaply; real padding would leave pure ACKs unchanged.
- **IAT jitter:** every timing feature of a malicious flow (G2 inter-arrival times, G1 IAT statistics and durations) is multiplied by one per-flow factor, drawn log-uniform from [0.5, 2].
- Handshake (G3), certificate (G4) and fingerprints (G5) are unchanged by both. Padding at the TLS record layer does not change the ClientHello.

## Results (mean over 5 seeds; SD ≤ 0.02)

| Attack on malicious test flows | PR-AUC, G1–G5 | PR-AUC, no G5 | PR-AUC, G1+G2 | Malicious recall @ val max-F1: G1–G5 / no G5 / G1+G2 |
|---|---|---|---|---|
| none | 0.901 | 0.982 | 0.912 | 0.59 / 0.59 / 0.72 |
| pad 16 B | 0.898 | 0.981 | 0.899 | 0.57 / 0.58 / 0.70 |
| pad 64 B | 0.896 | 0.981 | 0.845 | 0.56 / 0.57 / 0.51 |
| pad 256 B | 0.890 | 0.981 | **0.814** | 0.55 / 0.54 / **0.44** |
| IAT jitter ×0.5–2 | 0.901 | 0.982 | 0.918 | 0.59 / 0.61 / 0.74 |

Benign recall is unchanged by construction (0.97 / 0.99 / 0.91).

## Findings
1. **Size padding mainly hurts the size/timing-only model.**
   - G1+G2, the view left under ECH, loses 0.10 PR-AUC and 39% of its detections at 256-byte padding.
   - Models that also see handshake fields barely move: the no-G5 model loses 0.001, because G3/G4 are not affected by record padding.
2. **Timing jitter has no effect** on any model (±0.006). The models do not rely on precise inter-arrival times in this setting, consistent with the small timing contribution in E5a.
3. **Robustness and visibility pull in opposite directions.** The feature set most robust to padding (G1–G4) needs handshake visibility, which ECH removes; the ECH-tier model is the most padding-sensitive. A C2 author who pads records and uses ECH would defeat the size/timing view.

## Caveats
- A white-box-free, uniform perturbation; no adaptive attacker or optimisation.
- Applied to features, not to packets: real padding changes TLS record sizes, and packet sizes follow only roughly (segmentation).
- MTA E3 only, XGBoost only.
