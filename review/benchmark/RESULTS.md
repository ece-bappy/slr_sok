# Benchmark results by research question (consolidated, 2 Nov 2026)

One table per RQ (plan.md §2), giving the headline number, its 95% CI, the setting and the caveat that must travel with it. Details, per-seed CSVs and the full caveat lists are in the linked summaries; figures are in `figures/` (regenerate with `python review/benchmark/figures/make_figures.py`).

**Common protocol (unless stated):**
- Model: XGBoost with fixed hyperparameters, 5 seeds.
- Leakage controls: per-feature-set dedup (vectors present in both classes and within-class duplicates are removed); training balanced 1:1.
- Thresholds: chosen on validation only (max-F1; FPR 10⁻³).
- CIs: 95% test-set bootstrap, shown as the mean of the per-seed CI bounds. ± is the SD over seeds.
- Metric: PR-AUC unless a column says otherwise.
- Feature groups: G1 flow statistics, G2 first-20-packet sequence, G3 handshake, G4 certificate, G5 JA3/JA4 fingerprints. "No timing" drops inter-arrival and duration features.

## RQ1: How much does performance drop beyond random splits? (E1–E4)

Figure: `figures/fig_a_collapse.pdf`. Summaries: `SUMMARY.md`, `SUMMARY_mta_mcfp.md`, `SUMMARY_e4.md`, `SUMMARY_models.md`.

| Setting | PR-AUC [95% CI] | Macro-F1 [CI] | Caveat |
|---|---|---|---|
| MTA, all features, E1 random | 1.000 [1.000–1.000] | 0.993 [0.991–0.995] | Same infection cases in train and test |
| MTA, all, **E2 post-grouped** | 0.996 [0.995–0.996] | 0.910 [0.905–0.915] | Background is same-pcap popular-domain traffic, not enterprise traffic |
| MTA, all, **E3 ≤2022 → 2023–26** | **0.901** [0.896–0.906] | 0.777 [0.769–0.784] | Test FPR 0.012 at the val-10⁻³ threshold (12× the target) |
| MTA, G1+G2 no timing, E3 | 0.859 [0.850–0.866] | 0.791 [0.783–0.799] | |
| MCFP, all, E2 capture-grouped | 1.000 [1.000–1.000] | 0.954 [0.952–0.956] | **15% benign FPR** on unseen Normal captures; capture-level shortcut (RQ2) |
| RAID, G1+G2 no timing, E2 | 1.000 [1.000–1.000] | 0.999 | **Uninformative:** one C2 client–server pair; origin probe separates RAID benign from all others |
| HIKARI, G1+G2 no timing, E1 | 1.000 [1.000–1.000] | 0.995 | Clean-label subset only |
| HIKARI, E2 ‡ | 0.236 [0.205–0.272] | 0.509 [0.502–0.517] | ‡ **2-attacker transfer test, not a grouped-generalisation estimate**: trains on one attacker IP and tests on the other; the CNN inverts (`SUMMARY_models.md`) |
| HIKARI, E3 ‡ | 0.902 [0.894–0.909] | 0.773 [0.764–0.781] | ‡ Same two attackers in reverse; 210 training attack flows |
| **E4 MCFP → MTA**, G1+G2 no timing | **0.585** [0.577–0.593] | 0.572 [0.567–0.578] | Test prevalence 49%; test FPR 0.34 at the val-10⁻³ threshold |
| E4 MCFP → MTA, all | 0.844 [0.840–0.849] | 0.448 [0.445–0.450] | Ranks, but the source threshold flags 98% of MTA background |
| E4 MTA → MCFP, G1+G2 no timing | 0.849 [0.846–0.853] | 0.821 [0.819–0.823] | Test prevalence 34% |
| E4 RAID → MTA, G1+G2 no timing | 0.637 [0.628–0.645] | 0.337 [0.334–0.339] | Malicious recall 0.000 at the max-F1 threshold |
| Other families (LightGBM, RF, LR, 1D-CNN, BiLSTM) | same pattern | | E4 conclusions hold across every family. BiLSTM ≈ CNN within-dataset; ROC 0.69 vs 0.53 on MCFP → MTA without timing, still far below the control's 0.96 (`SUMMARY_models.md`) |
| Optuna tuning, all six families (40 trials, source validation only) | within ±0.10; 10 of 42 settings worse after tuning | | Tuned MCFP → MTA stays at 0.51–0.63 (prevalence 0.46–0.49) in every family; no conclusion changes (`SUMMARY_tuning.md`) |
| **Published baseline, RAID 2024** C-Cert / C-Behav RF, reproduced from the authors' code | RAID E2 0.999 / 1.000; MTA E3 0.880 [0.872–0.887] / 0.890 [0.883–0.896] | MTA E3 0.773 / 0.792 | Code reproduces the paper's tables exactly (C-Basic, C-Cert) or within 1 pp (C-Behav). Under drift both trail XGB on the same rows (0.941 / 0.903). C-Cert covers only 45% of MTA flows (28% of malicious) (`SUMMARY_r24.md`) |
| RAID 2024 baselines, E4 MCFP → MTA | C-Cert RF 0.820, C-Behav RF 0.863 | **C-Cert 0.789** vs XGB same rows 0.333 | The low-capacity C-Cert keeps its operating point (TNR 0.99, TPR 0.48), but only on the flows it covers. C-Behav does not transfer (TPR 0.16) |
| Unsupervised (Isolation Forest, autoencoder; benign-only training) | MTA E2 AE ROC 0.88; E3 0.78; MCFP → MTA ≈ 0.5–0.6 | | At a 1% benign-validation FPR threshold they catch only 0.3–21% of malicious flows; on MTA E3 that threshold gives a 13.6% test FPR (`SUMMARY_unsup.md`) |

**Answer:**
- In-dataset grouped splits remain near-perfect.
- Temporal drift costs about 0.1 PR-AUC on MTA.
- Cross-dataset transfer loses 0.15–0.4 PR-AUC, and no source-validated operating point survives it.
- This holds for six model families with or without tuning, for the published RAID 2024 classifiers, and for unsupervised anomaly detectors. The one partial exception is the single-feature C-Cert, which keeps a usable operating point across datasets on the minority of flows where it applies.

## RQ2: Which feature groups carry the signal; how much is shortcut or circularity? (E5a, E5b)

Figure: `figures/fig_e_origin_probe.pdf` (and `fig_c` for G5). Summaries: `SUMMARY_e5a.md`, `SUMMARY_e5b.md`.

| Setting | Result [95% CI] | Caveat |
|---|---|---|
| Origin probe: benign flows only, G1+G2 no timing, grouped, 4 sources | Balanced accuracy **0.989** ± 0.001 (chance 0.25) | Benign traffic alone identifies the dataset. Any cross-dataset mix of benign and malicious sources is confounded |
| SSLBL labels on MTA (label = cert/JA3 blocklist hit), all, E2 / E3 | 1.000 / **0.684** [0.643–0.719] | Circular: G4+G5 carry 99% of the gain. With IOC labels, E3 is 0.901 |
| MCFP, no ServerHello | 40% of malicious vs 0.9% of benign flows | A handshake-failure shortcut in the CTU captures |
| E5a MTA E3, without G5 (G1–G4) | **0.982** [0.980–0.985] (all groups: 0.899–0.901) | Leave-one-out; the other 4 groups each move PR-AUC by ≤ 0.013 |
| E5a MTA E3, G4 certificate alone (8 features) | 0.903 [0.871–0.931], macro-F1 0.837 | Absent under TLS 1.3 |
| E5a MCFP E2, G1 alone | 1.000, macro-F1 0.992, test FPR 0.0006 | Capture shortcut; adding TLS groups raises FPR to 0.14–0.20 |
| E5a MCFP → MTA, without G5, no timing | 0.808 [0.801–0.815] (other leave-one-out sets 0.57–0.76) | Most sets keep no usable threshold (FPR ≈ 0.97) |
| Cross-family check: MTA E3 without G5 vs all | XGB +0.081, LightGBM +0.023, RF +0.029 (CIs disjoint); LR 0.000 | Temporal penalty for every tree family; LR sees only the top-30 values (`SUMMARY_crossfamily.md`) |
| Cross-family check: MCFP → MTA without G5 vs all | XGB +0.087, LightGBM +0.014, RF −0.009, LR −0.003 (with timing) | Model-dependent; transfer fails with or without fingerprints |

**Answer:**
- The signal is redundant across G1–G4.
- The fingerprints (G5) add case- and era-specific shortcuts.
- MCFP and RAID are separable by capture environment.
- Blocklist-derived labels make certificate and fingerprint features circular.

## RQ3: How early can a flow be classified? (E6)

Figure: `figures/fig_d_early.pdf`. Summary: `SUMMARY_e6.md`.

| Setting | PR-AUC [95% CI] | Caveat |
|---|---|---|
| MTA E3, first 20 packets (visibility-tagged) | 0.901 [0.896–0.906] | Equal to the whole flow (0.901) |
| MTA E3, first 10 packets | 0.896 [0.891–0.901]; macro-F1 0.799 | |
| MTA E3, first 5 packets | 0.860 [0.852–0.868] | Background recall drops to 0.69 |
| MCFP E2, first 10 packets | 1.000 [1.000–1.000] | Capture shortcut, as in RQ2 |
| N = 3 | not reported as a result | Artefact: only the TCP handshake is visible, so dedup removes 87–99.8% of flows and the residue is separated by round-trip time (`SUMMARY_e6.md`) |

**Answer:**
- About 10 packets (through the ServerHello) are enough to match whole-flow accuracy.
- The jump from N = 3 to N = 5 is the ClientHello fingerprint, not behaviour.
- Without timing, early features drift worse: MTA E3 at N = 5 scores 0.37.

## RQ4: What does detection cost end to end? (E7)

Summary: `SUMMARY_e7.md`. Hardware: Xeon Silver 4410T and NVIDIA A2. "Edge" = the same box pinned to 1–2 cores with `taskset`, a **proxy, not a real device**.

| Setting | Result | Caveat |
|---|---|---|
| Feature extraction, full pipeline (Zeek + tlsfp + NFStream), 1–2 cores | **1.7–2.7 ms per TCP flow**; 350–590 flows/s per core; peak RSS ≤ 293 MB | Offline from pcap; Zeek is restarted per pcap; warm or cold page cache varies between runs |
| **Zeek-free pipeline** (NFStream + tlsfp, G1–G3) | **0.9–1.2 ms per TCP flow**; about 1,000 flows/s per core; RSS ≤ 264 MB | Same 30 pcaps, warm cache; full pipeline re-timed alongside at 1.7–2.2 ms |
| Zeek-free features, accuracy | MTA E3 0.971 [0.969–0.974] (XGB; full `all` 0.901); MCFP → MTA 0.925 with timing / 0.776 without | Better than the full set because it also drops fingerprints. No cross-dataset operating point (FPR 0.27–0.61) |
| Inference, batches of 1,024, any model | ≤ 0.06 ms per flow (XGBoost 106–123k flows/s on 1–16 threads) | |
| Inference, batch=1 | CNN 0.05 ms, LightGBM 2.9 ms, XGBoost 6.3 ms, RF 13.6 ms, LR 40 ms | Mostly Python/pandas wrapper overhead |
| GPU (A2) | No gain for XGBoost; CNN 1.6–2× when batched | |
| Model size and memory | 33 KB (LR) to 9.6 MB (RF); RSS 230–390 MB for trees, about 900 MB for the CNN (PyTorch) | |

**Answer:**
- Extraction, not the model, is the cost.
- A 1–2-core box handles a few hundred new TLS flows per second through the full pipeline, or about 1,000 through the Zeek-free one.
- The Zeek-free feature set is also the more accurate one under drift.

## RQ5: Visibility tiers and fingerprint drift (E8, E9)

Figures: `figures/fig_b_tiers.pdf`, `figures/fig_c_fingerprints.pdf`. Summaries: `SUMMARY_e8.md`, `SUMMARY_e9.md`.

| Setting | PR-AUC [95% CI] | Caveat |
|---|---|---|
| MTA E3, full (TLS 1.2 view) / TLS 1.3 tier / TLS 1.3 + ECH tier | 0.901 / 0.893 [0.887–0.899] / **0.912** [0.907–0.917] | Tiers are simulated by masking features on the same flows. Real ECH padding is not modelled |
| MTA E3, **TLS 1.3 flows only**: full / TLS 1.3 / ECH | 0.848 / 0.859 / **0.683** | The one place where the ECH tier loses (about 3.5k test flows) |
| MCFP E2, ECH tier | 1.000; test FPR 0.0004 (full: 0.15) | Capture shortcut |
| E9 MTA ≤2022 → 2023–26: no fingerprints / +JA3 / +JA4 / +both | **0.982** [0.980–0.985] / 0.894 / 0.895 / 0.901 | JA4 is no more robust than JA3 |
| E9 MCFP → MTA 2023–26: no fingerprints / +any fingerprint | 0.794 [0.781–0.806] / 0.67–0.72 | With fingerprints, the source threshold flags 100% of test flows |
| Test flows whose JA3 / JA4 was never seen in training (MTA ≤2022) | 53% / 52% (1,230 of 1,245 distinct JA3) | Background JA3/JA4 mix follows the sandbox hosts |
| Fingerprint-only models, later period | JA3 0.28, JA4 0.50 (at or below prevalence) | Evaluated on deduplicated distinct values (n = 45–1,418) |
| Cross-family E9, MTA ≤2022 → 2023–26: no fp vs +both | XGB 0.982 vs 0.901; LightGBM 0.983 vs 0.954; RF 0.973 vs 0.948; LR 0.932 vs 0.932 | Holds for every tree family; neutral for LR (`SUMMARY_crossfamily.md`, `fig_c` bottom row) |
| Cross-family E9, MCFP → MTA 2023–26 | XGB 0.794 vs 0.665; LightGBM 0.699 vs 0.677; RF 0.831 vs 0.853; LR 0.538 vs 0.535 | Not universal: RF ranks slightly better with fingerprints, but has a worse macro-F1 |

**Answer:**
- Losing the certificate costs ≤ 0.008.
- The size and timing view (ECH tier) matches the full view except on newer TLS 1.3 flows.
- JA3 and JA4 both drift: about half of later-period flows carry an unseen hash.
- Adding either fingerprint lowers temporal-drift accuracy for every tree family and is neutral for LR.
- Across datasets the effect depends on the model.
