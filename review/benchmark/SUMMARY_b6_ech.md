# Batch 6 item 5: ECH-padded visibility tier (8 Nov 2026)

`run_b6.py ech`, launched in `launch_batch6.sh` (A2, 8 Nov 14:18–14:20 WITA; exit 0). XGBoost, MTA E3 (≤2022 → 2023–26), 5 seeds. CSVs are in `b6_ech/`.

**Why:** E8's ECH tier masks fields but keeps the real ClientHello size. ECH clients pad the encrypted inner ClientHello, so its size is quantised.

**Padding rule used** (after draft-ietf-tls-esni §6.1.3, which pads EncodedClientHelloInner to a multiple of 32 bytes after padding the server name):
- The size of the packet that completes the ClientHello (G2 position `k_pkt_ch`) is rounded **up to the next multiple of 32 bytes**.
- A stronger variant rounds to a multiple of 256.
- Other packets are unchanged.

**Feature sets:**
- The flow statistics in G1 include byte totals and min/mean/max packet sizes, which would still reveal the original ClientHello size and cannot be recomputed from 20 packets. So the padded variants **drop G1's size-derived columns** (`*_bytes`, `*_ps`).
- An unpadded control without them isolates the padding effect.
- Variants:
  - E8's tier (G1 + G2, unpadded);
  - G1 without size columns + G2, unpadded;
  - the same, padded to 32;
  - the same, padded to 256.

## Results (PR-AUC mean ± SD over 5 seeds; ROC in brackets)

| Variant | All test flows | TLS 1.2 flows (9,197; 44% malicious) | **TLS 1.3 flows** (3,466; 56% malicious) |
|---|---|---|---|
| ECH tier as in E8 (G1 + G2) | 0.912 ± 0.005 (0.90) | 0.984 (0.99) | 0.683 ± 0.009 (0.54) |
| G1 without sizes + G2, unpadded (control) | 0.903 ± 0.007 (0.89) | 0.982 (0.98) | 0.656 ± 0.015 (0.51) |
| … ClientHello padded to 32 B | 0.909 ± 0.007 (0.90) | 0.980 (0.98) | 0.681 ± 0.014 (0.55) |
| … ClientHello padded to 256 B | 0.907 ± 0.011 (0.90) | 0.972 (0.98) | 0.717 ± 0.015 (0.60) |

## Findings
1. **ECH-style ClientHello padding does not change the ECH-tier conclusion.** Overall PR-AUC moves by ≤ 0.006 between the unpadded control and either padding level. The TLS 1.2 flows stay at 0.97–0.98.
2. **The TLS 1.3 weakness of the size/timing view is not about the ClientHello size.** On TLS 1.3 flows, every variant sits at PR-AUC 0.66–0.72 with ROC 0.51–0.60, near chance against a 0.56 prevalence. Padding even improves it slightly (+0.03 at 256 B), probably because quantisation removes a drifting detail. What separates classes on TLS 1.2 flows is later packets (the response pattern), and that does not carry over to 2023–26 TLS 1.3 traffic.
3. **E8's caveat is answered:** modelling ECH padding does not make the ECH tier look worse. RESULTS.md can keep the E8 numbers and cite this as a check.

## Caveats
- Simulated on the same flows, as E8. The padding acts on one packet's size only; real ECH also changes the outer ClientHello's extension set (removed in this tier anyway) and may add GREASE ECH to non-ECH clients.
- Dropping G1's size columns is conservative: a real deployment could compute flow sizes exactly, with the padded ClientHello inside them.
- The TLS 1.3 subset is evaluated with the threshold of the full validation set, as in E8.
