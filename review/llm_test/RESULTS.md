# Gemma extraction test (26 Oct 2026)

**Question:** should LLM-assisted full-text coding use Gemma's reasoning mode, and does dropping noisy sections help?

**Setup:** `gemma4:26b` on the Ollama PC (RTX 3060 12 GB, model partly offloaded to CPU). Three papers, 23 extraction-form fields each (69 cells). Scored by Claude against `gold.json`: correct, partial (right idea, imprecise or extra items), wrong. **The reference coding has not yet been checked by a human.**

| Paper | File |
|---|---|
| P01 | Barradas et al., RAID 2024 (supervised C2 classifiers, TLS 1.2→1.3) |
| P02 | Kanda et al., JIP 2025 (fingerprint analysis, no ML classifier: an edge case) |
| P03 | Gomez et al., arXiv 2109.03878 (unsupervised clustering) |

## Results

| Input | Reasoning | Correct | Partial | Wrong | Time / paper |
|---|---|---|---|---|---|
| Full text | off | 55 | 5 | 9 | ~1 min |
| Full text | on | 56 | 6 | 7 | ~2.3 min |
| Denoised | off | 57 | 6 | 6 | 15 s – 4 min |
| **Denoised** | **on** | **59 (86%)** | **6** | **4 (6%)** | **~3 min** |

Denoised = Related Work, Conclusion, Acknowledgments, Ethics and References removed (`scripts/pdf_sections.py`, 20–25% of each paper).

## Findings

1. **Denoising helps in both modes** (+2 correct, −2 or −3 wrong). Related Work describes other papers' datasets and models, which Gemma otherwise copies in (e.g. baseline models listed as the paper's own).
2. **Reasoning helps on the judgement fields** that matter most for the SoK: label/feature overlap, cross-dataset testing, early detection on P01.
3. **Reasoning needs sampling, not greedy decoding.** At temperature 0 it looped ("Wait, <field>: ...") until the context filled, returning nothing on all 3 papers. Google's recommended settings (temperature 1.0, top-k 64, top-p 0.95) fixed it. Side effect: answers vary between runs (P01's visibility tier was `tls13_ech` in one run and `tls13` in another).
4. **Remaining errors are mostly prompt definitions, not reading errors:**
   - `feature_visibility_tier`: wrong in most runs. Needs an explicit rule (certificate fields used → `tls12`; only packet sizes/timing → `tls13_ech`).
   - `temporal` / `split_protocol`: P02 has no train/test split, but every run marks it temporal because the paper compares "before/after TLS 1.3". Needs a `not_applicable` option.
5. **Evidence quotes** mostly match the paper text (quote match 1.0 for most denoised answers), so a reviewer can check each answer quickly.

## Recommendation

Use **denoised input + reasoning**, fix the two field definitions above, and keep human review of every paper (30–40 papers × ~3 min of Gemma time is about 2 hours unattended). Consider running reasoning twice and flagging fields where the two runs disagree for closer human review.

## Files

- `side_by_side.csv`: per field, the reference value and the four runs' values with evidence quotes. Columns `human_verdict` / `human_note` are for your check.
- `gold.json`: Claude's reference coding.
- Raw outputs: `D:\new papers\papers\llm\` (`*__think__denoised.json` etc., reasoning text in `*.thinking.txt`).
