# Batch 6 item 9: is later-period TLS 1.3 malware undetectable? (8 Nov 2026)

`run_b6.py tls13`, launched in `launch_batch6c.sh` (A2, 8 Nov 14:29–14:31 WITA; exit 0). XGBoost, MTA E3 (≤2022 → 2023–26), 5 seeds. CSVs are in `b6_tls13/`.

**Trigger:** item 5 found ROC 0.51–0.60 on TLS 1.3 test flows in every ECH-tier variant. Main asked whether later TLS 1.3 malicious flows are near-undetectable *whatever the features*.

**Answer: no.** The near-chance result belongs to the **size/timing view (G1+G2) only**. With handshake fields, TLS 1.3 flows are detected at ROC 0.94.

## (a) Per-version results for every reported feature set (trained on all versions)

ROC-AUC ± SD; PR-AUC in brackets. Test prevalence: TLS 1.3 subset 0.56 (3,466 flows); TLS 1.2 subset 0.44 (9,197).

| Feature set | TLS 1.3 subset | TLS 1.2 subset | All |
|---|---|---|---|
| G1–G5 (`all`) | 0.828 ± 0.036 (0.848) | 0.877 (0.898) | 0.876 (0.901) |
| **No G5 (G1–G4)** | **0.943** ± 0.003 (0.953) | 0.994 (0.991) | 0.984 (0.982) |
| **Zeek-free (G1–G3)** | **0.938** ± 0.014 (0.950) | 0.987 (0.983) | 0.973 (0.971) |
| **G1+G2 (ECH tier)** | **0.537** ± 0.021 (0.683) | 0.986 (0.984) | 0.901 (0.912) |
| G1+G2, no timing | 0.555 ± 0.031 (0.598; prevalence 0.45) | 0.968 (0.950) | 0.894 (0.859) |

So E8's "full 0.848 vs ECH 0.683" TLS 1.3 PR-AUCs mean ROC 0.83 vs 0.54. The ECH-tier number is essentially prevalence; the full-tier number is not.

## (b) TLS 1.3 share by period, class and year (deduplicated `all` table)

| Period / year | Benign TLS 1.3 share | Malicious TLS 1.3 share |
|---|---|---|
| Training ≤2022 (all years) | 9.6% | **11.2%** |
| 2019 / 2020 / 2021 / 2022 | 3% / 9% / 12% / 10% | **0% / 0% / 0.7% / 22%** |
| Test 2023–26 (all years) | 22.8% | **31.3%** |
| 2023 / 2024 / 2025 / 2026 | 11% / 30% / 27% / 67% | 13% / 28% / 46% / **84%** |

Malicious TLS 1.3 is almost absent from training before 2022: 4,418 of 39,566 malicious training flows (11.2%), nearly all from 2022. By 2026, 84% of malicious flows are TLS 1.3.

## (c) Training on one TLS version only (tested on the same version)

| Feature set | TLS 1.3 test, trained on all versions | **TLS 1.3 test, trained on TLS 1.3 only** | TLS 1.2 test, trained on all | TLS 1.2 test, trained on TLS 1.2 only |
|---|---|---|---|---|
| G1+G2 (ECH tier) | 0.537 | **0.892** (PR 0.911) | 0.986 | 0.985 |
| G1+G2, no timing | 0.555 | **0.798** | 0.968 | 0.978 |
| No G5 | 0.943 | 0.828 | 0.994 | 0.994 |
| Zeek-free | 0.938 | 0.822 | 0.987 | 0.988 |
| G1–G5 | 0.828 | 0.856 | 0.877 | 0.877 |

- **Size/timing patterns are version-specific.** What G1+G2 learns on TLS 1.2 flows, 87% of malicious training data, does not apply to TLS 1.3 flows. Trained on the few TLS 1.3 flows instead, the same view reaches ROC 0.89.
- **Handshake-based models are the opposite.** They generalise across versions and lose when restricted to the small TLS 1.3 training set (0.94 → 0.83).

## (d) Concentration (`breakdown.csv`; seed 0; G1–G5 and no-G5 models)
- No single post or family moves the TLS 1.3 ROC by more than **0.04 (G1–G5)** or **0.016 (no G5)** when left out.
- Posts with an inverted ranking (ROC < 0.5) in the TLS 1.3 subset: 9 of 47 posts for G1–G5, 4 of 47 for no G5.
- The TLS 1.3 malicious test set is dominated by **Lumma (1,128 of 1,939 flows)**. Lumma's own ROC within the subset is 0.86 (G1–G5) / 0.96 (no G5).
- The per-group breakdown was not computed for the G1+G2 model. Its near-chance TLS 1.3 ROC is explained by (c).

## (e) TLS 1.2 contrast
- All feature sets reach ROC 0.97–0.99 on TLS 1.2 test flows, except G1–G5 at 0.88.
- For G1–G5 on TLS 1.2, one large group of two-family-title posts drives the ranking: leaving it out raises the ROC to 0.98. With the hash model, the posts of a few campaigns decide the score.

## Findings
1. **Later TLS 1.3 malware is detectable**, at ROC 0.94 with flow + handshake features (no G5) or the Zeek-free set. What fails is the ECH view (sizes and timing only, ROC 0.54).
2. **The ECH-tier failure is a training-composition effect, not an information limit.** Malicious TLS 1.3 is about 0% of training before 2022; trained on TLS 1.3 flows, the ECH view reaches 0.89.
3. **Suggested RQ5 wording:** "Under ECH, size and timing patterns learned on TLS 1.2 malware do not transfer to TLS 1.3 malware (ROC 0.54); detectors need TLS 1.3 training data, with which the same view recovers to ROC 0.89. Handshake-visible models transfer across versions (0.94)."

## Caveats
- One temporal split; TLS 1.3 training data is mostly 2022.
- The TLS 1.3 test subset is dominated by one family (Lumma, 58% of its malicious flows).
- The per-version subsets use the threshold of the full validation set.
