# Batch 6 item 11: does multi-source training fix transfer? (leave-one-dataset-out, 8 Nov 2026)

`run_b6.py lodo`, launched in `launch_batch6e.sh` (A2, 8 Nov 14:54–15:09 WITA; exit 0). XGBoost, 5 seeds. CSVs are in `b6_lodo/`.

**Setup:**
- Each dataset is held out in turn. The model trains on the *other* datasets pooled, validates on a 15% stratified sample of the pool, and is tested on the full held-out dataset.
- **The pool is balanced per source:** up to 50k flows per class per source. MCFP and RAID are about 15× MTA and would otherwise dominate.
- Feature sets:
  - G1+G2 without timing, over MTA, MCFP, RAID and HIKARI (clean-label subset);
  - no G5 (G1–G4) and all (G1–G5), over MTA, MCFP and RAID only, because HIKARI has no TLS fields.
- **Origin probe:** an XGBoost classifier trained to tell which source a pool's *benign* flows come from (G1+G2 without timing, split grouped by capture/post/host).

## Results (mean over 5 seeds). Prevalence differs by row, so ROC is the comparable ranking column

Both validation-selected thresholds are reported:
- **strict:** validation FPR 10⁻³; TPR and test FPR at it;
- **max-F1:** malicious recall, benign recall and macro-F1 at it.

| Held-out dataset (prevalence) | Features | ROC, pooled | PR-AUC | **Strict: TPR / test FPR** | **Max-F1: recall mal / recall benign / macro-F1** | ROC, best single-source E4 |
|---|---|---|---|---|---|---|
| MTA (0.49) | G1+G2 no timing | **0.559** | 0.557 | 0.46 / **0.41** | 0.44 / 0.60 / 0.51 | 0.692 (RAID → MTA); 0.610 (MCFP → MTA) |
| MCFP (0.34) | G1+G2 no timing | 0.906 | 0.862 | 0.67 / 0.062 | 0.71 / 0.92 / 0.82 | 0.895 (MTA → MCFP) |
| RAID (0.37) | G1+G2 no timing | 0.538 | 0.403 | 0.00 / 0.000 | **0.00** / 1.00 / 0.39 | – |
| HIKARI ‡ (0.05) | G1+G2 no timing | **0.132** | 0.027 | 0.00 / 0.019 | 0.00 / 0.96 / 0.48 | – |
| MTA (0.73) | no G5 | 0.922 | 0.952 | 0.99 / **0.31** | 0.76 / 0.88 / 0.77 | 0.877 (MCFP → MTA, with timing) |
| MCFP (0.92) | no G5 | 0.991 | 0.999 | **0.87 / 0.011** | 0.89 / 0.99 / 0.78 | – |
| RAID (0.54) | no G5 | 1.000 | 1.000 | **0.64 / 0.000** | 0.81 / 1.00 / 0.89 | – |
| MTA (0.73) | all | 0.837 | 0.903 | 1.00 / **0.98** | 0.99 / 0.22 / 0.59 | 0.766 (MCFP → MTA, with timing) |
| MCFP (0.92) | all | 0.909 | 0.986 | 0.74 / 0.13 | 0.84 / 0.79 / 0.71 | 0.855 (MTA → MCFP) |
| RAID (0.54) | all | 0.931 | 0.931 | 0.68 / 0.084 | 0.88 / 0.72 / 0.80 | – |

(Macro-F1 on held-out MCFP is pulled down by its small benign class, 8% of flows, even where both recalls are high.)

‡ HIKARI: the held-out set holds HIKARI's two attacker IPs. Like E2/E3 it is a transfer test to two attacker hosts, not a generalisation estimate; its below-chance ROC repeats the CNN inversion in `SUMMARY_models.md`.

**Origin probe on the pools (balanced accuracy, chance in brackets):** 0.982–0.996 for the 3-source pools (0.33), and 0.977–1.000 for the 2-source pools (0.50).

## Findings
1. **Pooling sources does not fix transfer to MTA.**
   - With sizes and timing only, held-out MTA is at chance (ROC 0.56), *worse* than training on RAID or MCFP alone (0.69 / 0.61).
   - With handshake fields (no G5), pooling MCFP + RAID raises the ranking (ROC 0.92 vs 0.88 from MCFP alone), but the validated threshold still flags 31% of MTA benign flows.
   - With hashes (all), the threshold flags 98% of them.
2. **The environment shortcut is still fully available in every pool.** A probe tells the pooled sources apart from benign flows alone at 98–100% balanced accuracy. Pooling gives the model more environments to memorise, not fewer shortcuts. The source label is almost a function of the flow, so "benign vs malicious" can still be learned per source.
3. **Held-out MCFP and RAID keep an operating point with handshake fields, but both are separable by capture environment.**
   - Held-out MCFP with no G5: TPR 0.87 at a test FPR of 1.1% (11× the 10⁻³ target).
   - Held-out RAID with no G5: TPR 0.64 at FPR 0.
   - Both datasets are separable by how they were captured, which a model can exploit without having seen them:
     - In MCFP, flow statistics alone separate malware captures from CTU-Normal captures perfectly (G1 alone: PR-AUC 1.000, macro-F1 0.992, `SUMMARY_e5a.md`). That is a capture-level shortcut, and any environment-sensitive model may pick it up.
     - RAID's C2 is one Metasploit client–server pair (`SUMMARY_e5b.md`).
   - Without handshake fields, RAID is undetected (recall 0) and MCFP falls to a 6% FPR.
   - So these rows show separability of those two datasets, not transfer of malware knowledge.
4. **Suggested wording:** "Training on several sources at once does not remove the dataset shortcut: a probe identifies the pooled sources at ≥ 0.98 balanced accuracy. On held-out MTA, the only held-out set whose benign and malicious flows come from the same sandbox hosts, no feature set keeps a usable operating point (test FPR 0.31–0.98 at the validated threshold). Held-out MCFP and RAID do, but both are separable by capture environment (MCFP: flow statistics alone reach PR-AUC 1.000; RAID: one Metasploit pair)."

## Caveats
- One pooling scheme (equal per-source caps); other weightings or domain-adaptation methods were not tried.
- With HIKARI excluded from the TLS-feature rows, those pools have only two sources.
- Test FPR is at the threshold validated on the pooled sources, as in E4.
