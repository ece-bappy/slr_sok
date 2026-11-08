# Batch 6 item 4: what is it about fingerprints? (8 Nov 2026)

`run_b6.py encoding`, launched in `launch_batch6.sh` (A2, 8 Nov 13:45–14:18 WITA; exit 0). XGBoost, **20 seeds**. CSVs are in `b6_encoding/`.

**Question:** is the G5 penalty about *hashing* (memorising exact hash values) or about the *handshake content* the hashes summarise?

**Setup:**
- Every encoding is trained and tested on the same rows: the deduplicated G1–G5 table, with the raw ClientHello/ServerHello lists joined from `flows.parquet` (100% coverage).
- Settings:
  - MTA E3: ≤2022 → 2023–26, with timing.
  - E4 MCFP → MTA: no timing.
- Encodings (G1–G4 always included):
  - (a) the four hashes (JA3, JA3S, JA4, JA4S) as categorical features, as everywhere else;
  - (b) each hash replaced by its frequency in the training rows (unseen = 0);
  - (c) each hash replaced by a binary "seen in training" flag;
  - (d) no hash: multi-hot of the 64 most frequent training values of the cipher-suite, extension, supported-group, signature-algorithm, EC-point-format and ServerHello-extension lists, plus their lengths;
  - (e) no fingerprint information beyond G1–G4.

## Results (PR-AUC mean ± SD over 20 seeds [mean 95% CI]; Wilcoxon signed-rank over seeds against (a) and against (e))

| Encoding | MTA E3 PR-AUC | ROC | macro-F1 | test FPR @ val 10⁻³ | E4 MCFP → MTA PR-AUC | ROC | macro-F1 | test FPR @ val 10⁻³ |
|---|---|---|---|---|---|---|---|---|
| (a) hash categorical | 0.901 ± 0.004 [0.895–0.906] | 0.875 | 0.765 | 0.011 | 0.741 ± 0.056 [0.733–0.749] | 0.806 | 0.355 | **0.977** |
| (b) training frequency | 0.964 ± 0.006 (vs a p < 10⁻⁵) | 0.968 | 0.778 | 0.009 | 0.698 ± 0.030 (vs a: −0.044, p = 0.008) | 0.717 | 0.512 | 0.762 |
| (c) seen-in-training flag | **0.983** ± 0.002 (vs a p < 10⁻⁵; vs e p = 0.93) | 0.985 | 0.811 | 0.002 | **0.802** ± 0.019 (vs e p = 0.16) | 0.850 | 0.683 | 0.534 |
| (d) decomposed lists, no hash | 0.982 ± 0.002 (vs a p < 10⁻⁵) | 0.984 | 0.809 | 0.002 | 0.762 ± 0.019 (vs a p = 0.12) | 0.794 | 0.675 | 0.531 |
| (e) none (G1–G4) | **0.983** ± 0.002 [0.981–0.985] | 0.985 | 0.811 | 0.002 | **0.808** ± 0.020 [0.801–0.815] | 0.854 | 0.684 | 0.537 |

## Findings

1. **The penalty comes from the raw hash as a categorical feature.** Encodings that keep the handshake *content* but drop the hash identity give the same result as no fingerprints on MTA E3:
   - (d) decomposed lists: 0.982;
   - (c) the seen flag: 0.983;
   - (e) none: 0.983 (identical to (c): p = 0.93).
   Only the hash-as-category encoding (a) loses 0.08 PR-AUC and has a 5× higher test FPR.
2. **Novelty is not a signal.** If "this hash was never seen" indicated malware, the flag (c) would beat (e); it does not, on either setting. In the 2026 breakdown (`SUMMARY_b6_rolling.md`), unseen hashes are just as common among benign flows (79%) as among malicious ones (91%).
3. **The handshake content adds nothing beyond G1–G4 under drift.** The decomposed cipher/extension/group lists (d) match (e) on MTA E3 and trail it across datasets (0.762 vs 0.808). G3 already carries the counts and extension flags.
4. **Frequency encoding helps within MTA (0.964) but hurts across datasets (0.698, below the hash itself).** A hash's training frequency is a property of the training capture environment, a shortcut of its own.
5. **Suggested wording for the paper:** "Raw JA3/JA4 hashes used as categorical features age badly; neither hash novelty nor the decomposed handshake lists carry signal beyond the other flow and handshake features." This replaces the broader "fingerprints hurt".

## Caveats
- One model family (XGBoost). The cross-family check of the plain G5 contrast is in `SUMMARY_crossfamily.md`; the rolling-origin version of (b)/(c) is item 3c (`b6_rolling_enc/`).
- On E4 every MTA client hash is unseen in MCFP, so (c) is a constant there and must equal (e) up to noise. MTA E3 is the informative test of (c).
- The rows are deduplicated once on the G1–G5 vector, so all encodings see identical data. This differs from the per-set dedup of `SUMMARY_e9.md`, which explains small differences from E9's numbers.
