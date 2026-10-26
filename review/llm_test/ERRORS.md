# Error analysis: Gemini 3.1 Flash Lite, grouped + schema + check (round 4)

All wrong/partial answers from the 9 checked runs and 9 drafts (3 papers × 3 runs), each checked against the paper text (26 Oct 2026). 10 distinct errors.

## Summary

| Cause | Distinct errors | Preventable? |
|---|---|---|
| **Reference coding or grading wrong/too narrow** (model was right) | 4 | Fix the reference (needs your confirmation) |
| **Ambiguous field definition** (defensible either way) | 3 | Yes: sharpen definitions |
| **Genuine reading error** | 2 | Mostly: one targeted hint; one is check-pass behaviour |
| **Hallucinated content** (value with no basis in the paper) | **0** | — |
| Non-verbatim "quotes" (alongside correct or defensible values) | 4 instances | Yes: forbid splicing; flag low quote match |

No answer was invented: every value traces to something the paper says. The real failure modes are misreading which part of the paper an answer applies to, ambiguous definitions, and "quotes" that are spliced or paraphrased.

## Details

### Model right, reference/grading wrong (4)
| Paper | Field | Model | Paper text | Verdict |
|---|---|---|---|---|
| P03 Gomez | temporal | yes | Sandbox training data Nov 2017–Oct 2019, research-network test data Oct 2019–Oct 2020; "To evaluate degradation over time, we then apply the detector again on almost four months of benign traffic" | Model right; reference said unclear/no |
| P02 Kanda | metrics | + "average occurrence-based precision" | "Figure 4 shows the average occurrence-based precision" | Model right; reference too narrow |
| P03 Gomez | first_n_packets | "6 sequences" | "we consider the first three RRPs, analyzing a total of six sequences" | Same thing as "3 RRPs"; grader too strict |
| P02 Kanda | granularity | packet (6/6 runs) | Analysis unit is "155,047 TLS Client Hello packets" | Defensible; reference only allowed flow/session |

### Ambiguous definitions (3)
| Paper | Field | Model | Why it's ambiguous | Fix |
|---|---|---|---|---|
| P01 RAID | ech_considered | no (1 of 3 runs) | Threat model assumes "TLS 1.3 with ECH", but ECH traffic is never simulated | Define: yes if the threat model or features assume ECH-hidden fields |
| P01 RAID | label_source | + sandbox | MTA captures come from sandbox runs, but malicious flows were picked by SSLBL certificates | Define: the signal that decides malicious vs benign, not where the traffic came from |
| P03 Gomez | host_grouped | yes | One experiment splits by trace (one trace per sample); another samples 90% of flows at random | Define: answer for the main detection experiment |

### Genuine reading errors (2)
| Paper | Field | Model | Cause | Fix |
|---|---|---|---|---|
| P01 RAID | feature_groups (+G3), visibility tier (tls13) | draft run 1 only; **corrected by the check** | Read the feature-extraction paragraph listing ClientHello fields, which continues "These are not used for classification, but rather to identify and filter out flows" | Hint: count only features fed to the classifier, not fields used for filtering or labelling |
| P03 Gomez | split_protocol = random | checked run 3 only; **introduced by the check** | Took the 10-fold false-negative experiment (90% random flows per cluster) as the main evaluation | Tell the checker to change a value only when a verbatim quote contradicts it; define "main experiment" |

### Non-verbatim quotes (4 instances)
- P03 temporal: "The sandbox dataset includes traffic from 2017-2019 and the research network traffic includes traffic from 2019-2020" is **not in the paper**; it's a summary of table dates (quote match 0.41). The claim is true, the quote is made up.
- P01 label_source, P03 host_grouped: several real sentences joined with "..." (quote match 0.35, 0.64); the second joins two different experiments, which is how the host-grouping confusion arose.
- Check pass, P02 early_detection: "evidence" is the checker's own explanation (quote match 0.52).

**Fix:** require one contiguous quote (no "..."), allow an `evidence_source: table/figure` marker for table content, and auto-flag any answer with quote match < 0.9 for human review.

## What this means
- Correcting the 4 reference/grading mistakes would raise the round-4 scores. **The reference is not changed yet**: editing it after seeing the model's answers needs your independent confirmation, or the test is biased.
- The 3 definition fixes and 2 targeted hints address every remaining error type found. They're cheap prompt changes, but with only 3 test papers they risk overfitting, so they should be validated on new test papers.
- Human review stays essential, mainly for fields where runs disagree or quotes don't match the paper.
