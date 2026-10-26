# Screening test: Gemma 4 26B, title/abstract (26 Oct 2026)

**Sample:** 10 records drawn with a fixed seed from `screening_log.csv`: 4 likely relevant (malicious + TLS/encrypted in the title), 4 random clean records, 2 random `no_tls_term` records. The extraction-validation candidates were left out.

**Reference:** Claude screened the 10 blind, before writing or running the script (`claude_reference_10.csv`).

**Runs:** `scripts/screen_llm.py`, batches of 10, JSON schema output, with and without reasoning.

| Run | Same decision as reference | Same exclusion criterion | Time for 10 |
|---|---|---|---|
| No reasoning (`gemma_nothink_10.csv`) | 10/10 | 5/6 | 39 s |
| Reasoning (`gemma_think_10.csv`) | 10/10 | 5/6 | 71 s |
| No reasoning, mandatory reasons (`gemma_nothink_10_v2.csv`) | 10/10 | 5/6 | 39 s |

- The one criterion difference (S3414, classifying Internet devices from HTTP responses): Gemma said `benign_only`, the reference `off_topic`; both are valid exclusions.
- The record with no abstract (S2414) was correctly sent to `maybe`.
- v1 left the reason empty for includes; the prompt now requires a reason for every record (v2).

**Limits:** 10 records, 4 of them obvious includes, so this shows the script and prompt work but says nothing reliable about recall on borderline papers. That needs the planned blind sample (100 random + ~20 known-relevant records screened by a human).

**Full-run estimate:** 3,503 records ≈ 3.8 h without reasoning, ≈ 7 h with reasoning, with the Ollama PC on.
