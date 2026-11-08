# Related-work research: ML detection of malicious TLS traffic (SoK + benchmark)

Compiled 2026-11-08 for the Computers & Security submission.

How to read this file:
- **Verified** means the bibliographic data was checked on an authoritative page: the publisher or DOI landing page, a Crossref API record (`api.crossref.org/works/<doi>`), the arXiv abstract page, USENIX/NDSS/IETF pages, J-STAGE or PMC. The URL used is given for each item.
- **BibTeX**: every verified item has a full entry under the stated key in `related_work_candidates.bib`, so the entries are not repeated here. Items in "Unverified/uncertain" are not in the .bib file.
- Fields that could not be confirmed were left out.
- DBLP refused automated access (bot wall), and MDPI and ScienceDirect landing pages returned 403. Crossref was used for those items instead.

---

## 1. Verified core citations (task 1)

| # | Key | Bibliographic data (verified) | Verified at |
|---|-----|-------------------------------|-------------|
| 1 | `arp2022dos` | D. Arp, E. Quiring, F. Pendlebury, A. Warnecke, F. Pierazzi, C. Wressnegger, L. Cavallaro, K. Rieck. "Dos and Don'ts of Machine Learning in Computer Security." 31st USENIX Security Symposium, 2022, pp. 3971–3988. ISBN 978-1-939133-31-1 (USENIX papers have no DOI). | https://www.usenix.org/conference/usenixsecurity22/presentation/arp |
| 2 | `jacobs2022emperor` | A. S. Jacobs, R. Beltiukov, W. Willinger, R. A. Ferreira, A. Gupta, L. Z. Granville. "AI/ML for Network Security: The Emperor has no Clothes." ACM CCS 2022, pp. 1537–1551. doi:10.1145/3548606.3560609 | https://api.crossref.org/works/10.1145/3548606.3560609 |
| 3 | `apruzzese2023sok` | G. Apruzzese, P. Laskov, J. Schneider. "SoK: Pragmatic Assessment of Machine Learning for Network Intrusion Detection." IEEE EuroS&P 2023, pp. 592–614. doi:10.1109/EuroSP57164.2023.00042; arXiv:2305.00550 | Crossref record for the DOI; https://arxiv.org/abs/2305.00550 |
| 4 | `wickramasinghe2025sok` | N. Wickramasinghe, A. Shaghaghi, G. Tsudik, S. Jha. "SoK: Decoding the Enigma of Encrypted Network Traffic Classifiers." IEEE S&P 2025, pp. 1825–1843. doi:10.1109/SP61157.2025.00165; arXiv:2503.20093 (this ID is correct) | https://arxiv.org/abs/2503.20093 ; Crossref |
| 5 | `barradas2024extending` | D. Barradas, C. Novo, B. Portela, S. Romeiro, N. Santos. "Extending C2 Traffic Detection Methodologies: From TLS 1.2 to TLS 1.3-enabled Malware." RAID 2024 (27th Int. Symp. on Research in Attacks, Intrusions and Defenses), ACM, pp. 181–196. doi:10.1145/3678890.3678921 (this DOI is correct) | https://api.crossref.org/works/10.1145/3678890.3678921 |
| 6 | `kanda2025analysis` | A. Kanda, M. Hashimoto, T. Okubo. "An Analysis of TLS Parameter Variation in Malware C2 Communication." Journal of Information Processing 33 (2025), pp. 1119–1127. doi:10.2197/ipsjjip.33.1119 (this DOI is correct) | https://www.jstage.jst.go.jp/article/ipsjjip/33/0/33_1119/_article |
| 7 | `yu2026shortcut` | Q. Yu, C. Lin, Z. Ma, Z. Song, Y. Lu, G. Yang, D. Qi. "Shortcut in Generalization: Rethinking Evaluation Protocol for Encrypted Traffic Classification." arXiv:2610.17961, submitted 13 Oct 2026. The arXiv comments say it was accepted at IEEE CSCloud 2026. No proceedings DOI or pages exist yet. | https://arxiv.org/abs/2610.17961 |
| 8 | `zhao2025sweet` | Y. Zhao, G. Dettori, M. Boffa, L. Vassio, M. Mellia. "The Sweet Danger of Sugar: Debunking Representation Learning for Encrypted Traffic Classification." Proc. ACM SIGCOMM 2025, pp. 296–310. doi:10.1145/3718958.3750498; arXiv:2507.16438 | https://arxiv.org/abs/2507.16438 ; Crossref |
| 9 | `huang2026sok` | S. Huang, S. Yang. "SoK: Where Do Flow Labels Come From? Auditing Label Provenance in Encrypted Traffic Benchmarks." arXiv:2609.02140, submitted 2 Sep 2026. Preprint only, with no venue listed. | https://arxiv.org/abs/2609.02140 |
| 10 | `engelen2021troubleshooting` | G. Engelen, V. Rimmer, W. Joosen. "Troubleshooting an Intrusion Detection Dataset: the CICIDS2017 Case Study." 2021 IEEE Security and Privacy Workshops (SPW), pp. 7–12. doi:10.1109/SPW53761.2021.00009 | https://api.crossref.org/works/10.1109/SPW53761.2021.00009 |
| 11 | `fu2023hypervision` | C. Fu, Q. Li, K. Xu. "Detecting Unknown Encrypted Malicious Traffic in Real Time via Flow Interaction Graph Analysis" (HyperVision). NDSS 2023. doi:10.14722/ndss.2023.23080; arXiv:2301.13686 (this ID is correct) | https://arxiv.org/abs/2301.13686 ; https://ndss-symposium.org/ndss-paper/detecting-unknown-encrypted-malicious-traffic-in-real-time-via-flow-interaction-graph-analysis ; Crossref |
| 12 | `ferriyan2021generating` | A. Ferriyan, A. H. Thamrin, K. Takeda, J. Murai. "Generating Network Intrusion Detection Dataset Based on Real and Encrypted Synthetic Attack Traffic" (HIKARI-2021). Applied Sciences 11(17):7868, 2021. doi:10.3390/app11177868 | https://api.crossref.org/works/10.3390/app11177868 |
| 13a | `anderson2016identifying` | B. Anderson, D. McGrew. "Identifying Encrypted Malware Traffic with Contextual Flow Data." AISec 2016, ACM, pp. 35–46. doi:10.1145/2996758.2996768 | https://api.crossref.org/works/10.1145/2996758.2996768 |
| 13b | `anderson2017machine` | B. Anderson, D. McGrew. "Machine Learning for Encrypted Malware Traffic Classification: Accounting for Noisy Labels and Non-Stationarity." KDD 2017, ACM, pp. 1723–1732. doi:10.1145/3097983.3098163 | https://api.crossref.org/works/10.1145/3097983.3098163 |
| 13c | `anderson2018deciphering` | B. Anderson, S. Paul, D. McGrew. "Deciphering Malware's Use of TLS (Without Decryption)." J. Computer Virology and Hacking Techniques 14(3):195–211, 2018 (online 31 Aug 2017). doi:10.1007/s11416-017-0306-6; arXiv:1607.01639 | https://api.crossref.org/works/10.1007/s11416-017-0306-6 |

What each paper does and how we use it:

1. **Arp et al. 2022.** Identifies 10 recurring pitfalls in security ML, such as sampling bias, data snooping, spurious correlations and the base-rate fallacy, and measures how often they occur in top-venue papers. *Use:* this is the pitfall taxonomy we code each reviewed paper against. Our contribution is to quantify these pitfalls for malicious TLS specifically and to show their effect empirically.
2. **Jacobs et al. 2022.** Introduces Trustee, which extracts decision trees from black-box network-security models and shows that published models rely on shortcuts and underspecified features. *Use:* evidence that shortcut learning is common in network ML. We show a TLS-specific version of it: dataset-of-origin shortcuts and label-feature circularity.
3. **Apruzzese et al. 2023.** A SoK that re-evaluates ML-based NIDS across many settings and hardware platforms, and includes a practitioner user study, arguing for "pragmatic" assessment that includes cost. *Use:* supports our cost analysis (feature extraction dominates cost). They cover generic flow-based NIDS, not TLS.
4. **Wickramasinghe et al. 2025.** A SoK of ML traffic classifiers with 348 feature-occlusion experiments. It finds that many "encrypted" classifiers were trained on unencrypted legacy data and overfit to design oversights. *Use:* this is the closest SoK in scope. It covers generic encrypted-traffic classification (application or service identification). It does not cover malicious-TLS detection, temporal or cross-dataset collapse, JA3/JA4 ageing, or TLS 1.3 and padding robustness.
5. **Barradas et al. 2024.** Adapts TLS 1.2 C2 classifiers to TLS 1.3 by inferring certificate size and filtering handshake records. It reports more than 93% detection on TLS 1.3 after training on TLS 1.2 only, and explicitly leaves record padding out of scope. *Use:* this is the main point of contrast for our finding that size/timing models trained on TLS 1.2 fail on TLS 1.3 malware and are defeated by padding. We test the threat model they excluded.
6. **Kanda et al. 2025.** Uses about 11.5 years of malware C2 captures (Trickbot, IcedID, Cobalt Strike) to define "Parameter Fluctuation" and "Parameter Drift" in TLS client parameters. *Use:* direct measurement support for our finding that raw JA3/JA4 hashes age badly. We add the downstream ML consequence of that drift.
7. **Yu et al. 2026.** Shows that encrypted-traffic-classification results are inflated by field-level shortcuts such as Source-IP overlap, by cross-partition sharing, and by train/test processing mismatches. Increasing IP overlap from 0% to 100% adds about 32–33 points of accuracy. *Use:* supports our dataset-of-origin shortcut finding. It studies three unnamed public ETC datasets, and the abstract mentions neither malicious traffic nor temporal splits.
8. **Zhao et al. 2025 (SIGCOMM).** Shows that representation-learning ETC models score high only because flawed data preparation leaks shortcuts, and proposes Pcap-Encoder with a stricter evaluation methodology. *Use:* supports our claim that random splits inflate results. It concerns application classification, not malware.
9. **Huang & Yang 2026.** Audits label provenance in 14 encrypted-traffic benchmark entries. Downstream papers' labels disagree with the recovered record in 8 of 23 referenced cells, and side-channel-only classifiers reach a balanced-accuracy ceiling of 0.56–0.76. *Use:* closely related to our label-feature circularity point. Its abstract does not mention malware or blocklist labels, so our blocklist-circularity finding remains distinct.
10. **Engelen et al. 2021.** Documents labelling and feature-extraction (CICFlowMeter) errors in CIC-IDS2017. *Use:* dataset-quality background for the CIC-family datasets in our benchmark.
11. **Fu et al. 2023 (HyperVision).** An unsupervised flow-interaction-graph detector for encrypted malicious traffic, evaluated on 92 datasets and 48 attacks. *Use:* a representative graph-based or unsupervised approach in the review. Whether it holds up temporally is outside its own evaluation.
12. **Ferriyan et al. 2021 (HIKARI-2021).** A NIDS dataset with encrypted synthetic attack traffic plus real benign background traffic. *Use:* one of our benchmark datasets and a source of dataset-of-origin shortcuts.
13. **Anderson & McGrew 2016/2017; Anderson, Paul & McGrew 2018.** Cisco's foundational work on detecting malware TLS without decryption, combining TLS ClientHello, certificate, DNS and HTTP context with flow features. The KDD'17 paper explicitly names noisy labels and non-stationarity as the core difficulties. *Use:* the KDD'17 paper is the earliest statement of our temporal-drift thesis. We revisit it with modern data, TLS 1.3 and JA4.

---

## 2. Corrections (errors or imprecisions in the candidate list)

1. **"Debunking Representation Learning for Encrypted Traffic Classification" (arXiv 2507.16438).** The full title is "**The Sweet Danger of Sugar:** Debunking Representation Learning for Encrypted Traffic Classification" by Zhao, Dettori, Boffa, Vassio, Mellia. It was published at **ACM SIGCOMM 2025**, pp. 296–310, doi:10.1145/3718958.3750498. Cite the SIGCOMM version, not the bare arXiv one.
2. **Engelen, Rimmer, Joosen (2021).** The venue is the **2021 IEEE Security and Privacy Workshops (SPW)** (the WTMC workshop), pp. 7–12, doi:10.1109/SPW53761.2021.00009. It is not the main IEEE S&P conference, although the imec repository mislabels it that way.
3. **HyperVision.** The arXiv abstract page lists no venue. The NDSS 2023 DOI is **10.14722/ndss.2023.23080**, confirmed by Crossref. Cite the NDSS version.
4. **Yu et al. "CSCloud 2026".** The only evidence for the venue is the authors' arXiv comment ("Accepted for publication at IEEE CSCloud 2026"). No proceedings record or DOI exists yet. Cite it as an arXiv preprint "to appear in IEEE CSCloud 2026", or recheck before camera-ready. The arXiv ID 2610.17961 resolves correctly.
5. **Huang & Yang (arXiv 2609.02140).** Preprint only: no venue, not peer reviewed. Do not attach a venue to it. Its abstract does not cover malware or blocklist labels.
6. **Barradas/Novo RAID 2024.** "Barradas, Novo et al." matches the Crossref author order: Barradas, Novo, Portela, Romeiro, Santos. Pages are 181–196.
7. **Wickramasinghe et al.** The ID arXiv:2503.20093 is correct. Add pages 1825–1843 and the publisher DOI 10.1109/SP61157.2025.00165.
8. **Anderson, Paul, McGrew, JCVHT.** It appeared online in 2017 but the issue is 2018. Use 2018 with vol. 14(3), pp. 195–211.
9. **Transcending Transcend (S&P 2022).** Crossref gives pp. **805–823**, but the Royal Holloway repository lists 1165–1183. Use the Crossref value. Note also that the arXiv v1 had a different subtitle ("…with Conformal Evaluation").
10. **ECH.** draft-ietf-tls-esni has been published as **RFC 9849, "TLS Encrypted Client Hello", March 2026** (Proposed Standard). Cite the RFC, not the draft.
11. **JA3.** The Salesforce blog page shows "Jan 15" without a year. The GitHub README says JA3 was created at Salesforce in **2017** by Althouse, Atkinson and Atkins, and the repository was archived on 1 May 2025. Cite the GitHub repository with year 2017 and treat the blog post year as unconfirmed.
12. **Oh et al. (Applied Sciences 12(1):155).** Crossref gives a 2021 online date, but volume 12 is the 2022 volume. Use 2022 for consistency.
13. **Papadogiannaki & Ioannidis (ACM CSUR 54(6)).** Online July 2021, issue July 2022. Use 2022.
14. **"Learning from what we don't know" (task 2b).** No paper with this title was found. The likely intended works are Jacobs et al. CCS'22 (Trustee) and Beltiukov et al. CCS'23 (netUnicorn), which both cover shortcut learning and generalisation in network-security ML. nPrint is a different paper: Holland et al., CCS'21, "New Directions in Automated Traffic Analysis".
15. **"Lost in Translation" (task 2b).** The only match is J. Ruohonen, "Lost in Translation: Intrusion Detection Research with 'Kaggle Datasets'", a Cambridge Open Engage **working paper (May 2026, not peer reviewed)**, doi:10.33774/coe-2026-hd0xx. Cite it only with that caveat.

---

## 3. Surveys (task 2a)

| Key | Bibliographic data | Verified at |
|-----|--------------------|-------------|
| `wang2022machine` | Z. Wang, K. W. Fok, V. L. L. Thing. "Machine Learning for Encrypted Malicious Traffic Detection: Approaches, Datasets and Comparative Study." **Computers & Security** 113 (2022) 102542. doi:10.1016/j.cose.2021.102542; arXiv:2203.09332 | arXiv abs page; Crossref |
| `wang2023feature` | Z. Wang, V. L. L. Thing. "Feature Mining for Encrypted Malicious Traffic Detection with Deep Learning and Other Machine Learning Algorithms." **Computers & Security** 128 (2023) 103143. doi:10.1016/j.cose.2023.103143; arXiv:2304.03691 | arXiv abs page; Crossref |
| `shen2023machine` | M. Shen, K. Ye, X. Liu, L. Zhu, J. Kang, S. Yu, Q. Li, K. Xu. "Machine Learning-Powered Encrypted Network Traffic Analysis: A Comprehensive Survey." IEEE COMST 25(1):791–824, 2023. doi:10.1109/COMST.2022.3208196 | Crossref |
| `papadogiannaki2022survey` | E. Papadogiannaki, S. Ioannidis. "A Survey on Encrypted Network Traffic Analysis Applications, Techniques, and Countermeasures." ACM CSUR 54(6):1–35, 2022. doi:10.1145/3457904 | Crossref |
| `oh2022survey` | C. Oh, J. Ha, H. Roh. "A Survey on TLS-Encrypted Malware Network Traffic Analysis Applicable to Security Operations Centers." Applied Sciences 12(1):155, 2022. doi:10.3390/app12010155 | Crossref |
| `ji2024artificial` | I. H. Ji, J. H. Lee, M. J. Kang, W. J. Park, S. H. Jeon, J. T. Seo. "Artificial Intelligence-Based Anomaly Detection Technology over Encrypted Traffic: A Systematic Literature Review." Sensors 24(3):898, 2024. doi:10.3390/s24030898 | https://pmc.ncbi.nlm.nih.gov/articles/PMC10857182/ |
| `sharma2025survey` | A. Sharma, A. H. Lashkari. "A Survey on Encrypted Network Traffic: A Comprehensive Survey of Identification/Classification Techniques, Challenges, and Future Directions." Computer Networks 257 (2025) 110984. doi:10.1016/j.comnet.2024.110984 | Crossref |
| `zhou2024challenges` | J. Zhou, W. Fu, W. Hu, Z. Sun, T. He, Z. Zhang. "Challenges and Advances in Analyzing TLS 1.3-Encrypted Traffic: A Comprehensive Survey." Electronics 13(20):4000, 2024. doi:10.3390/electronics13204000 | Crossref |
| `abuadaiq2026encrypted` | H. Abu-Adaiq, M. I. Biswas, A. Y. Alnajjar, S. Zhang. "Encrypted-Traffic Detection in the TLS 1.3 Era: A Comprehensive Review and Future Research Directions." Electronics 15(17):3846, published 27 Aug 2026. doi:10.3390/electronics15173846 | Crossref (abstract read from the Crossref record) |
| `rahaman2026systematic` | M. Rahaman, A. Mahmud, A. A. Aziz, O. M. S. Abujawa, J.-J. Chin. "A Systematic Literature Review on Data-Efficient and Adaptive Learning Techniques for Encrypted Traffic Classification Under Modern Protocols." Computers 15(5):319, 2026. doi:10.3390/computers15050319 | Crossref |

Summaries and how our paper differs:

- **Wang, Fok & Thing 2022 (C&S).** Proposes a general ML framework for encrypted malicious-traffic detection, reviews existing techniques, merges five public sources into one dataset, and re-implements and compares 10 detection algorithms. **This is the strongest prior work against our novelty claim**: it is a review plus benchmark on encrypted malicious traffic, published in our target journal. *Difference:* it is a narrative rather than a systematic review. Its benchmark pools sources into a single dataset and, from the abstract, does not test temporal or cross-dataset generalisation, JA3/JA4 ageing, TLS 1.3 or padding robustness, cost, or label circularity. Pooling sources could even introduce the dataset-of-origin shortcut we report. We must cite it and position against it explicitly.
- **Wang & Thing 2023 (C&S).** Analyses features for encrypted malicious traffic, proposes a new feature concept and a two-layer DL+ML detector, and builds a combined dataset. *Use:* a representative "high accuracy on a pooled dataset" result to include in our coded corpus.
- **Shen et al. 2023 (COMST).** The most-cited broad survey of ML-based encrypted traffic analysis, covering asset identification, characterisation, privacy leakage and anomaly detection. It describes the pipeline from collection through representation and model to evaluation. *Difference:* malicious traffic is one sub-area, with no benchmark and no evaluation-methodology audit.
- **Papadogiannaki & Ioannidis 2022 (CSUR).** Surveys encrypted traffic analysis applications, techniques and countermeasures. *Difference:* broad, written before TLS 1.3 and ECH were widely deployed, and with no empirical component.
- **Oh, Ha & Roh 2022.** A survey of TLS-encrypted malware traffic analysis aimed at SOCs, noting that many handshake features become unavailable under TLS 1.3. *Difference:* the most topically similar earlier survey (TLS malware specifically), but narrative, with no benchmark and no drift or shortcut analysis.
- **Ji et al. 2024 (Sensors).** A PRISMA SLR of AI-based anomaly detection over encrypted traffic: 32 studies from 2019 to August 2023. It finds CTU-Malware-Captures common, RF and CNN dominant, and few studies reporting efficiency. *Difference:* an SLR with no benchmark and a broader scope (anomaly detection, any encrypted protocol). It does not audit split protocols.
- **Sharma & Lashkari 2025 (Computer Networks).** A comprehensive survey of ML/DL identification and classification techniques for encrypted traffic, with a taxonomy and dataset analysis. *Difference:* general classification, no benchmark.
- **Zhou et al. 2024 (Electronics).** Surveys how TLS 1.3 features (ECH, 0-RTT, forward secrecy) affect traffic analysis, and compiles TLS 1.3 datasets. *Use:* background for our TLS 1.3 section. It has no malicious-specific benchmark.
- **Abu-Adaiq et al. 2026 (Electronics).** A "systematic and technically grounded" review of detection under TLS 1.3 and ECH, with particular attention to malicious and C2 traffic. According to search snippets the search window is 2020–2026. It reports no experiments and states that behavioural-statistical fusion "remains empirically unvalidated". **This is a novelty threat on the review side**: a recent TLS-1.3-focused review touching malicious and C2 traffic. *Difference:* no benchmark, and the abstract mentions no PRISMA protocol. Our empirical results (TLS 1.2 to 1.3 transfer failure, padding) answer the gap it identifies.
- **Rahaman et al. 2026 (Computers).** An SLR of data-efficient learning (few-shot, self-supervised, LLM) for encrypted traffic classification under modern protocols. *Difference:* organised by learning paradigm, not malicious-specific, no benchmark.

Also found but **not verified**:
- Y. Li et al., "A Survey of Encrypted Malicious Traffic Detection", CCCI 2021, pp. 1–7, according to a DBLP listing seen via search. IEEE Xplore returned an empty page.
- K. Keshkeh et al., "A Review on TLS Encryption Malware Detection: TLS Features, Machine Learning Usage, and Future Directions", ACeS 2021 (Springer CCIS chapter 10.1007/978-981-16-8059-5_13). Not fetched.

---

## 4. Drift and shortcuts (task 2b)

| Key | Bibliographic data | Verified at |
|-----|--------------------|-------------|
| `pendlebury2019tesseract` | F. Pendlebury, F. Pierazzi, R. Jordaney, J. Kinder, L. Cavallaro. "TESSERACT: Eliminating Experimental Bias in Malware Classification across Space and Time." USENIX Security 2019, pp. 729–746. ISBN 978-1-939133-06-9 | https://www.usenix.org/conference/usenixsecurity19/presentation/pendlebury |
| `jordaney2017transcend` | R. Jordaney, K. Sharad, S. K. Dash, Z. Wang, D. Papini, I. Nouretdinov, L. Cavallaro. "Transcend: Detecting Concept Drift in Malware Classification Models." USENIX Security 2017, pp. 625–642. ISBN 978-1-931971-40-9 | https://www.usenix.org/conference/usenixsecurity17/technical-sessions/presentation/jordaney |
| `barbero2022transcending` | F. Barbero, F. Pendlebury, F. Pierazzi, L. Cavallaro. "Transcending TRANSCEND: Revisiting Malware Classification in the Presence of Concept Drift." IEEE S&P 2022, pp. 805–823. doi:10.1109/SP46214.2022.9833659; arXiv:2010.03856 | Crossref; arXiv abs page |
| `malekghaini2023deep` | N. Malekghaini, E. Akbari, M. A. Salahuddin, N. Limam, R. Boutaba, B. Mathieu, S. Moteau, S. Tuffin. "Deep Learning for Encrypted Traffic Classification in the Face of Data Drift: An Empirical Study." Computer Networks 225 (2023) 109648. doi:10.1016/j.comnet.2023.109648 | Crossref |
| `hynek2024cesnet` | K. Hynek, J. Luxemburk, J. Pešek, T. Čejka, P. Šiška. "CESNET-TLS-Year22: A Year-Spanning TLS Network Traffic Dataset from Backbone Lines." Scientific Data 11 (2024) 1156. doi:10.1038/s41597-024-03927-4 | Crossref |
| `soukup2025drift` | D. Soukup, R. Plný, D. Vašata, T. Čejka. "Drift-Based Dataset Stability Benchmark." arXiv:2512.23762 (Dec 2025), preprint | arXiv abs page |
| `li2026colossus` | B. Li, L. Meng, R. Song, C. Pan, T. Pu, Z. Ma, Y. Jiang, L. Cui, Z. Hao. "The Colossus with Feet of Clay: Debunking Encrypted Traffic Classifiers under PQC Evolution." arXiv:2608.22683 (Aug 2026), preprint | arXiv abs page |
| `holland2021new` | J. Holland, P. Schmitt, N. Feamster, P. Mittal. "New Directions in Automated Traffic Analysis" (nPrint/nPrintML). ACM CCS 2021, pp. 3366–3383. doi:10.1145/3460120.3484758 | Crossref |
| `beltiukov2023netunicorn` | R. Beltiukov, W. Guo, A. Gupta, W. Willinger. "In Search of netUnicorn: A Data-Collection Platform to Develop Generalizable ML Models for Network Security Problems." ACM CCS 2023, pp. 2217–2231. doi:10.1145/3576915.3623075; arXiv:2306.08853 | Crossref; arXiv |
| `flood2024bad` | R. Flood, G. Engelen, D. Aspinall, L. Desmet. "Bad Design Smells in Benchmark NIDS Datasets." IEEE EuroS&P 2024, pp. 658–675. The DOI was not confirmed and is omitted. IEEE Xplore document 10629000. | DBLP record seen via search; authors' preprint https://detlearsom.github.io/pubs/BadSmells-EuroSP24-finaldraft.pdf (partially verified) |
| `sharma2026split` | M. Sharma, K. Saini, D. Behl. "The Split Protocol Decides the Result: Re-Evaluating Encrypted Traffic Classification." arXiv:2611.06290 (4 Nov 2026), preprint | arXiv abs page |
| `ruohonen2026lost` | J. Ruohonen. "Lost in Translation: Intrusion Detection Research with 'Kaggle Datasets'." Cambridge Open Engage working paper, 2026. doi:10.33774/coe-2026-hd0xx | https://www.cambridge.org/engage/coe/article-details/6a106a98d1922e37d5b350ec |
| `sommer2010outside` | R. Sommer, V. Paxson. "Outside the Closed World: On Using Machine Learning for Network Intrusion Detection." IEEE S&P 2010, pp. 305–316. doi:10.1109/SP.2010.25 | Crossref |

Summaries and how we use them:
- **TESSERACT.** Shows that spatial bias (unrealistic class ratios) and temporal bias (training on future samples) inflate Android malware classifiers, and proposes time-aware splits plus the AUT metric. *Use:* our temporal-split protocol follows its constraints. We are the first to apply these constraints systematically to malicious TLS.
- **Transcend / Transcending Transcend.** Conformal-evaluation-based detection of drifting samples so that models can abstain or be retrained. *Use:* the drift-detection or rejection baseline to mention as mitigation. We measure drift rather than propose a rejector.
- **Malekghaini et al. 2023.** Shows that DL encrypted traffic classifiers degrade on ISP data collected over more than two years, and proposes architectural mitigations. *Use:* evidence of temporal decay for benign app classification. We show the same for malicious TLS.
- **CESNET-TLS-Year22.** A year-long backbone TLS dataset (180 services) built for time-aware evaluation. *Use:* a possible benign temporal source and an example of good dataset practice. It contains no malware labels.
- **Soukup et al. 2025.** A drift-based dataset-stability benchmark demonstrated on CESNET-TLS-Year22. *Use:* related methodology. It is benign-only and a preprint.
- **Li et al. 2026 (Colossus).** Hybrid post-quantum key exchange (X25519MLKEM768) in TLS 1.3 causes "protocol drift" that breaks HTTPS website-fingerprinting classifiers across domains. *Use:* supports our point that protocol evolution breaks models trained on older traffic. Its subject is website fingerprinting, not malware.
- **nPrint (Holland et al.).** A unified bit-level packet representation plus AutoML. *Use:* nPrint-style raw representations are prone to learning header shortcuts (TTL, IP, timestamps). Cited when discussing which features leak dataset of origin.
- **netUnicorn.** Explainability-guided iterative data collection for generalisable network-security models, which shows that models trained in one environment fail in another. *Use:* supports our cross-dataset collapse finding and the need for multi-environment data.
- **Flood et al. 2024.** Finds six "data design smells" in seven benchmark NIDS datasets, including labels leaked through features and near-duplicates. *Use:* supports our dataset-of-origin and label-circularity findings for the non-TLS-specific datasets.
- **Sharma, Saini & Behl 2026.** Macro-F1 falls from 0.992 to 0.567 when captures are kept disjoint. A tree trained on the capture ID alone scores 0.983 under random split. Temporal splits on QUIC backbone data did *not* hurt. *Use:* strong support for our capture-disjoint and dataset-of-origin argument. Its "temporal split does not hurt" result on benign QUIC is a useful contrast with our malicious-TLS finding that temporal splits collapse. This needs to be discussed, not ignored.
- **Ruohonen 2026.** A working paper on provenance problems with Kaggle-hosted IDS datasets. Cite only as a non-peer-reviewed working paper.
- **Sommer & Paxson 2010.** The classic argument for why ML-based NIDS struggle in practice: closed-world assumption, cost of errors, semantic gap. *Use:* framing in the introduction.

---

## 5. TLS / fingerprinting background (task 2c)

| Key | Bibliographic data | Verified at |
|-----|--------------------|-------------|
| `rfc8446` | E. Rescorla. "The Transport Layer Security (TLS) Protocol Version 1.3." RFC 8446, IETF, August 2018. doi:10.17487/RFC8446 | https://datatracker.ietf.org/doc/html/rfc8446 (seen in search; record padding is in §5.4) |
| `rfc9849` | E. Rescorla, K. Oku, N. Sullivan, C. A. Wood. "TLS Encrypted Client Hello." RFC 9849, IETF, March 2026 (Proposed Standard; previously draft-ietf-tls-esni, last version -25) | https://datatracker.ietf.org/doc/draft-ietf-tls-esni/ |
| `althouse2017ja3` | J. Althouse, J. Atkinson, J. Atkins. JA3, Salesforce, 2017. https://github.com/salesforce/ja3 (archived 1 May 2025). Blog: J. Althouse, "TLS Fingerprinting with JA3 and JA3S", Salesforce Engineering (the year is not shown on the page) | https://github.com/salesforce/ja3 ; https://engineering.salesforce.com/tls-fingerprinting-with-ja3-and-ja3s-247362855967/ |
| `althouse2023ja4` | J. Althouse. "JA4+ Network Fingerprinting." FoxIO blog, 26 Sep 2023 (date from the byline). JA4 is BSD-3 licensed; the other JA4+ methods use the FoxIO License 1.1. | https://foxio.io/blog/ja4-network-fingerprinting ; https://github.com/FoxIO-LLC/ja4 |
| `foote2023chrome` | J. Foote, A. Kumar, W. Woodson (Fastly). "A First Look at Chrome's TLS ClientHello Permutation in the Wild." Fastly blog, 8 Feb 2023 | https://www.fastly.com/blog/a-first-look-at-chromes-tls-clienthello-permutation-in-the-wild |
| `shamsimukhametov2022ech` | D. Shamsimukhametov, A. Kurapov, M. Liubogoshchev, E. Khorov. "Is Encrypted ClientHello a Challenge for Traffic Classification?" IEEE Access 10:77883–77897, 2022. doi:10.1109/ACCESS.2022.3191431 | Crossref |
| `matousek2024experience` | P. Matoušek, O. Ryšavý, I. Burgetová. "Experience Report: Using JA4+ Fingerprints for Malware Detection in Encrypted Traffic." CNSM 2024 (20th Int. Conf. on Network and Service Management), IFIP. Pages and DOI not confirmed. | https://opendl.ifip-tc6.org/db/conf/cnsm/cnsm2024/1571045669.pdf (first page read) |
| `polopeyres2026detecting` | E. Polo-Peyres, J. E. López de Vergara, G. Sutter, I. González, L. de Pedro. "Detecting Malware in Encrypted Network Traffic Using Machine Learning and TLS Fingerprints." UCAmI 2025, Vol. 2, LNNS, Springer, 2026, pp. 331–342. doi:10.1007/978-3-032-16995-2_29 | Crossref |

Summaries:
- **RFC 8446.** TLS 1.3 encrypts everything after ServerHello, including the certificate, hides the record content type, and allows record padding (§5.4). *Use:* the protocol basis for why TLS 1.2 certificate and handshake features disappear, and the padding threat we evaluate.
- **RFC 9849 (ECH).** Encrypts the inner ClientHello (SNI, ALPN and others) under a public outer ClientHello. *Use:* defines what an "ECH-surviving" feature set is: size and timing, not SNI or the inner ClientHello. Now a published RFC.
- **JA3.** An MD5 hash of the ClientHello version, ciphers, extensions, curves and point formats. The creators caution that hashes collide across software. *Use:* the baseline fingerprint feature whose ageing we measure.
- **JA4+.** The successor to JA3. It sorts extensions and ciphers to survive Chrome's permutation and cipher stunting, and adds JA4S, JA4X, JA4H and others. *Use:* the modern fingerprint baseline. Our result that hashes age badly applies to JA4 too.
- **Fastly 2023.** Measures Chrome's ClientHello extension permutation (planned for Chrome 110, visible from 108/109; around 15! orderings), which gives a new JA3 per connection. The share of the dominant Chrome JA3 dropped from 20 Jan 2023. *Use:* a concrete cause of JA3 drift in benign traffic. Benign-side drift produces false positives in JA3-based models.
- **Shamsimukhametov et al. 2022.** Shows that state-of-the-art traffic classifiers degrade significantly once ECH hides the inner ClientHello, and proposes ECH-robust classifiers. *Use:* evidence that ClientHello-dependent features lose value under ECH. It covers application classification.
- **Matoušek et al. 2024.** Measures coverage and uniqueness of JA4/JA4S/JA4X fingerprints for malware vs benign apps. Malware families share fingerprints. *Use:* single-snapshot evidence of the limits of JA4. We add the temporal dimension.
- **Polo-Peyres et al. 2026.** Compares statistical flow features with JA4+ fingerprints for ML malware detection. This comes from a search snippet; the abstract was not read in full. *Use:* include in the coded corpus.

Related TLS 1.3/ECH impact work, **not verified** in detail: Shamsimukhametov et al., "Early Traffic Classification with Encrypted ClientHello: a Multi-Country Study", IEEE Access 2024, doi:10.1109/ACCESS.2024.3469730 (DOI seen in search only); Merlach, Trevisan, Giordano, passive ECH adoption measurement, NETWORK 2025 (polito repository); Mücke et al., ECH deployment mapping, SIGCOMM 2025 Posters, doi:10.1145/3744969.3748401 (search only).

---

## 6. Base rate (task 2d)

| Key | Bibliographic data | Verified at |
|-----|--------------------|-------------|
| `axelsson2000base` | S. Axelsson. "The Base-Rate Fallacy and the Difficulty of Intrusion Detection." ACM TISSEC 3(3):186–205, 2000. doi:10.1145/357830.357849 | https://api.crossref.org/works/10.1145/357830.357849 |

Summary: applies Bayes' theorem to show that, because intrusions are rare, a detector needs an extremely low false-positive rate for its alarms to be mostly true positives. *Use:* justifies reporting precision at realistic prevalence and FPR at low operating points, not balanced accuracy. An earlier version appeared at ACM CCS 1999 ("The Base-Rate Fallacy and its Implications for the Difficulty of Intrusion Detection", per a CERIAS record seen in search). That record was not verified, so cite the TISSEC 2000 version.

---

## 7. Novelty threats (task 2e)

Claim under test: "first systematic review + benchmark specific to malicious TLS detection".

**Assessment:** the claim as worded is **at risk**. Wang, Fok & Thing (2022), in *Computers & Security* itself, is a review plus a 10-algorithm comparative benchmark on encrypted malicious traffic. It can be defended only if narrowed to *systematic* (protocol-driven, PRISMA-style) review **plus** a *generalisation-focused* benchmark (temporal, cross-dataset, TLS 1.2→1.3, padding, cost, shortcut and label audits) specific to *malicious TLS*. Suggested rewording: "To our knowledge, this is the first systematic review of ML-based malicious-TLS detection paired with a benchmark that evaluates generalisation across time, datasets and TLS versions, rather than within a pooled random split."

Ranked threats:
1. **Wang, Fok, Thing 2022, C&S 113:102542 (`wang2022machine`).** Review + framework + combined 5-source dataset + 10 re-implemented algorithms on encrypted malicious traffic. *Highest threat.* Our differences: systematic protocol; TLS-specific; temporal and cross-dataset evaluation (theirs pools data); TLS 1.3, padding and ECH; JA3/JA4 ageing; cost; label circularity.
2. **Wickramasinghe et al., S&P 2025 (`wickramasinghe2025sok`).** SoK + large-scale occlusion experiments on encrypted traffic classifiers. Our difference: they cover application/service classification; we cover malicious detection with temporal, cross-dataset and TLS-version shifts.
3. **Abu-Adaiq et al., Electronics 2026 (`abuadaiq2026encrypted`).** A "systematic" review of TLS 1.3/ECH-era detection with attention to malicious and C2 traffic. Our difference: no benchmark, no PRISMA mentioned in the abstract. Our experiments supply the empirical validation it says is missing.
4. **Ji et al., Sensors 2024 (`ji2024artificial`).** A PRISMA SLR (32 papers) on AI anomaly detection over encrypted traffic. Our difference: no benchmark, broader protocol scope, ends Aug 2023.
5. **Oh, Ha, Roh, Appl. Sci. 2022 (`oh2022survey`).** A TLS-malware-specific survey. Our difference: narrative, no benchmark.
6. **Nguyen-Huu, Phan, Nguyen-An 2026, arXiv:2609.27311 (`nguyenhuu2026multiview`, ASIANComNet 2026).** A leakage-controlled measurement study of evaluation pitfalls in encrypted C2 detection on 17,577 TLS flows from 62 Cobalt Strike captures. It finds that frequency encoding before the split inflates F1 by 0.28, that endpoint-dependent labels leave only 2,132 independent groups, and that 32% of captures have no TLS flows to known C2 addresses. **Closest in spirit to our empirical findings** (leakage, labels tied to destination, i.e. circularity). Our difference: one malware family, one data source, no systematic review, and no temporal or TLS-version analysis.
7. **Evaluation-protocol critiques of generic ETC:** Zhao et al. SIGCOMM'25, Yu et al. 2026, Sharma et al. 2026 (arXiv:2611.06290), Huang & Yang 2026. Each covers part of our "random split / shortcut / label provenance" story for *benign* encrypted traffic. None, by their abstracts, covers malware/C2/DoH-tunnel detection, blocklist labels, JA3/JA4 ageing or TLS 1.3 padding. Our paper should cite them as concurrent evidence that the problem is general, and claim the malicious-TLS-specific measurement.
8. **Barradas et al. RAID'24 and Kanda et al. JIP'25.** Primary studies that partly anticipate two of our findings: TLS 1.2→1.3 transfer, which they find *works* while padding is left out of scope, and TLS parameter drift, measured without the ML consequence. These are not review-plus-benchmark papers, but our TLS 1.3 and JA3/JA4 claims must be framed relative to them.

Searched with no further threat found: arXiv 2025–2026 for SoK, benchmark or systematic review on malicious TLS, encrypted C2, DoH tunnelling or HTTPS attacks; JA3/JA4 longitudinal ML studies; TLS 1.3 padding evasion of C2 classifiers (only Barradas'24 discusses it, and it is out of scope there). Other relevant primary works found: MalMoE (INFOCOM 2026, drift-aware encrypted malicious detection), Striking Back at Cobalt (arXiv 2506.08922), Novo & Morla AISec'20 (proxy-based evasion of flow-based C2 detectors). These are listed below.

| Key | Bibliographic data | Verified at | Summary / use |
|-----|--------------------|-------------|---------------|
| `nguyenhuu2026multiview` | H.-H. Nguyen-Huu, V.-T. Phan, K. Nguyen-An. "Multi-View Fusion for Encrypted C2 Detection: A Leakage-Controlled Measurement Study of Evaluation Pitfalls." arXiv:2609.27311 (23 Sep 2026). Accepted at ASIANComNet 2026 per arXiv comments. | https://arxiv.org/abs/2609.27311 | See threat 6. Cite as concurrent evidence of leakage and label-dependence in C2 detection. |
| `tan2026malmoe` | Y. Tan, Q. Li, M. Yang, Y. Hu, L. Zhang, X. Zhang. "MalMoE: Mixture-of-Experts Enhanced Encrypted Malicious Traffic Detection Under Graph Drift." IEEE INFOCOM 2026 (per arXiv comments); arXiv:2602.10157. Pages and DOI not confirmed. | https://arxiv.org/abs/2602.10157 | Graph-based MoE detector designed for "graph drift". Use as an example of drift-aware detection in the corpus. |
| `parssegny2025striking` | C. Parssegny, J. Mazel, O. Levillain, P. Chifflier. "Striking Back At Cobalt: Using Network Traffic Metadata To Detect Cobalt Strike Masquerading Command and Control Channels." arXiv:2506.08922 (2025), preprint. | https://arxiv.org/abs/2506.08922 | Metadata-only, traffic-adaptive Cobalt Strike C2 detection. Include in the corpus. |
| `novo2020flow` | C. Novo, R. Morla. "Flow-based Detection and Proxy-based Evasion of Encrypted Malware C2 Traffic." AISec 2020, ACM, pp. 83–91. doi:10.1145/3411508.3421379; arXiv:2009.01122 | Crossref; arXiv | Realistic (proxy-crafted) evasion of flow-feature C2 detectors. Prior evidence for our padding and evasion robustness result. |

---

## 8. Unverified / uncertain

- **Y. Li, H. Guo, J. Hou, Z. Zhang, T. Jiang, Z. Liu, "A Survey of Encrypted Malicious Traffic Detection", CCCI 2021, pp. 1–7.** Seen only via a DBLP listing in search results. The IEEE Xplore page (document 9583191) returned empty, so the publisher and DOI are not confirmed.
- **K. Keshkeh, A. Jantan, K. Alieyan, U. M. Gana, "A Review on TLS Encryption Malware Detection: TLS Features, Machine Learning Usage, and Future Directions", ACeS 2021 (Springer chapter, doi prefix 10.1007/978-981-16-8059-5_13).** Not fetched, so pages and series are unverified.
- **Shamsimukhametov et al., "Early Traffic Classification with Encrypted ClientHello: a Multi-Country Study", IEEE Access 2024, doi:10.1109/ACCESS.2024.3469730.** DOI seen in search only.
- **Merlach, Trevisan, Giordano, passive ECH and HTTPS-RR adoption study, NETWORK 2025.** polito repository via search only. The title and venue details were not confirmed.
- **Mücke, Gasser, Schmidt, Wählisch, ECH deployment mapping, SIGCOMM 2025 Posters & Demos, doi:10.1145/3744969.3748401.** Search only.
- **Flood et al. EuroS&P 2024 DOI.** Not confirmed and omitted from the .bib. The bibliographic fields come from DBLP via search and the authors' preprint. Fetch IEEE Xplore 10629000 to add the DOI.
- **"Error Prevalence in NIDS datasets: A Case Study on CIC-IDS-2017 and CSE-CIC-IDS-2018" (Lanvin et al., 2022).** Title seen in search only.
- **RFC 8701 (GREASE).** Not fetched. Add it only after checking rfc-editor.org.
- **Axelsson CCS 1999 conference version.** CERIAS record only.
- **JA3 blog post year.** Not shown on the page.
- **"Learning from what we don't know".** No such paper found (see Corrections, item 14).
- **Anderson & McGrew 2016 arXiv/Cisco TLS paper "Deciphering..." arXiv:1607.01639.** The arXiv ID was seen in search results; the JCVHT journal version is verified.
- **Wang, Fok, Thing 2022 benchmark details.** Whether it uses random splits and how it pools sources is inferred from the abstract only. Read the paper before writing the positioning sentence.
