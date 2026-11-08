# Manuscript outline (v1, 8 Nov 2026)

**Format assumed:** SoK track at a CORE A venue (ACSAC / RAID / EuroS&P / AsiaCCS style): about 13 pages of body text in two columns, plus references and appendices. A Q1 journal version (TIFS / TDSC / Computers & Security) would move the appendices into the body. Page budgets below are for the conference version.

**Sources of every number:**
- `review/benchmark/RESULTS.md` (benchmark) and the `SUMMARY_*.md` files it links.
- `review/synthesis/SUMMARY.md` (67-paper core set).
- `review/coding/kappa_report.md`, `review/coding/validation_report.md`, `review/final_screening/SPOT_CHECK.md`.
- `plan.md` §1.1 (prior work) and §4 (protocol).

Never type a number into the draft without its source file.

---

## Title (pick one)

1. *SoK: Do Malicious TLS Traffic Classifiers Survive Deployment?* (the plan's working title, shortened)
2. *SoK: Malicious TLS Detection Under Drift, Dataset Shift and Shrinking Visibility*
3. *SoK: What Ninety-Nine Percent Hides: Evaluating ML Detection of Malicious TLS Traffic*

## Abstract (about 200 words)

1. **Problem:** the literature reports 95–99.9% accuracy, but under protocols a deployed detector never sees.
2. **What we did:** systematized 291 eligible studies (2019–2026), human-coded a 67-paper core set, and ran a controlled benchmark on four public sources plus a reproduction of RAID 2024.
3. **Three or four headline findings, with numbers:**
   - In the core set, about 71% of main results use a random or stratified random split; only 4% are temporal and 22% report an FPR or PR-AUC.
   - Temporal and cross-dataset drops; no source-validated threshold survives a dataset change.
   - Raw JA3/JA4 hashes as features age badly (0.901 vs 0.983 without them, 20 seeds).
   - Under ECH, size/timing models trained on TLS 1.2 malware fail on TLS 1.3 malware (ROC 0.54), and 256-byte padding defeats them even with TLS 1.3 training.
4. **Recommendations and artefact release.**

---

## 1. Introduction (about 1.25 pages)

- **The gap:** high reported accuracy, against what deployment needs: a new network, a later time, a real-time decision, and less visibility under TLS 1.3/ECH.
- **Why now:** TLS 1.3 is the majority, ECH is being rolled out, and fingerprinting moved from JA3 to JA4. The field is growing fast: 35 of the 67 core papers are from 2025–26.
- **RQ1–RQ5:** one line each (plan.md §2).
- **Contributions:**
  1. Systematization: a PRISMA review, a taxonomy along the visibility and evaluation axes, and gap statistics from human-verified coding (κ reported).
  2. A unified, visibility-tagged feature pipeline from raw pcaps (G1–G5, plus a Zeek-free variant).
  3. A controlled benchmark answering RQ1–RQ5:
     - an origin probe;
     - a label-circularity audit;
     - rolling-origin drift;
     - an ECH padding analysis;
     - end-to-end cost.
  4. An independent reproduction of the RAID 2024 classifiers, including the authors' released UCNet table.
  5. Deployment recommendations and an evaluation checklist.
- **Teaser:** one box or figure with the 3–4 headline numbers. Candidate: a reduced `fig_a_collapse`.

## 2. Background and threat model (about 1 page)

- **2.1 What a passive observer sees:**
  - TLS 1.2: certificate in clear.
  - TLS 1.3: certificate encrypted, ClientHello visible.
  - TLS 1.3 + ECH: outer ClientHello only.
  - **Table 1:** feature groups G1–G5 × visibility tier (plan.md §5.2 table).
- **2.2 Fingerprinting:** JA3/JA3S, JA4/JA4S; extension randomization in Chrome.
- **2.3 Threat and deployment model:**
  - The defender is a passive edge monitor with no decryption and a real-time budget.
  - The attacker is a non-adaptive malware operator, with simple padding and jitter as the evasion bound.
  - Base rates are at or below 1% malicious.
- **2.4 Evaluation terms used throughout:**
  - random / grouped / temporal / cross-dataset splits;
  - operating point = a threshold chosen on validation only;
  - PR-AUC vs ROC under prevalence.

## 3. Systematization of the literature (about 2.5 pages)

- **3.1 Method:**
  - search string, databases and dates;
  - LLM pre-screening as suggestion only, with a human deciding (spot-check: 0/120 wrong exclusions, 95% upper bound about 2.5%);
  - the low_venue rule;
  - the core-set rule (CORE A*/A, Scimago Q1 CS, top-10% cited);
  - extraction: a two-model ensemble with human verification of every core paper (validation: agreed answers 42/44 correct; free text 13/20 and 15/20 correct; 0 invented);
  - second coder on 14 papers: single-choice agreement 82%, median κ 0.56; list fields pooled κ 0.77;
  - **Figure 1:** PRISMA flow. **TODO:** regenerate the final counts; the plan.md table predates the strict pass and the spot-check.
- **3.2 Taxonomy (Table 2):** papers by task (C2/botnet, DoH tunnelling, web attacks, generic malware) × feature visibility tier × evaluation protocol. Columns as in the synthesis tables.
- **3.3 Gap statistics (Table 3 or a compact figure), each feeding an RQ:**
  - **Evaluation protocol (RQ1):**
    - main split random or stratified 71%;
    - temporal 4%, host-grouped 6%, cross-dataset 4% of main results;
    - easy-vs-hard reported in 16%.
  - **Metrics:** FPR or PR-AUC in 22%; accuracy only in 4%.
  - **Labels (RQ2):** dataset_provided 81%, generated 31%, label–feature overlap in 2 papers.
  - **Shortcut checks:** none 34%; most "checks" are ablations, and no paper runs an origin probe (shortcut_check = probe in 0 papers, from SUMMARY.md).
  - **Visibility (RQ5):**
    - 67% of core papers use only ECH-surviving features (G1/G2);
    - 81% don't state the TLS version;
    - only 2 papers consider ECH;
    - fingerprints are used in 6 papers or fewer.
  - **Early detection (RQ3):** 60% classify the whole flow.
  - **Cost (RQ4):** 45% report no cost; 21% report end-to-end cost.
  - **Reproducibility:**
    - code released 24%, data released 16%;
    - only 63% use any openly downloadable dataset, because CIC/UNB data is registration-gated;
    - 18% use only private captures.
- **3.4 Datasets the field relies on (Table 4):**
  - Most-used datasets: CIC-IDS2017 (14), DoHBrw (13), ISCX VPN (13), USTC-TFC (11), MCFP (9).
  - Known quality issues per dataset, for example CIC-IDS2017 labelling errors (Engelen et al.).
  - Our HIKARI finding: benign traffic is header-only, and the label tables mismatch the pcaps.
- **3.5 Takeaways:** 4–5 bullets that motivate Section 4.

## 4. Benchmark methodology (about 1.75 pages)

- **4.1 Datasets (Table 5):**
  - MTA 2019–2026, labelled from IOC/sandbox metadata and not from certificates or JA3;
  - Stratosphere MCFP;
  - RAID 2024 (Tranco benign, Metasploit C2);
  - HIKARI (clean-label subset only, ‡ 2-attacker caveat);
  - DoHBrw: **pending the download**. Drop it, or add it as a fifth source, before submission.
  - Per dataset: flows, dedup counts, TLS versions, class balance, capture environment. Source: the dataset audit tables.
- **4.2 Pipeline:**
  - Zeek + tlsfp + NFStream;
  - visibility tags (packet index, tier);
  - JA3/JA4 checked against Wireshark (15/15);
  - join rate 99.98%;
  - Zeek-free variant.
- **4.3 Splits E1–E4 and the other experiments (Table 6, compact experiment matrix):**
  - E1–E4 splits;
  - rolling origin;
  - leave-one-family-out and leave-one-dataset-out;
  - origin probe;
  - SSLBL vs IOC labels;
  - early N;
  - visibility tiers, ECH padding and evasion;
  - base-rate reweighting;
  - host-level aggregation.
- **4.4 Models:** XGBoost as the main model; LightGBM, RF, LR, 1D-CNN and BiLSTM; Isolation Forest and an autoencoder; the RAID 2024 C-Basic/C-Cert/C-Behav classifiers from the authors' code; Optuna tuning on source validation only.
- **4.5 Protocol:**
  - per-feature-set dedup;
  - 1:1 training balance;
  - validation-only thresholds (max-F1, FPR 10⁻³);
  - 5 seeds (20 for headline contrasts), bootstrap CIs and paired Wilcoxon tests;
  - pooled precision at realistic base rates.

## 5. Results (about 4 pages; one subsection per RQ, each ending in a boxed answer)

### 5.1 RQ1: Beyond random splits
- **Figure 2** (`fig_a_collapse`):
  - E1→E3 on MTA: 1.000 → 0.996 → 0.901.
  - Cross-dataset: MCFP→MTA 0.585 (G1+G2 without timing).
  - No source threshold survives: test FPR 0.34, and 98% of background flagged.
- **Figure 3** (`fig_f_rolling`): the hash model falls to ROC 0.41 by 2026; models without hashes stay ≥ 0.95, except in 2025; retraining rescues the hash model.
- **Robustness across choices:**
  - The result holds for six families with tuning, the RAID 2024 classifiers, unsupervised detectors, and every dedup and ratio choice.
  - Leave-one-dataset-out with pooled training doesn't help.
- **Deployment view:** at a 0.1% base rate, precision is 0.17 (no G5) vs 0.05 (hash model). At host level, 60% of infected host-hours are flagged with 0 false alarms in 127 benign host-hours (small sample: report the 95% bound).

### 5.2 RQ2: Where the signal comes from, and what is shortcut
- **Figure 4** (`fig_e_origin_probe`): benign traffic alone identifies its dataset (0.989 balanced accuracy, chance 0.25).
- **Circularity:** with SSLBL labels, E3 scores 0.684 vs 0.901 with IOC labels; G4+G5 carry 99% of the gain.
- **MCFP shortcuts:** handshake failures (no ServerHello in 40% of malicious vs 0.9% of benign flows); G1 alone scores 1.000 on MCFP.
- **Fingerprint encodings (Table 7):** hash 0.901 vs seen-flag 0.983 vs decomposed lists 0.982 vs none 0.983. The problem is the hash value, not the handshake content.
- **Leave-one-family-out:** gains concentrate in XGBoost.

### 5.3 RQ3: How early
- **Figure 5** (`fig_d_early`): N=10 (through the ServerHello) matches the whole flow (0.896 vs 0.901); N=5 gives 0.860.
- The N=3 artefact: only the TCP handshake is visible, so dedup removes the flows.
- Without timing, early features drift worse (0.37 at N=5).

### 5.4 RQ4: Cost
- **Table 8:**
  - extraction 1.7–2.7 ms per flow (full) vs 0.9–1.2 ms (Zeek-free);
  - inference ≤ 0.06 ms batched;
  - batch=1 overhead;
  - model size and RSS.
- **Message:** extraction is the cost. The Zeek-free set is cheaper and more accurate under drift (0.971).
- **Caveat:** the "edge" is a core-pinned proxy, not a real device.

### 5.5 RQ5: Visibility tiers and fingerprint drift
- **Figure 6** (`fig_b_tiers`):
  - Losing the certificate costs ≤ 0.008.
  - The ECH tier matches overall but fails on TLS 1.3 malware: ROC 0.54, recovering to 0.89 with TLS 1.3 training.
  - Handshake-visible models transfer (0.94).
- **Padding:** +256 B per data packet takes the ECH tier to about 0.59. Symmetric augmentation doesn't recover it (0.58). ClientHello padding (ECH §6.1.3) is harmless.
- **Figure 7** (`fig_c_fingerprints`): about half of later flows carry an unseen JA3/JA4; JA4 is no more robust than JA3; consistent across tree families, neutral for LR.

### 5.6 Reproducing RAID 2024 (about 0.3 pages; or move to Appendix C)
- **Reproduction:** exact for C-Basic and C-Cert; within 1 pp for C-Behav; UCNet rows from the released table exact, rebuilt rows within 0.2 pp except three C-Behav cells.
- **RF gap:** cause pending the scikit-learn 1.3.2 rerun.
- **Under our protocol:** C-Cert keeps an operating point across datasets, but only on the 45% of flows it covers.

## 6. Discussion (about 1.25 pages)

- **6.1 Reconciling literature and benchmark:** which published claims are at risk, mapped from the core-set coding. Combine 71% random splits with our E1→E3/E4 drops, and the 67% ECH-tier papers with the TLS 1.3/padding result.
- **6.2 Recommendations:**
  - **For evaluators (checklist, Table 9):**
    - temporal or cross-dataset splits;
    - validation-only thresholds;
    - FPR/PR-AUC at a stated base rate;
    - an origin probe;
    - labels independent of features;
    - per-TLS-version results;
    - the cost of extraction, not only inference.
  - **For builders:**
    - drop raw hashes (or use a seen-flag);
    - keep handshake visibility where possible;
    - plan for ECH (the size/timing tier needs TLS 1.3 training data and is padding-fragile);
    - retrain regularly;
    - aggregate at host level.
  - **For dataset creators:** benign and malicious from the same environment; release pcaps with flow-level labels; recent TLS 1.3 malware.
- **6.3 Threats to validity:**
  - MTA background is sandbox/popular-domain traffic, not an enterprise;
  - few TLS 1.3 malicious samples before 2022;
  - the 2025 test year is small;
  - ECH is simulated by masking;
  - the attacker is non-adaptive;
  - the edge is a proxy;
  - the 14-paper second-coder sample;
  - LLM-assisted screening, bounded by the spot-check;
  - no ET-BERT/YaTC, no CESNET, no own lab capture (DoHBrw pending).

## 7. Related work (about 0.75 pages)

Arp et al.; Jacobs et al.; Apruzzese et al.; Wickramasinghe et al. (S&P 2025); Barradas et al. (RAID 2024); Kanda et al.; Yu et al.; Huang & Yang. One sentence each on the delta, from plan.md §1.1. **Re-run the novelty search** before submission.

## 8. Conclusion (about 0.3 pages)

The three-sentence answer, the artefact link, and future work: campus validation in Dhaka, a real edge device, adaptive attackers, real ECH captures.

## Ethics, open science, AI-use statement

Public data only; no human subjects. Code, features, coding sheets and the registry released on Zenodo. AI tools used for screening suggestions and extraction drafts, with a human deciding and verifying every value. Follow the venue's policy.

## Appendices

- **A. Review protocol:** screening rulebook, extraction form and coding rulebook (with rule R1), validation and κ tables.
- **B. Core-set table:** the 67 papers × coded fields (possibly online only).
- **C. RAID 2024 reproduction:** full tables, deviations (slimmed inputs, library versions).
- **D. Dataset audit:** per-dataset counts, the HIKARI label mismatch, the dedup effects.
- **E. Extra results:**
  - per-family tables;
  - Optuna tuning;
  - unsupervised baselines;
  - training-set sensitivity;
  - 20-seed tests;
  - leave-one-family-out.

---

## Open items before drafting can finish

1. **PRISMA counts:** produce the final flow from the screening files (`review/screening_llm/`, `review/final_screening/`) after the strict pass and the spot-check.
2. **Venue:** confirm the venue and its page limit; this sets the budgets above.
3. **DoHBrw:** add it as a fifth source, or state it is excluded.
4. **Contribution 3 in plan.md (own 2026 lab capture):** not done. It is dropped from the contributions unless captured.
5. **UCNet RF gap:** fill in the cause after the scikit-learn 1.3.2 rerun.
6. **Taxonomy task labels (Table 2):** not a coded field yet. Derive them from titles/abstracts by a rule, or code them by hand.
7. **Related work:** re-run the search (monthly-alert item in plan.md).
