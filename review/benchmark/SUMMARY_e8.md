# E8 visibility tiers (1 Nov 2026)

`run_benchmark.py --sets tier_tls12_full,tier_tls13,tier_tls13_ech` (XGBoost, 5 seeds, same protocol as E1–E3). CSVs are in `e8_mta/`, `e8_mcfp/` and `e8_raid/`.

**Tiers** simulate what a passive observer sees, by masking feature groups on every flow:
- `tier_tls12_full`: G1–G5 (statistics, packet sequence, handshake, certificate, fingerprints).
- `tier_tls13`: no certificate (G4), as in TLS 1.3, where it is encrypted.
- `tier_tls13_ech`: no handshake fields or fingerprints either (G1, G2 only: sizes, directions, timing), as with Encrypted Client Hello hiding SNI and the inner ClientHello extensions.

The masking is applied to all flows. The per-version breakdown is by the TLS version actually observed in the flow.

## Results (PR-AUC, mean over 5 seeds)

| Dataset | Exp | full | TLS 1.3 | TLS 1.3 + ECH |
|---|---|---|---|---|
| MTA | E2 post-grouped | 0.9958 | 0.9917 | **0.9995** |
| MTA | E3 temporal | 0.901 | 0.893 | **0.912** |
| MCFP | E2 capture-grouped | 0.9999 (test FPR 0.15) | 0.9998 (0.14) | **1.0000 (0.0004)** |
| RAID | E2 pcap-grouped | 1.000 | 1.000 | 1.000 |

Operating points (MTA E3): recall malicious 0.59 / 0.53 / 0.72 and recall background 0.97 / 0.98 / 0.91 for full / TLS 1.3 / ECH.

**Per observed TLS version, MTA E3 (PR-AUC; ≈ 9.2k TLS 1.2 and 3.5k TLS 1.3 test flows):**

| Observed version | full | TLS 1.3 | TLS 1.3 + ECH |
|---|---|---|---|
| TLS 1.2 flows | 0.898 | 0.888 | **0.984** |
| TLS 1.3 flows | **0.848** | **0.859** | 0.683 |
| no ServerHello (≈ 160) | 0.873 | 0.914 | 0.687 |

## Findings

1. **Losing TLS metadata does not hurt the headline numbers; it often helps.** On MTA and MCFP the G1/G2-only model matches or beats the full model in every setting. In MCFP E2 the full model misclassifies 15% of benign flows from unseen Normal captures, while the ECH-tier model misclassifies 0.04%. Certificate and fingerprint fields mostly add case- and era-specific shortcuts (`SUMMARY_e5b.md`).
2. **The exception is temporal drift on TLS 1.3 flows.** On 2023–26 TLS 1.3 traffic, the ECH tier drops to PR-AUC 0.68, against 0.85–0.86 when handshake fields are visible. Packet-size and timing patterns learned on ≤ 2022 traffic (84% TLS 1.2) transfer to new TLS 1.2 flows, but not to TLS 1.3 flows. There, the ClientHello and ServerHello fields that ECH would hide still carry signal.
3. **Removing the certificate (TLS 1.3 tier) costs almost nothing** (≤ 0.008 PR-AUC): the fingerprints and handshake fields cover what the certificate gave.
4. **RAID is uninformative:** every tier scores 1.000, consistent with the origin probe (RAID benign is 99.8–100% identifiable by environment).

## Caveats
- Tiers are simulated by masking features on the same flows. They are not captures of real TLS 1.3 or ECH sessions. Real ECH also changes record sizes (padding, GREASE), which this cannot model.
- `tier_tls13` keeps the JA3/JA4 client fingerprints. Under ECH the outer ClientHello is still visible but generic, which `tier_tls13_ech` approximates by dropping G3/G5 entirely.
- HIKARI has no TLS fields, so it is not in E8. MCFP E3 is infeasible (see `SUMMARY_mta_mcfp.md`).
