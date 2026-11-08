# Manuscript outline (v2, 8 Nov 2026): Q1 journal version

**Format:** a Q1 journal article combining a systematic review with an empirical benchmark. There is no hard page limit like a conference SoK has, so the conference appendices (review protocol, reproduction, dataset audit) move into the body, and the review covers the full 291-paper map as well as the 67-paper core set.

**Budget:** about 14,000â€“16,000 words without references, 10â€“12 figures, 10â€“12 tables, about 120 references. Supplementary material holds the per-paper coding table, the per-seed CSVs and the rulebooks.

**Candidate journals.** Choose before drafting, because length and style differ.

| Journal | Fit | Length / style notes |
|---|---|---|
| ACM Computing Surveys | A systematic review plus a benchmark is a natural fit; high impact | About 35 pages in the acmsmall format; expects a broad survey, so the 291-paper map gets more weight |
| IEEE TDSC / IEEE TIFS | Security-flagship journals; strong for the benchmark findings | About 14â€“16 two-column pages before overlength charges; would need tighter Sections 3 and 7 |
| Computers & Security (Elsevier) | Takes long empirical-plus-review papers; quick turnaround | No strict limit; single-column review format; structured abstract and highlights required |
| IEEE TNSM / Computer Networks | Network-measurement audience | Weaker fit for the review part |

The word budgets below suit Computing Surveys or Computers & Security. For TDSC or TIFS, cut about 25%: shorten 3.2, 7 and 8.5, and move them to supplementary material.

**Sources of every number:**
- `review/benchmark/RESULTS.md` (benchmark) and the `SUMMARY_*.md` files it links.
- `review/synthesis/SUMMARY.md` (67-paper core set).
- `review/coding/kappa_report.md`, `review/coding/validation_report.md`, `review/final_screening/SPOT_CHECK.md`.
- `plan.md` Â§1.1 (prior work) and Â§4 (protocol).

Never type a number into the draft without its source file.

---

## Title (pick one; journals usually drop the "SoK:" prefix)

1. *Do Malicious TLS Traffic Classifiers Survive Deployment? A Systematic Review and Benchmark*
2. *Machine-Learning Detection of Malicious TLS Traffic Under Drift, Dataset Shift and Shrinking Visibility: A Systematic Review and Empirical Evaluation*
3. *What Ninety-Nine Percent Hides: A Systematic Review and Benchmark of Malicious TLS Traffic Detection*

## Abstract (about 250 words; structured if the journal asks: Context / Objective / Method / Results / Conclusions)

1. **Problem:** the literature reports 95â€“99.9% accuracy, but under protocols a deployed detector never meets.
2. **What we did:** a PRISMA review of 3,503 records down to 291 eligible studies (2019â€“2026); human-verified coding of a 67-paper core set (Îº reported); a controlled benchmark on four public sources; a reproduction of RAID 2024.
3. **Headline findings, with numbers:**
   - About 71% of core-set main results use random or stratified random splits; 4% are temporal; 22% report an FPR or PR-AUC.
   - Temporal and cross-dataset drops; no source-validated threshold survives a dataset change.
   - Raw JA3/JA4 hashes as features age badly (0.901 vs 0.983 without them, 20 seeds).
   - Under ECH, size/timing models trained on TLS 1.2 malware fail on TLS 1.3 malware (ROC 0.54), and 256-byte padding defeats them even with TLS 1.3 training.
4. **Recommendations, the checklist and the artefact release.**

**Highlights** (Elsevier, 3â€“5 bullets of â‰¤ 85 characters each): written last.

---

## 1. Introduction (about 1,300 words)

- **The gap:** high reported accuracy, against what deployment needs: a new network, a later time, a real-time decision, and less visibility under TLS 1.3/ECH.
- **Why now:** TLS 1.3 is the majority, ECH is being rolled out, and fingerprinting moved from JA3 to JA4. The field is growing fast: 35 of the 67 core papers are from 2025â€“26.
- **Why a review alone and a benchmark alone are not enough:** the review shows what the field does; the benchmark shows what that costs.
- **RQ1â€“RQ5:** stated in full, as a table (plan.md Â§2).
- **Contributions:**
  1. A systematic review: a PRISMA flow, a 291-paper map, a taxonomy and gap statistics from human-verified coding.
  2. A unified, visibility-tagged feature pipeline from raw pcaps (G1â€“G5, plus a Zeek-free variant).
  3. A controlled benchmark answering RQ1â€“RQ5:
     - an origin probe;
     - a label-circularity audit;
     - rolling-origin drift;
     - an ECH padding analysis;
     - base-rate and host-level views;
     - end-to-end cost.
  4. An independent reproduction of the RAID 2024 classifiers, including the authors' released UCNet table.
  5. An evaluation checklist and deployment recommendations.
- **Paper organisation:** a short paragraph.

## 2. Background (about 1,500 words)

- **2.1 TLS visibility:**
  - TLS 1.2: certificate in clear.
  - TLS 1.3: certificate encrypted, ClientHello visible.
  - TLS 1.3 + ECH: outer ClientHello only, plus the padding guidance in draft-ietf-tls-esni.
  - **Table 1:** feature groups G1â€“G5 Ã— visibility tier.
- **2.2 Fingerprinting:** JA3/JA3S, JA4/JA4S; GREASE and extension randomization; JARM in brief.
- **2.3 How malicious TLS is detected:** an ML pipeline sketch (**Figure 1**: capture â†’ flow assembly â†’ features â†’ model â†’ threshold â†’ alert), including where labels come from.
- **2.4 Threat and deployment model:**
  - The defender is a passive edge monitor with no decryption and a real-time budget.
  - The attacker is a non-adaptive malware operator, with simple padding and jitter as the evasion bound.
  - Base rates are at or below 1% malicious.
- **2.5 Evaluation terms:**
  - random / grouped / temporal / cross-dataset splits;
  - operating point = a threshold chosen on validation only;
  - PR-AUC vs ROC under prevalence;
  - pooled precision at a base rate.
- **2.6 Prior surveys and SoKs:** how this paper differs; the short version of Section 9.

## 3. Review method (about 1,800 words; the conference appendix moves here)

- **3.1 Protocol:**
  - search string, databases and dates (search v1 vs v2, 3,503 unique records);
  - inclusion and exclusion criteria;
  - the low_venue rule.
- **3.2 Screening:**
  - LLM pre-screening only suggests (lenient and strict passes), and a human decides;
  - same-prompt agreement check: 13 of 15 records;
  - spot-check: 0/120 wrong exclusions, 95% upper bound about 2.5%;
  - **Figure 2:** PRISMA flow. **TODO:** regenerate the final counts.
- **3.3 Core set:** the rule fixed before coding (CORE A*/A, Scimago Q1 CS, top-10% cited); 92 candidates â†’ 67 papers.
- **3.4 Extraction:**
  - the form and the RQ each field serves (**Table 2**, plan.md Â§4);
  - input rules (deterministic artefact links, verbatim evidence);
  - a two-model ensemble with human verification of every core paper.
- **3.5 Reliability:**
  - blind validation on 4 held-out papers: agreed answers 42/44 correct; free text 13/20 and 15/20 correct; 0 invented;
  - second coder on 14 papers: single-choice agreement 82%, median Îº 0.56; list fields pooled Îº 0.77;
  - adjudication changed 17 verified values;
  - rulebook change R1, reported with Îº both ways.
- **3.6 Dataset registry:**
  - one check per dataset;
  - the "public" levels (open / registration / private);
  - CIC/UNB data counts as registration-gated.

## 4. Systematic map and taxonomy (about 2,300 words)

- **4.1 The 291-paper map:** from metadata and abstracts.
  - papers per year (growth);
  - venue types;
  - task (C2/botnet, DoH tunnelling, web attacks/brute force, generic malware, anomaly);
  - model families over time (classical â†’ DL â†’ transformers/LLMs).
  - **Figure 3** (`review/map_labels/fig_map.pdf`): done 8 Nov. Two-LLM blind labels, human-decided disputes; agreement κ 0.78 / 0.82 / 0.74; spot check 1/90 agreed labels wrong.
- **4.2 Taxonomy (Figure 4 / Table 3):** three axes.
  - what is observed: G1â€“G5 and the visibility tier;
  - how it is learned: model family, granularity, first-N;
  - how it is evaluated: split, labels, metrics, cost.
  - Place the 67 core papers on these axes, citing representative papers per cell.
- **4.3 Gap statistics on the core set (Table 4 plus a compact figure), each tied to an RQ:**
  - **Evaluation protocol (RQ1):**
    - main split random or stratified 71%;
    - temporal 4%, host-grouped 6%, cross-dataset 4% of main results;
    - easy-vs-hard reported in 16%.
  - **Metrics:** FPR or PR-AUC in 22%; accuracy only in 4%.
  - **Labels (RQ2):** dataset_provided 81%; labelâ€“feature overlap in 2 papers.
  - **Shortcut checks:** none 34%; most "checks" are ablations; no paper runs an origin probe.
  - **Visibility (RQ5):**
    - 67% use only ECH-surviving features;
    - 81% don't state the TLS version;
    - 2 papers consider ECH;
    - fingerprints are used in 6 papers.
  - **Early detection (RQ3):** 60% classify the whole flow.
  - **Cost (RQ4):** 45% report none; 21% report end-to-end cost.
  - **Reproducibility:**
    - code 24%, data 16%;
    - 63% use an openly downloadable dataset, 79% an obtainable one;
    - 18% use only private captures.
- **4.4 Datasets the field relies on (Table 5):**
  - Usage counts: CIC-IDS2017 14, DoHBrw 13, ISCX VPN 13, USTC-TFC 11, MCFP 9.
  - Access level, TLS content and known quality issues per dataset.
  - Our HIKARI finding: benign traffic is header-only, and the label tables mismatch the pcaps.
- **4.5 Takeaways:** the hypotheses that Sections 5â€“6 test.

## 5. Benchmark methodology (about 2,000 words)

- **5.1 Datasets (Table 6, the full audit):**
  - MTA 2019â€“2026, labelled from IOC/sandbox metadata and not from certificates or JA3;
  - Stratosphere MCFP;
  - RAID 2024;
  - HIKARI (clean-label subset, â€¡ 2-attacker caveat);
  - DoHBrw: **pending** (open item 3).
  - Per dataset: flows, dedup counts, TLS versions, class balance, capture environment.
- **5.2 Pipeline:**
  - Zeek + tlsfp + NFStream;
  - visibility tags;
  - checks: JA3/JA4 against Wireshark (15/15), join rate 99.98%;
  - the Zeek-free variant.
  - **Figure 5:** pipeline diagram.
- **5.3 Experiment matrix (Table 7):**
  - E1â€“E9;
  - batch 6: rolling origin, leave-one-family-out and leave-one-dataset-out, encodings, padding and evasion, base rate, host level, training-set sensitivity.
- **5.4 Models:**
  - XGBoost as the main model; LightGBM, RF, LR, 1D-CNN and BiLSTM;
  - Isolation Forest and an autoencoder;
  - the RAID 2024 classifiers from the authors' code;
  - Optuna tuning on source validation only.
- **5.5 Protocol and statistics:**
  - per-feature-set dedup; 1:1 training balance;
  - validation-only thresholds;
  - 5 seeds (20 for headline contrasts), bootstrap CIs, paired Wilcoxon tests;
  - pooled precision at base rates;
  - hardware and software versions.

## 6. Results (about 4,500 words; one subsection per RQ, each ending in a boxed answer)

### 6.1 RQ1: Beyond random splits
- **Figure 6** (`fig_a_collapse`):
  - MTA: 1.000 â†’ 0.996 â†’ 0.901 from E1 to E3.
  - MCFPâ†’MTA: 0.585.
  - No source threshold survives a dataset change.
- **Figure 7** (`fig_f_rolling`): the hash model falls to ROC 0.41 by 2026; models without hashes stay â‰¥ 0.95, except in 2025; retraining rescues the hash model.
- **Robustness across choices:**
  - six families, tuned and untuned;
  - the RAID 2024 classifiers;
  - unsupervised detectors;
  - dedup and class-ratio choices;
  - leave-one-dataset-out.
- **Deployment view:**
  - precision at a 0.1% base rate: 0.17 (no G5) vs 0.05 (hash model);
  - host level: 60% of infected host-hours flagged with 0 false alarms in 127 benign host-hours (with the 95% bound).

### 6.2 RQ2: Signal, shortcuts and circularity
- **Figure 8** (`fig_e_origin_probe`): the origin probe scores 0.989 (chance 0.25).
- **Circularity:** SSLBL labels give 0.684 vs 0.901 with IOC labels.
- **MCFP shortcuts:** handshake failures, and G1 alone scores 1.000.
- **Table 8 (fingerprint encodings):** hash 0.901, seen-flag 0.983, decomposed lists 0.982, none 0.983.
- **Leave-one-family-out:** gains concentrate in XGBoost.

### 6.3 RQ3: How early
- **Figure 9** (`fig_d_early`):
  - N=10 matches the whole flow (0.896 vs 0.901);
  - N=5 gives 0.860;
  - N=3 is an artefact;
  - without timing, N=5 scores 0.37.

### 6.4 RQ4: Cost
- **Table 9:**
  - extraction 1.7â€“2.7 ms per flow (full) vs 0.9â€“1.2 ms (Zeek-free);
  - inference â‰¤ 0.06 ms batched;
  - batch=1 overhead;
  - model size and memory.
- **Message:** extraction is the cost. The Zeek-free set is also the more accurate one under drift (0.971).
- **Caveat:** the edge is a core-pinned proxy.

### 6.5 RQ5: Visibility tiers and fingerprint drift
- **Figure 10** (`fig_b_tiers`):
  - Losing the certificate costs â‰¤ 0.008.
  - On TLS 1.3 malware, the ECH tier scores ROC 0.54, or 0.89 with TLS 1.3 training; handshake-visible models score 0.94.
- **Padding:**
  - +256 B per data packet takes the ECH tier to about 0.59;
  - symmetric augmentation stays at 0.58;
  - ClientHello padding is harmless.
- **Figure 11** (`fig_c_fingerprints`): about half of later flows carry an unseen hash; JA4 is no more robust than JA3.

## 7. Reproducing RAID 2024 (about 900 words; its own section in the journal version)

- **Why reproduce:** the closest prior work, and the only one with released code and data.
- **Reproduction:**
  - C-Basic and C-Cert exact; C-Behav within 1 pp;
  - UCNet released-table rows exact; rebuilt rows within 0.2 pp except three C-Behav cells;
  - the RF gap's cause: after the scikit-learn 1.3.2 rerun.
- **Deviations:** slimmed inputs, library versions.
- **Under our protocol:**
  - on MTA E3, C-Cert scores 0.880 and C-Behav 0.890, vs XGB 0.941 on the same rows;
  - C-Cert keeps a cross-dataset operating point, but only on the 45% of flows it covers.
- **Table 10:** paper vs ours.

## 8. Discussion (about 2,000 words)

- **8.1 Literature vs benchmark:** which published claims are at risk. Combine 71% random splits with the E1â†’E3/E4 drops, and the 67% ECH-tier papers with the TLS 1.3/padding result.
- **8.2 Evaluation checklist (Table 11):**
  - temporal or cross-dataset splits;
  - validation-only thresholds;
  - FPR/PR-AUC at a stated base rate;
  - an origin probe;
  - labels independent of features;
  - per-TLS-version results;
  - end-to-end cost;
  - releasing pcaps and labels.
  - Score each core paper against the checklist: a compliance figure (**Figure 12**).
- **8.3 Recommendations for detector builders:**
  - drop raw hashes (or use a seen-flag);
  - keep handshake visibility where possible;
  - plan for ECH (TLS 1.3 training data; padding fragility);
  - retrain regularly;
  - aggregate at host level.
- **8.4 Recommendations for dataset creators:** benign and malicious from the same environment; pcaps with flow-level labels; recent TLS 1.3 malware; open access, not registration-gated.
- **8.5 Open problems:** adaptive attackers vs ECH-tier detectors, real ECH captures, label provenance at scale, real edge hardware.
- **8.6 Threats to validity:**
  - **Review:**
    - LLM-assisted screening, bounded by the spot-check;
    - a 14-paper second-coder sample;
    - core-set selection bias.
  - **Benchmark:**
    - MTA background is not an enterprise;
    - few TLS 1.3 malicious samples before 2022;
    - the 2025 test year is small;
    - ECH simulated by masking;
    - a non-adaptive attacker;
    - the edge is a proxy;
    - no ET-BERT/YaTC, no CESNET, no own lab capture.

## 9. Related work (about 1,000 words)

- **Generic ML-for-security pitfalls:** Arp et al.; Jacobs et al.; Apruzzese et al.
- **Encrypted traffic classification SoKs:** Wickramasinghe et al. (S&P 2025); Yu et al.; Huang & Yang.
- **Malicious TLS specifically:** Barradas et al. (RAID 2024); Kanda et al.
- **Earlier surveys of encrypted malicious traffic detection:** find and cite them. **TODO:** run the novelty search.
- One sentence on the delta per work.

## 10. Conclusion (about 400 words)

The answers to RQ1â€“RQ5 in one paragraph, the artefact link, and future work (campus validation in Dhaka, a real edge device, adaptive attackers, real ECH captures).

## Declarations

Data and code availability (Zenodo DOI); ethics (public data only, no human subjects); generative-AI use statement per journal policy (screening suggestions, extraction drafts, a human verifying every value); funding; competing interests; CRediT author contributions.

## Supplementary material

- **S1:** rulebooks (screening, coding with R1) and the extraction prompt.
- **S2:** the 67-paper coding table and the 291-paper map.
- **S3:** per-seed results, Optuna tuning, per-family tables, 20-seed tests, training-set sensitivity.
- **S4:** the RAID 2024 reproduction cell tables.

---

## Open items before drafting can finish

1. **Journal:** DONE: Computers & Security (Elsevier class, manuscript in `D:\new papers\manuscript`).
2. **PRISMA counts:** DONE 8 Nov: `review/PRISMA.md` from `scripts/prisma_counts.py` (5,894 identified; 3,503 screened; 325 assessed by a human; 291 included; 67 core).
3. **DoHBrw:** add it as a fifth source, or state it is excluded.
4. **Own 2026 lab capture (contribution 3 in plan.md):** not done; dropped unless captured.
5. **UCNet RF gap:** DONE: the scikit-learn version (1.3.2 reproduces it exactly); the remaining ≤ 1.2 pp UCNet gaps come from our rebuilt input files (`SUMMARY_r24.md`, 89b85a0).
6. **Task labels for the 291-paper map:** DONE 8 Nov (`review/map_labels/`, rulebook `review/coding/map_label_rulebook.txt`).
7. **Checklist scores for Figure 12:** PARTLY DONE 8 Nov: `review/synthesis/checklist.md` from `scripts/checklist_scores.py`. Six of eight items scored from the coding. C2 (validation-only thresholds) and C6 (per-TLS-version results) are not in the coding scheme: either code them for the 67 papers or drop them from the figure. C5 rests on label_feature_overlap, whose κ was −0.17 before adjudication; say so.
8. **Related work:** DONE in the paper session (Wang et al. 2022 positioning, b832e2d; batch 7 tests their protocol, a7e8164).
