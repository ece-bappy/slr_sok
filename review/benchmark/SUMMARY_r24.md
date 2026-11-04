# Published baselines: RAID 2024 C-Cert and C-Behav (3 Nov 2026)

Barradas, Novo et al., *Extending C2 Traffic Detection Methodologies: From TLS 1.2 to TLS 1.3-enabled Malware*, RAID 2024. Code: github.com/CarlosANovo/extending12to13 (commit 5562b6a), cloned to A2 with approval; the user approved running it. Launched in `scripts/launch_batch5_r24.sh` (A2, 3 Nov 15:40–18:25 WITA, log `/data/tls-sok/out/batch5r24_1340.log`). The first `r24_repro` run failed on the matplotlib import; it was rerun by hand right after (log `/data/tls-sok/logs/r24_repro.log`) and exited 0.

## 1. Reproduction from the released code (`r24_repro/`, `r24_repro_grid/`)

`scripts/r24_reproduce.py` runs the code cells of `02-C-ALL`, `03-C-CERT` and `04-C-BEHAV` unchanged, on the processed CSVs that ship with the repository. The Metasploit certificate lengths come from our earlier OSF download (the README says to fetch them separately). Every result row the notebooks print (the paper's LaTeX table rows) is compared with the output stored in the notebook. Those stored outputs match the paper's Tables 2–4.

| Classifier | Paper table rows | Max gap, run with the authors' recorded best parameters | Max gap, with their grid searches rerun |
|---|---|---|---|
| C-Basic (DT, RF) | Table 2 | **0.00 pp** (all 4 rows) | 0.00 pp |
| C-Cert (DT, RF), TLS 1.2 and TLS 1.3 via certificate-size inference | Tables 3–4 | **0.00 pp** (all 8 rows) | 0.00 pp |
| C-Behav DT, TLS 1.2 and TLS 1.3 via behaviour extraction | Tables 3–4 | 1.42 pp (TLS 1.3 rows) | **0.00 pp** |
| C-Behav RF | Tables 3–4 | 0.97 pp | 0.97 pp (e.g. MTA TNR 90.61 vs 91.58; TPR 98.14 vs 97.59) |

- **Why the C-Behav DT gap closes on the grid pass.** The final C-Behav tree is built without `random_state`, so its tie-breaking depends on the global random state. Running the grid cells first, as the authors did, evidently leaves that state as it was in their run.
- **Remaining C-Behav RF gap (≤ 0.97 pp).** Likely the scikit-learn version (1.9.1 here vs 1.3.2 in the paper) changing RF internals at a fixed seed.
- **Grid searches** (rerun on A2) select the parameters the notebooks hard-code:
  - C-Cert DT: identical choice and CV score (0.98386).
  - C-Cert RF: same depth 5 and 40 trees at the same CV score, but gini instead of entropy (a tie, with one feature).
  - C-Behav DT: identical (CV F1 0.92182 vs 0.92185).
  - C-Behav RF: depth 25 with 40 trees instead of depth 20 with 70 trees (CV F1 0.931 vs 0.934).
  - The notebooks then use the hard-coded values, so the tables are unaffected.
- **Not reproduced here:** the UCNet results (their campus network). The raw traces are not released; the README links an anonymised, preprocessed copy for validation (osf.io/x6yjg). We did not download it, because no new downloads were approved, so those cells fail with FileNotFoundError. Fetching that copy into `data/ucnet/` would let them run.
- **Deviations** (logged per cell in `cells.csv`):
  - `display()` is silenced.
  - `multiprocess` → `multiprocessing`; `tqdm.notebook` → `tqdm`.
  - matplotlib is not installed on A2, so it is replaced by a no-op stub. This affects plots only.
  - A few `02-C-ALL` cells only display grid-search objects whose fitting the authors commented out; they error and do not affect any number.

**Verdict:** the released code reproduces the published C-Basic, C-Cert and C-Behav numbers, exactly or within 1 pp.

## 2. Under our protocol (`r24_protocol/`)

**Setup** (`scripts/r24_records.py` + `scripts/r24_benchmark.py`):
- **Record extraction.** Joy-format record sequences (first 20 TLS records: length, direction, content type, plus the server certificate list) are extracted from our pcaps. Flow boundaries match our flow tables, so all 62,324 MTA, 908,616 MCFP and 1,094,468 RAID flows (after dedup) are joined, a 100% match.
  - Check: on the Metasploit TLS 1.2 long-certificate capture, the extracted chain length is 2,547 bytes, the authors' Wireshark value.
- **Features** are computed with the authors' own functions (`tls_paper_funcs.py`):
  - C-Cert: certificate chain size (TLS < 1.3), or inferred size (TLS 1.3).
  - C-Behav: the first 10 application-data records, after handshake removal on TLS 1.3.
- **Classifiers** use their hard-coded parameters and their training-noise augmentation.
- **Our protocol around them:** labels and splits are ours; 1:1 training balance; validation-only thresholds; 5 seeds; bootstrap CIs.
- **Same-rows reference:** each classifier is scored only on flows where its feature exists. XGBoost on G1–G5 is trained and scored on exactly the same rows.
- **The paper's own operating point** (`predict()`, i.e. probability 0.5) is in `summary.csv` as `tpr_at_0.5` / `tnr_at_0.5`.

**Coverage** (share of flows where the feature exists):

| Dataset | C-Cert: all / malicious / benign | C-Behav: all / malicious / benign | TLS 1.3 share |
|---|---|---|---|
| RAID | 0.94 / 1.00 / 0.86 | 0.92 / 1.00 / 0.82 | 48% |
| MTA | **0.45 / 0.28 / 0.90** | 0.92 / 0.92 / 0.94 | 14% |
| MCFP | 0.87 / 0.89 / 0.62 | 0.85 / 0.86 / 0.74 | 0.004% |

On MTA, C-Cert can score only 28% of malicious flows: most malware C2 there is TLS 1.3, a resumed session, or a flow whose certificate inference fails. Its scores below are for that subset.

**Results** (PR-AUC mean ± SD [mean 95% CI]; macro-F1 at the validation max-F1 threshold; "TNR / TPR @0.5" is the paper's operating point):

| Setting (test prevalence) | C-Cert DT | C-Cert RF | C-Behav DT | C-Behav RF | XGB G1–G5, same rows |
|---|---|---|---|---|---|
| RAID E2, pcap-grouped (0.57–0.59) | 0.962 [0.962–0.963] | 0.999 | 1.000 | 1.000 | 1.000 |
| MTA E2, post-grouped (cert rows 0.43; behav 0.73) | 0.899 ± 0.122 | 0.981 [0.977–0.984] | 0.972 [0.969–0.975] | 0.996 [0.996–0.997] | 0.998 (cert rows) / 0.999 (behav rows) |
| MTA E3, ≤2022 → later (0.37; 0.49) | 0.692 [0.681–0.704] | 0.880 [0.872–0.887] | 0.762 [0.752–0.771] | 0.890 [0.883–0.896] | **0.941** (cert rows) / **0.903** (behav rows) |
| MTA E3 macro-F1 | 0.776 | 0.773 | 0.791 | 0.792 | 0.880 / 0.788 |
| E4 MCFP → MTA (0.46; 0.73) | 0.767 [0.761–0.772] | 0.820 [0.815–0.825] | 0.746 [0.743–0.750] | 0.863 [0.860–0.867] | 0.822 / 0.894 |
| E4 macro-F1 | **0.788** | **0.789** | 0.326 | 0.565 | 0.333 / 0.609 |
| E4 TNR / TPR @0.5 | 0.99 / 0.59 | 0.99 / 0.48 | 0.93 / 0.13 | 0.98 / 0.16 | 0.02 / 0.99 (cert rows); 0.03 / 1.00 (behav rows) |

## Findings

1. **The published classifiers are reproducible, and on their own data they match the paper.** On RAID E2 under our protocol, C-Cert RF and C-Behav score 0.999–1.000, the same as our XGBoost. RAID is uninformative, as for every model (`SUMMARY_e5b.md`).
2. **Under drift they lose more than a multi-feature model.** On MTA E3, C-Cert RF reaches 0.880 and C-Behav RF 0.890, against XGB G1–G5 at 0.941 / 0.903 on the same rows. The depth-1 C-Cert tree drops to 0.692.
3. **Their scores rank badly across datasets, but their operating point transfers better.** MCFP → MTA:
   - The single-feature C-Cert keeps its training-time operating point: TNR 0.99 at TPR 0.48–0.59, macro-F1 0.79.
   - XGBoost on the same rows ranks slightly better (PR-AUC 0.82) but flags 98% of MTA background at its validated threshold (macro-F1 0.33).
   - Low capacity limits how far a model can overfit the source environment. This holds only on the 45% of MTA flows that C-Cert can score at all (28% of the malicious ones).
4. **C-Behav does not transfer across datasets:** TPR 0.13–0.16 at the paper's threshold, PR-AUC 0.75–0.86 against a prevalence of 0.73.
5. **Coverage is part of the result.** A certificate-size detector cannot see most TLS 1.3 / resumed malware flows on MTA. Papers that report C-Cert-style accuracy should report coverage alongside it.

## Caveats
- Features come from our own record extraction, not from Joy itself. The format and the authors' functions are identical, and the certificate length matches the authors' Wireshark-derived value on their Metasploit capture. Differences in Joy's TCP reassembly corner cases are possible.
- All rows are deduplicated on the G1–G5 vector, not on each baseline's own features. Per-feature-set dedup would collapse C-Cert to a few hundred distinct certificate sizes, so every classifier sees the same flows instead.
- Their models were trained on TLS 1.2 and tested on TLS 1.3, because the authors had no TLS 1.3 labels. Here both versions are in training, because our datasets are labelled, and per-version results are in `results_per_tls_version.csv`.
- Joined feature tables (`joined_*.parquet`, about 1 GB) stay on A2 at /data/tls-sok/benchmark/r24_protocol/ and are not committed.
