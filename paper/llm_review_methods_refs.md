# References for the LLM-assisted review methods section

Checked on 2026-11-09 against Crossref (api.crossref.org/works/<doi>), Europe PMC REST records (for abstracts and BMJ volume numbers), arXiv abstract pages, and the OSF API. Summaries come from the abstracts in those records. BibTeX for every verified item is in `llm_review_methods_refs.bib`.

Support tags: **[SCREEN]** screening suggestions, **[EXTRACT]** data extraction, **[DISAGREE]** disagreement-based human review, **[HITL]** human in the loop, **[REPORT]** reporting and responsible-use guidance, **[PRIOR]** earlier automation work.

---

## A. LLM-assisted title/abstract screening

### khraisha2024can
Khraisha Q, Put S, Kappenberg J, Warraitch A, Hadfield K. Can large language models replace humans in systematic reviews? Evaluating GPT-4's efficacy in screening and extracting data from peer-reviewed and grey literature in multiple languages. *Research Synthesis Methods*. 2024;15(4):616-626. doi:10.1002/jrsm.1715
- Verified at: https://api.crossref.org/works/10.1002/jrsm.1715
- Finding: In a pre-registered study, GPT-4 was tested on title/abstract screening, full-text screening and data extraction. Its reliability ranged from none to moderate depending on dataset balance, and data extraction was moderate. Full-text screening came close to human performance only with highly reliable prompts. The authors urge "substantial caution".
- Support: **[SCREEN][EXTRACT][HITL]** Explains why we used the LLM to *suggest* decisions and did not let it replace human reviewers.

### guo2024automated
Guo E, Gupta M, Deng J, Park Y-J, Paget M, Naugler C. Automated Paper Screening for Clinical Reviews Using Large Language Models: Data Analysis Study. *Journal of Medical Internet Research*. 2024;26:e48996. doi:10.2196/48996
- Verified at: https://api.crossref.org/works/10.2196/48996
- Finding: GPT-4 screened more than 24,000 records from six reviews. Accuracy was 0.91 and sensitivity for included papers was 0.76. Agreement with consensus human decisions was high (PABAK 0.96), higher than agreement between the two human screeners (kappa 0.46). The authors recommend LLMs as an aid to researchers, not a replacement.
- Support: **[SCREEN][HITL]** Shows that LLM screening is feasible, and its imperfect sensitivity justifies human confirmation of every suggested exclusion.

### tran2024sensitivity
Tran V-T, Gartlehner G, Yaacoub S, Boutron I, Schwingshackl L, Stadelmaier J, Sommer I, Alebouyeh F, Afach S, Meerpohl J, Ravaud P. Sensitivity and Specificity of Using GPT-3.5 Turbo Models for Title and Abstract Screening in Systematic Reviews and Meta-analyses. *Annals of Internal Medicine*. 2024;177(6):791-799. doi:10.7326/M23-3389
- Verified at: https://api.crossref.org/works/10.7326/M23-3389 (abstract via Europe PMC REST search on the DOI)
- Finding: The study covered 22,665 citations from five reviews. Under a "sensitive" rule, sensitivity was 94.6-99.8% but specificity only 2.2-46.6%. Restricting human screening to the records GPT did not rule out would have missed 0-1 of 26 full-text-eligible citations. The authors conclude that the model "may be used as a second reviewer".
- Support: **[SCREEN]** Directly supports using an LLM to flag likely exclusions so that humans can prioritise their screening.

### syriani2024screening
Syriani E, David I, Kumar G. Screening articles for systematic reviews with ChatGPT. *Journal of Computer Languages*. 2024;80:101287. doi:10.1016/j.cola.2024.101287 (preprint: arXiv:2307.06464)
- Verified at: https://api.crossref.org/works/10.1016/j.cola.2024.101287 and https://arxiv.org/abs/2307.06464
- Finding: This software-engineering study measured ChatGPT's consistency, classification performance and generalisability for SR screening and compared it with traditional SR-automation classifiers. It concludes that ChatGPT is a viable option for automating screening, but that it must be integrated into SR tools with care.
- Support: **[SCREEN]** Software-engineering evidence that LLM screening is viable, which matters for a computing-domain review.

### huotala2024promise
Huotala A, Kuutila M, Ralph P, Mäntylä M. The Promise and Challenges of Using LLMs to Accelerate the Screening Process of Systematic Reviews. In: *Proceedings of the 28th International Conference on Evaluation and Assessment in Software Engineering (EASE 2024)*. ACM; 2024:262-271. doi:10.1145/3661167.3661172
- Verified at: https://api.crossref.org/works?query.bibliographic=... (Crossref record, DOI 10.1145/3661167.3661172) and https://arxiv.org/abs/2404.15667
- Finding: The study compared GPT-3.5 and GPT-4 with human screeners on software-engineering abstracts. GPT-4 beat GPT-3.5, and one-shot and few-shot prompting beat zero-shot. Some model-prompt combinations matched humans, but LLMs were not significantly more accurate than humans.
- Support: **[SCREEN][HITL]** A software-engineering venue paper backing LLM screening *assistance* with humans still deciding.

### lieberum2025large
Lieberum J-L, Toews M, Metzendorf M-I, Heilmeyer F, Siemens W, Haverkamp C, Böhringer D, Meerpohl JJ, Eisele-Metzger A. Large language models for conducting systematic reviews: on the rise, but not yet ready for use—a scoping review. *Journal of Clinical Epidemiology*. 2025;181:111746. doi:10.1016/j.jclinepi.2025.111746
- Verified at: https://api.crossref.org/works/10.1016/j.jclinepi.2025.111746 (abstract via Europe PMC)
- Finding: The review included 37 studies. LLMs were applied to 10 of 13 SR steps, most often search (41%), study selection (38%) and data extraction (30%). Of the studies, 54% rated LLMs as promising, but "fully established or validated applications are often lacking".
- Support: **[SCREEN][EXTRACT][HITL]** Overview showing that LLM use is growing but not validated enough to run unsupervised.

## B. LLM-based data extraction (accuracy, errors, hallucination)

### gartlehner2024data
Gartlehner G, Kahwati L, Hilscher R, Thomas I, Kugley S, Crotty K, Viswanathan M, Nussbaumer-Streit B, Booth G, Erskine N, Konet A, Chew R. Data extraction for evidence synthesis using a large language model: A proof-of-concept study. *Research Synthesis Methods*. 2024;15(4):576-589. doi:10.1002/jrsm.1710
- Verified at: https://api.crossref.org/works/10.1002/jrsm.1710
- Finding: Claude 2 extracted 160 data elements from 10 RCTs with 96.3% accuracy, and results were consistent across replications. It made six errors, mostly missed items.
- Support: **[EXTRACT]** Shows that LLM full-text extraction can be accurate, while the remaining errors (often omissions) justify human checking.

### konet2024performance
Konet A, Thomas I, Gartlehner G, Kahwati L, Hilscher R, Kugley S, Crotty K, Viswanathan M, Chew R. Performance of two large language models for data extraction in evidence synthesis. *Research Synthesis Methods*. 2024;15(5):818-824. doi:10.1002/jrsm.1732
- Verified at: https://api.crossref.org/works/10.1002/jrsm.1732
- Finding: Claude 2 reached 96.3% accuracy. GPT-4 with a PDF plugin reached only 68.8%, mostly because of PDF-parsing errors. When given selected text, accuracy rose to 98.7% and 100%. The authors conclude that human validation remains essential.
- Support: **[EXTRACT][HITL]** Shows that accuracy differs between models and depends on the input pipeline, which motivates using two models and human validation.

### gartlehner2025artificial
Gartlehner G, Kugley S, Crotty K, Viswanathan M, Dobrescu A, Nussbaumer-Streit B, Booth G, Treadwell JR, Han JM, Wagner J, Apaydin EA, Coppola EL, Maglione M, Hilscher R, Chew R, Pilar M, Swanton B, Kahwati LC. Artificial Intelligence–Assisted Data Extraction With a Large Language Model: A Study Within Reviews. *Annals of Internal Medicine*. 2025;178(12):1763-1771. doi:10.7326/ANNALS-25-00739 (preprint: medRxiv doi:10.1101/2025.03.20.25324350)
- Verified at: Crossref bibliographic query (DOI 10.7326/annals-25-00739); abstract via Europe PMC REST search on the DOI
- Finding: The study covered six reviews, 63 studies and 9,341 data elements. AI-assisted extraction (LLM extraction followed by human verification) reached 91.0% accuracy versus 89.0% for human-only extraction. Major errors were 2.5% versus 2.7%, and the AI-assisted method saved a median of 41 minutes per study.
- Support: **[EXTRACT][HITL]** The strongest evidence that LLM extraction *with human verification* is at least as accurate as human-only extraction.

### khan2025collaborative
Khan MA, Ayub U, Naqvi SAA, Khakwani KZR, Sipra ZbR, Raina A, Zhou S, He H, Saeidi A, Hasan B, Rumble RB, Bitterman DS, Warner JL, Zou J, Tevaarwerk AJ, Leventakos K, Kehl KL, Palmer JM, Murad MH, Baral C, Riaz Ib. Collaborative large language models for automated data extraction in living systematic reviews. *Journal of the American Medical Informatics Association*. 2025;32(4):638-647. doi:10.1093/jamia/ocae325
- Verified at: https://api.crossref.org/works/10.1093/jamia/ocae325
- Finding: GPT-4-turbo and Claude-3-Opus were arranged to mimic two independent human reviewers. Values on which the two models agreed were highly accurate (0.94 on the test set). Disagreements had low accuracy (0.41-0.50), which rose to 0.76 after cross-critique.
- Support: **[DISAGREE]** Direct evidence for our design: two-model agreement marks reliable values, and disagreements identify the items that need human review.

### ji2023survey
Ji Z, Lee N, Frieske R, Yu T, Su D, Xu Y, Ishii E, Bang YJ, Madotto A, Fung P. Survey of Hallucination in Natural Language Generation. *ACM Computing Surveys*. 2023;55(12):1-38. doi:10.1145/3571730
- Verified at: https://api.crossref.org/works/10.1145/3571730
- Finding: A survey that defines and categorises hallucination in neural text generation (content that is unfaithful to the source or not supported by it).
- Support: **[EXTRACT][HITL]** A general citation for hallucination risk, which motivates checking extracted values against the source text.

## C. Responsible AI use and reporting guidance

### flemyng2025position
Flemyng E, Noel-Storr A, Macura B, Gartlehner G, Thomas J, Meerpohl JJ, Jordan Z, Minx J, Eisele-Metzger A, Hamel C, Jemioło P, Porritt K, Grainger M. Position statement on artificial intelligence (AI) use in evidence synthesis across Cochrane, the Campbell Collaboration, JBI and the Collaboration for Environmental Evidence 2025. *Environmental Evidence*. 2025;14(1):20. doi:10.1186/s13750-025-00374-5
- Verified at: https://api.crossref.org/works/10.1186/s13750-025-00374-5
- Finding: A joint statement from the four organisations, co-published in their journals. Reviewers may use AI if they can show it does not compromise methodological rigour. Human oversight is required, authors remain accountable, AI use that makes or suggests judgements must be reported in full, and the statement endorses RAISE.
  - Caveat: the substance comes from search snippets and organisational news pages, because the PMC full text was not reachable. Check the wording before quoting it.
  - The co-publication DOIs in CDSR, Campbell Systematic Reviews and JBI Evidence Synthesis were not verified, so cite the Environmental Evidence version.
- Support: **[REPORT][HITL]** Authoritative guidance requiring human oversight and transparent reporting of AI-assisted screening and extraction.

### raise_osf (partially verified)
Responsible use of AI in evidence SynthEsis (RAISE): recommendations and guidance. Open Science Framework project. https://osf.io/fwaud/
- Verified at: https://api.osf.io/v2/nodes/fwaud/
  - Confirmed: the title, that the project is public, its creation date (2024-08-29) and that it is still being updated (last modified 2026-09).
  - Not confirmed: the author list and a version number, so neither is in the BibTeX entry.
- Finding: A three-part guidance. RAISE 1 gives recommendations for eight roles in the evidence-synthesis ecosystem, RAISE 2 covers building and evaluating tools, and RAISE 3 covers selecting and using tools. It asks reviewers to remain ultimately responsible and to report AI use transparently.
- Support: **[REPORT][HITL]** The framework the position statement endorses. Cite it together with flemyng2025position.

### page2021prisma
Page MJ, McKenzie JE, Bossuyt PM, et al. (26 authors). The PRISMA 2020 statement: an updated guideline for reporting systematic reviews. *BMJ*. 2021;372:n71. doi:10.1136/bmj.n71
- Verified at: https://api.crossref.org/works/10.1136/bmj.n71 (volume 372 via Europe PMC, PMID 33782057); checklist wording via Europe PMC full text of PMC8005924
- Finding: Checklist items 8 (selection process) and 9 (data collection process) ask authors to report, "if applicable, details of automation tools used in the process".
- Support: **[REPORT]** Requires us to report the LLM tools used in screening and extraction.

### page2021prismaee
Page MJ, Moher D, Bossuyt PM, et al. (26 authors). PRISMA 2020 explanation and elaboration: updated guidance and exemplars for reporting systematic reviews. *BMJ*. 2021;372:n160. doi:10.1136/bmj.n160
- Verified at: https://api.crossref.org/works/10.1136/bmj.n160 (volume via Europe PMC, PMID 33781993)
- Finding: Gives the detailed guidance and examples for each PRISMA 2020 item, including items 8 and 9.
- Support: **[REPORT]** A companion citation for how to report automation tools.

## D. Human-in-the-loop machine learning

### mosqueirarey2023human
Mosqueira-Rey E, Hernández-Pereira E, Alonso-Ríos D, Bobes-Bascarán J, Fernández-Leal Á. Human-in-the-loop machine learning: a state of the art. *Artificial Intelligence Review*. 2023;56(4):3005-3054. doi:10.1007/s10462-022-10246-w (online 2022)
- Verified at: https://api.crossref.org/works/10.1007/s10462-022-10246-w
- Finding: Reviews and defines the forms of human-ML collaboration: active learning, interactive ML, machine teaching, curriculum learning and explainable AI.
- Support: **[HITL]** Conceptual grounding for a pipeline in which humans keep control of the final decisions.

### wu2022survey
Wu X, Xiao L, Sun Y, Zhang J, Ma T, He L. A survey of human-in-the-loop for machine learning. *Future Generation Computer Systems*. 2022;135:364-381. doi:10.1016/j.future.2022.05.014
- Verified at: https://api.crossref.org/works/10.1016/j.future.2022.05.014
- Finding: A survey of methods that bring human knowledge and feedback into ML pipelines. Crossref had no abstract, so this summary is based on the title and scope.
- Support: **[HITL]** A second general citation for human-in-the-loop ML.

## E. Earlier systematic-review automation

### marshall2019toward
Marshall IJ, Wallace BC. Toward systematic review automation: a practical guide to using machine learning tools in research synthesis. *Systematic Reviews*. 2019;8(1):163. doi:10.1186/s13643-019-1074-9
- Verified at: https://api.crossref.org/works/10.1186/s13643-019-1074-9 (abstract via Europe PMC)
- Finding: A practical guide to machine-learning methods for search, screening and data extraction. It covers which methods are ready for use, along with their strengths and weaknesses.
- Support: **[PRIOR]** Places LLM assistance within the established line of work on SR automation.

### omaraeves2015using
O'Mara-Eves A, Thomas J, McNaught J, Miwa M, Ananiadou S. Using text mining for study identification in systematic reviews: a systematic review of current approaches. *Systematic Reviews*. 2015;4(1):5. doi:10.1186/2046-4053-4-5
- Verified at: https://api.crossref.org/works/10.1186/2046-4053-4-5 (abstract via Europe PMC)
- Finding: Text mining typically saved 30-70% of screening workload, sometimes at the cost of missing about 5% of relevant studies (95% recall). Ranking records is safe, and using text mining as a second screener is acceptable with caution. Automatic exclusion was "promising but not yet fully proven".
- Support: **[PRIOR][SCREEN]** A precedent for treating machine exclusions as suggestions that humans confirm, rather than as automatic decisions.

---

## Rejected or unverifiable candidates

- **"Syriani et al. (ChatGPT screening)" as an arXiv-only item**: not rejected. It was published in J. Comput. Lang. 2024 (see syriani2024screening), so cite the journal version, not arXiv:2307.06464.
- **RAISE as a formal journal publication**: not found. One secondary source said a RAISE paper had been submitted to *Research Synthesis Methods*, but no published DOI was confirmed. Cite the OSF project together with the position statement.
- **Co-published versions of the position statement** (Cochrane Database of Systematic Reviews, Campbell Systematic Reviews, JBI Evidence Synthesis): exist according to news and search results, but their DOIs and bibliographic fields were not verified. Omitted.
- **Felizardo et al. 2024 (ChatGPT-4o data extraction for SE mapping studies; ChatGPT screening replication)**: found only through secondary pages, and the venue and DOI were not confirmed. Omitted.
- **Psychological Bulletin 2025 (eight LLMs vs. human extraction across 22 reviews)** and **Cochrane Evidence Synthesis and Methods 2025 (Elicit on 20 RCTs)**: these appeared in search snippets only. They were not verified, so they are not cited.
