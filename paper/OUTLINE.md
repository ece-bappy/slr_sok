# Manuscript outline (v3, 9 Nov 2026): Computers & Security

**Target:** Computers & Security (Elsevier), a Q1 journal. Elsevier `elsarticle` class with numbered references (`elsarticle-num`, sort&compress) and Times (newtx). The manuscript is in `D:\new papers\manuscript` (its own git repo): `main.tex`, `sections/*.tex`, `refs.bib` (verified related work), `refs_core.bib` (67 core studies, from `scripts/core_bib.py`), and `figures/`. Build with `build.ps1`; latexmk needs Perl, which is not installed.

**Figures:** standalone PDFs at no more than the text width (390 pt), included unscaled, in Times, with the smallest text 10 pt in diagrams and 9 pt in plots. No TikZ in the manuscript: diagram sources live in `figures/src/`.

**Budget:** 14,000–16,000 words without references. **Now:** about 15,200 words drafted across sections 1–7 and 9, plus 9 figures, 13 tables and about 115 references.

**Sources of every number** (each one carries a hidden `\src{}` note in the .tex):
- `review/benchmark/RESULTS.md` and its `SUMMARY_*.md` files (benchmark, batches 1–7);
- `review/synthesis/SUMMARY.md`, `papers.csv` and `datasets.csv` (67-paper core set);
- `review/PRISMA.md`, `review/map_labels/` (291-study map), `review/coding/{kappa_report,validation_report}.md`, `review/final_screening/SPOT_CHECK.md`;
- `review/synthesis/checklist.md` (evaluation checklist), `paper/related_work_research.md` (related work).

Never type a number into the draft without its source file.

---

## Drafting status

| § | Section | Status | Words | Figures and tables | Open placeholders |
|---|---|---|---|---|---|
| – | Title | Chosen: *Do Malicious TLS Traffic Classifiers Survive Deployment? A Systematic Review and Benchmark* | – | – | – |
| – | Abstract, highlights, keywords | Keywords done; abstract and highlights not written | – | – | write last |
| 1 | Introduction | **Drafted** | 1,210 | Table 1 (RQs) | citation for the share of malware C2 over TLS; artefact DOI |
| 2 | Background | **Drafted** | 1,310 | Table 2 (feature groups × tiers), Fig. 1 (pipeline) | – |
| 3 | Review method | **Drafted** | 1,700 | Fig. 2 (PRISMA), Table 3 (extraction form) | κ for checklist items C2/C6; align the AI-use paragraph with the declarations |
| 4 | Systematic map and taxonomy | **Drafted** | 1,640 | Fig. 3 (map), Table 4 (taxonomy, all 67 cited), Table 5 (gap statistics), Table 6 (datasets used) | – |
| 5 | Benchmark methodology | **Drafted** | 1,810 | Table 7 (datasets), Table 8 (experiment matrix) | DoHBrw: add or state excluded |
| 6 | Results | **Drafted** | 3,820 | Figs. 4–9, Table 9 (pooled protocol), Table 10 (encodings), Table 11 (cost) | – |
| 7 | Reproducing RAID 2024 | **Drafted** | 1,020 | Table 12 (reproduction) | – |
| 8 | Discussion | **Not drafted** (notes only) | – | planned: checklist table + Fig. 10 (compliance) | checklist C2/C6 pending |
| 9 | Related work | **Drafted** | 1,650 | Table 13 (closest works) | discuss the benign-QUIC temporal contrast in §8 |
| 10 | Conclusion | **Not drafted** | – | – | – |
| – | Declarations | Skeleton | – | – | authors, CRediT, funding, competing interests, AI declaration, DOI |

---

## Section contents as drafted

### 1. Introduction
- **Context:** malware C2 hides in TLS, so detection relies on what stays visible. The field is growing: 35 of the 67 core studies are from 2025–26.
- **The gap:** a deployed detector meets later traffic, other networks, real-time decisions, low base rates, TLS 1.3/ECH and drifting fingerprints. These problems are documented for security ML in general and for benign encrypted-traffic classification, but not measured for malicious TLS.
- **Two closest works pull in opposite directions:**
  - Wang et al. (2022) see cross-dataset failure and recommend pooled training;
  - RAID 2024 shows TLS 1.2→1.3 transfer and leaves padding open.
- **RQ table and findings:**
  - review: 71% random splits, 22% FPR/PR-AUC, 81% TLS version unstated, 67% ECH-tier only, 45% no cost, 0 origin probes;
  - benchmark: 1.000→0.901; pooled 0.999 vs held-out 0.559; hash 0.983→0.901 and below chance by 2026; ECH tier 0.54 on TLS 1.3 and ~0.59 with padding; extraction cost; 17% precision at a 0.1% base rate.
- **Five contributions, with the narrowed novelty claim:** not the first benchmark, but the first systematic review paired with a benchmark of deployment conditions.

### 2. Background
- **2.1 Visibility:** what an observer sees under TLS 1.2, TLS 1.3 and ECH (RFC 8446, RFC 9849), and how the benchmark simulates the tiers.
- **2.2 Fingerprinting:** JA3/JA4, Chrome permutation, malware parameter drift, shared JA4+.
- **2.3 The detection pipeline (Fig. 1):** label sources, label–feature circularity, the capture-environment shortcut.
- **2.4 Threat model:** passive edge defender; non-adaptive attacker with padding and jitter; base rates 1%–0.01%.
- **2.5 Evaluation terms:** splits, operating point, PR-AUC vs ROC, pooled precision (Eq. 1). A short pointer to prior surveys.

### 3. Review method
- **Search:** 26 Oct 2026; OpenAlex, Semantic Scholar, arXiv; 5,894 records → 3,503 after de-duplication.
- **Screening:**
  - two LLM passes only *suggest* exclusions: lenient 1,856, strict 1,147 (with reasons), plus 175 under the venue rule;
  - a human screened all 325 that remained;
  - spot-check: 0/120 wrong, 60 from each pass;
  - 34 human exclusions: 20 on title, abstract or dataset section, 14 after reading the full text.
- **Core rule:** 92 candidates → 14 failed full text → 78 ranked → 67.
- **Extraction:** form (Table 3), coding rules, two-model ensemble with every quote checked and every value human-verified; validation (42/44; free text 13/20 and 15/20; 0 invented).
- **Reliability:**
  - κ on single-choice fields: median 0.56, mean 0.51 (82% agreement); list fields pooled κ 0.77;
  - weak fields, and rule R1;
  - adjudication of 106 disagreements: 63 same meaning, 28 coder 1, 15 coder 2; 17 values changed.
- **Registry:** access levels open / on request / private; CIC and UNB count as on request.
- **Map labels:** κ 0.78 / 0.82 / 0.74; 119 disputes decided by a human; spot-check 1/90 wrong.
- **Checklist items C2/C6:** coded afterwards. **κ pending.**

### 4. Systematic map and taxonomy
- **4.1 Map (Fig. 3):**
  - growth 11 → 64 studies per year;
  - threats: malware 127, DoH 58 (driven by DoHBrw), C2 34, multi-attack 27, DoS 14, other 31;
  - study types; model classes and their shift; 15% of abstracts name no model.
- **4.2 Taxonomy:** three axes (observed, learned, evaluated). Table 4 places all 67 studies by threat × visibility tier (5 / 13 / 45 / 4).
- **4.3 Gap statistics (Table 5):** paragraphs on protocol, labels and shortcuts (label-overlap κ −0.17 caveat), early decision and cost, visibility, reproducibility.
- **4.4 Datasets relied on (Table 6):** little malicious TLS in the most-used datasets (ISCX VPN has no malicious class); registration-gated access; mixed environments; HIKARI and MCFP problems.
- **4.5 Hypotheses H1–H5:** the benchmark supports four and refines H3.

### 5. Benchmark methodology
- **5.1 Datasets (Table 7):** MTA, MCFP, RAID, HIKARI, each with its limits. Why not CESNET, DoHBrw (placeholder) or the RAID campus traces.
- **5.2 Pipeline:** Zeek + TLS parser + NFStream; flow-match and JA3/JA4 checks; feature counts; visibility tags; runs without timing; the Zeek-free variant.
- **5.3 Experiments (Table 8):** E1–E4 definitions (70/15/15; grouped 5-fold; ≤2022 vs 2023–26; three cross-dataset pairs), batches 6 and 7, the probe, the blocklist audit, the padding rules.
- **5.4 Models:** XGBoost settings; LightGBM, RF, LR, CNN, BiLSTM; Isolation Forest and an autoencoder; RAID 2024 classifiers; Optuna tuning.
- **5.5 Protocol:** dedup, 1:1 training balance, validation thresholds, metrics, 5/20 seeds, bootstrap, Wilcoxon, environment, release policy.

### 6. Results (five boxed answers)
- **6.1 RQ1:**
  - collapse (Fig. 4) and rolling origin (Fig. 5);
  - robustness: families, tuning, RAID 2024, unsupervised, training choices;
  - pooled protocol vs held out (Table 9);
  - base rates and host level.
- **6.2 RQ2:** origin probe (Fig. 6), SSLBL circularity, MCFP shortcuts, ablation, encodings (Table 10), cross-family, leave-one-family-out.
- **6.3 RQ3:** early detection (Fig. 7).
- **6.4 RQ4:** cost (Table 11).
- **6.5 RQ5:** tiers (Fig. 8), TLS 1.3 diagnostic, ClientHello and record padding, evasion, fingerprint drift (Fig. 9).

### 7. Reproducing RAID 2024
- **Reproduction:** exact under scikit-learn 1.3.2; the C-Behav DT is exact on the grid pass.
- **UCNet:** rebuild with stage counts; released-table rows exact; the rebuilt-input rows' ≤ 1.2 pp gap is independent of version.
- **Under our protocol:** four findings, including coverage (C-Cert scores 28% of malicious MTA flows). Table 12.

### 8. Discussion (to draft next)
- **8.1 Literature vs benchmark:** which published claims are at risk. Combine the 71% random splits with the E1→E3/E4 drops and the pooled-protocol result; the 67% ECH-tier studies with the TLS 1.3 and padding results; the 45% no-cost with the extraction cost.
- **8.2 Evaluation checklist** (table + Fig. 10, compliance of the 67 studies). Scores from `review/synthesis/checklist.md`:
  - C1 temporal or cross-dataset 25%;
  - C3 FPR or PR-AUC 22% (upper bound);
  - C4 origin probe 0%;
  - C5 labels independent 96% (κ −0.17 caveat);
  - C7 end-to-end cost 21%;
  - C8 data released 16%;
  - 51/67 meet at most 2 of 6, none meets all 6.
  - **C2 (tuning data) and C6 (per-TLS-version results) are being coded by Main;** mark them pending until then.
- **8.3 For detector builders:** drop raw hashes (a seen-flag is enough); keep handshake visibility where possible; plan for ECH (TLS 1.3 training data, padding fragility); retrain regularly; aggregate per host; report coverage.
- **8.4 For dataset creators:** benign and malicious from the same environment; packet captures with flow-level labels; recent TLS 1.3 malware; open access.
- **8.5 Open problems:** adaptive attackers vs size-and-timing detectors; real ECH captures; label provenance at scale; real edge hardware. Also the contrast with benign QUIC, where temporal splits did not hurt (Sharma et al. 2026), kept as a hypothesis.
- **8.6 Threats to validity:**
  - **Review:** LLM-assisted screening (bounded by the spot-check); 14-paper second-coder sample; core-set selection bias; map labels from abstracts.
  - **Benchmark:**
    - MTA background is not an enterprise;
    - few TLS 1.3 malicious flows before 2022; the small 2025 test year;
    - ECH simulated by masking; non-adaptive attacker; edge proxy;
    - no ET-BERT/YaTC, CESNET or own lab capture;
    - batch 7 caveats: four sources, not Wang's five; held-out rows from b6 LODO with 50k caps; HIKARI is a two-attacker transfer test.

### 9. Related work
- **Done:** four strands (surveys; ML-for-security pitfalls; protocol critiques of encrypted-traffic classification; malicious TLS under drift and visibility), plus positioning.
- **Closest works checked against full texts:** Wang 2022, RAID 2024, Ji 2024, Oh 2022, Abu-Adaiq 2026 and Wickramasinghe 2025.
- **Wang et al.'s pooled protocol** is tested on our data (batch 7, with a footnote of caveats).
- **Table 13:** no prior work has more than three of the six properties fully.

### 10. Conclusion (about 400 words, to draft)
The five answers in one paragraph; the artefact link; future work (campus validation in Dhaka, a real edge device, adaptive attackers, real ECH captures).

### Declarations
Data and code availability (DOI); ethics (public data only, no human subjects); generative-AI declaration per Elsevier policy; CRediT; competing interests; funding.

### Supplementary material
- **S1:** rulebooks (screening, coding with R1, map labels, checklist) and the extraction prompt.
- **S2:** the 67-study coding table and the 291-study map labels.
- **S3:** per-seed results, Optuna tuning, per-family tables, 20-seed tests, training-set sensitivity, batch 7 tables.
- **S4:** RAID 2024 reproduction cell tables and UCNet stage counts.

---

## Open items

1. **Journal:** DONE. Computers & Security.
2. **PRISMA counts:** DONE (`review/PRISMA.md`). In Fig. 2 and §3.
3. **DoHBrw:** OPEN. Add it as a fifth source, or keep "not used" in §5.1. The map's 20% DoH share makes adding it attractive.
4. **Own 2026 lab capture (contribution 3 in plan.md):** DROPPED. Not done, and not claimed in the paper.
5. **UCNet RF gap:** DONE. The scikit-learn version; in §7.
6. **Map task labels:** DONE. In §3 and §4.1.
7. **Checklist (Fig. 10):** PARTLY DONE. Six items scored; C2/C6 being coded by Main (Flash Lite done, Gemini 3.8 via agy, the user adjudicates `todo/08_checklist_review.csv`).
8. **Related work:** DONE. Positioning against Wang et al. and RAID 2024 from full texts; batch 7 in the text.
9. **Discussion and conclusion:** OPEN. Drafting next.
10. **Abstract and highlights:** OPEN. Write after §8 and §10.
11. **Introduction citation:** OPEN. A primary or vendor source for the share of malware C2 carried over TLS.
12. **Author information:** OPEN, from the user. Authors and affiliations, CRediT, funding, competing interests, artefact DOI.
13. **Reference check:** OPEN.
    - S0971 (arXiv 2602.09606): its author field came from the search record ("Kemal Bicakci A"); check it.
    - S2326 and S2360: no volume in Crossref (early access).
