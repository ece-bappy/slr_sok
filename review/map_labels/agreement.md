# Map labels: judge agreement (291 included papers)

Flash Lite = gemini-3.1-flash-lite (API); Gemini 3.8 = gemini-3.8-flash-high (agy). Same prompt (`review/coding/map_label_rulebook.txt`), blind to each other.

| Field | Agreement | Cohen's κ |
|---|---|---|
| task | 242/291 (83%) | 0.78 |
| study_type | 279/291 (96%) | 0.82 |
| model_class | 233/291 (80%) | 0.74 |

Papers agreed on all three fields: 186/291.

## Human check (8 Nov 2026)

- Spot check of agreed labels: 1/90 field labels wrong (1.1%; 95% Wilson upper bound 6.0%), on 30 randomly drawn papers.
  - S1494 model_class: hybrid -> classical_ml (corrected from agreed hybrid: Isolation Forest and LOF are non-neural classical ML algorithms (no neural components))
- Disputed labels (119): human sided with Flash Lite 44, with Gemini 3.8 73, with neither 2.
- Final labels: `final_labels.csv` (source column per field).
