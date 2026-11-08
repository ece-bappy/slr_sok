# Batch 6 item 10: does padding defeat the ECH-tier detector, and does a padding-aware defender recover? (8 Nov 2026)

`run_b6.py padech`, launched in `launch_batch6d.sh` (A2, 8 Nov 14:39–14:40 WITA; exit 0). XGBoost, 5 seeds. CSVs are in `b6_padech/`.

**Setup:**
- Test set: the TLS 1.3 subset of the MTA E3 test set (3,466 flows, 56% malicious; 2,703 flows, 45% malicious without timing, because of per-set dedup).
- Models:
  - G1+G2 (the ECH tier), with and without timing;
  - trained on (i) all TLS versions or (ii) TLS 1.3 flows only (`SUMMARY_b6_tls13.md`).
- Training variants:
  - plain;
  - **padding-augmented, both classes**: every training flow padded by a random 0–256 B per data packet, so padding carries no class information. **This is the defender result.**
  - padding-augmented, malicious flows only: a contrast, which teaches "unusually large = malicious".
- Test: clean, or malicious test flows padded by 32 or 256 B per data packet. The padding rule is that of item 8 (data packets > 66 B only, capped at 1,514 B). Thresholds come from the clean validation set.

## Results (ROC-AUC mean over 5 seeds; PR-AUC in brackets; SD ≤ 0.08)

G1+G2 (with timing), TLS 1.3 test subset, prevalence 0.56:

| Training | Clean | Pad 32 B | **Pad 256 B** |
|---|---|---|---|
| All versions, plain | 0.537 (0.683) | 0.533 | 0.537 |
| All versions, augmented both classes | 0.633 (0.740) | 0.623 | 0.567 (0.704) |
| All versions, augmented malicious only (contrast) | 0.708 | 0.688 | 0.943 |
| **TLS 1.3 only, plain** | **0.892 (0.911)** | 0.886 | **0.592 (0.598)** |
| **TLS 1.3 only, augmented both classes** | **0.903 (0.916)** | 0.895 | **0.576 (0.679)** |
| TLS 1.3 only, augmented malicious only (contrast) | 0.796 | 0.827 | 0.866 |

G1+G2 without timing (prevalence 0.45), TLS 1.3 only:

| Training | Clean | Pad 32 B | Pad 256 B |
|---|---|---|---|
| Plain | 0.798 | 0.743 | 0.559 |
| Augmented both classes | 0.792 | 0.733 | 0.441 |

## Findings
1. **Padding defeats the ECH-tier detector.** The best ECH-tier model, trained on TLS 1.3 flows, drops from ROC 0.89 to **0.59** when malicious flows pad each data packet by 256 B (without timing: 0.80 → 0.56). 32-B padding, the ECH ClientHello quantum, costs ≤ 0.06.
2. **A defender who anticipates padding does not recover.** With symmetric augmentation (both classes padded during training), the model stays at ROC 0.58 under 256-B padding (no timing: 0.44), while keeping its clean accuracy (0.90). Training with padding makes the model *ignore* sizes rather than see through the padding. Size patterns are what padding removes.
3. **The malicious-only augmentation "recovers" (0.87–0.94) only through a shortcut.** It learns that unusually large flows are malicious. An attacker who pads towards benign sizes would defeat it. It is reported as a contrast, not a defence.
4. Together with item 9: under ECH, a detector needs (i) TLS 1.3 training data to work at all and (ii) gives way to cheap record padding. Under ECH plus padding, the remaining signal is weak (ROC ≈ 0.6).

## Caveats
- The attacker pads every data packet by a fixed amount; no adaptive attack. Padding to benign-like sizes would likely be stronger.
- The defender's augmentation distribution (uniform 0–256 B) is one choice; other schemes (per-record random padding, learning on padding-invariant features) were not tried.
- XGBoost only; MTA E3 only; feature-level simulation as in items 5 and 8.
