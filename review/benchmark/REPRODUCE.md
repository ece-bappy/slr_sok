# Reproducing the benchmark (artifact guide, 4 Nov 2026)

This guide covers every table and figure in `RESULTS.md`: the command or launcher that produced it, its input, its runtime on our machine, and its output. It also gives the pinned environment, the seeds, where each dataset comes from, and what we may not redistribute. No dataset files or credentials are included in the repository or in this guide.

## 1. Machine and environment

| Item | Value |
|---|---|
| Host ("A2") | 2× Intel Xeon Silver 4410T (20 cores / 40 threads), 30 GB RAM, NVIDIA A2 16 GB (driver 595.99.02), Ubuntu 24.04.4 LTS, kernel 6.8 |
| Zeek | 8.0.10 (`/usr/local/bin/zeek`) |
| Main venv (`~/tls-sok/.venv`) | Python 3.12.3. Key packages: numpy 2.5.4, pandas 3.1.0, pyarrow 26.0.0, **scikit-learn 1.9.1**, xgboost 3.4.1, lightgbm 4.7.0, optuna 5.0.0, nfstream 6.6.0, dpkt 1.9.8, scipy 1.18.1, psutil 7.2.2. Full pin: `env/requirements-a2-main.txt` |
| Torch venv (`/data/tls-sok/venv-torch`, made by `scripts/setup_torch_venv.sh`) | Python 3.12.3, torch 2.15.0+cu132 (CUDA 13.2), scikit-learn 1.9.1, pandas 3.1.0, numpy 2.5.4. Full pin: `env/requirements-a2-torch.txt`. Has no optuna: `tune.py` appends the main venv's site-packages at run time for the CNN/BiLSTM searches (same Python version) |
| Figures (any PC) | Python 3.13.2, matplotlib 3.10.1, pandas 2.2.3, numpy 2.2.3 (`env/requirements-figures-local.txt`) |
| RAID 2024 authors' environment (from their README) | Python 3.10, **scikit-learn 1.3.2**, pandas 2.1.1, numpy 1.26.1. We ran their code under 1.9.1; the remaining C-Behav RF gap (≤ 0.97 pp) is most likely this version difference (`SUMMARY_r24.md`) |

**Install:**
```bash
python3.12 -m venv ~/tls-sok/.venv
~/tls-sok/.venv/bin/pip install -r review/benchmark/env/requirements-a2-main.txt
```
```bash
bash scripts/setup_torch_venv.sh
```
Zeek is installed system-wide (`/usr/local/bin/zeek`). The pipeline needs only its `conn`, `ssl` and `x509` logs.

**Running jobs.** All long jobs run detached on the host through `scripts/detach.sh LOG cmd …` (nohup + setsid). Batch launchers (`launch_batch*.sh`) are resumable: each step leaves a `.done` marker in `/data/tls-sok/logs/`, and re-running the launcher skips finished steps.

**Paths.** `/data/tls-sok/{raw,unpacked,out,tables,benchmark,logs}`. Scripts default to these paths; change them with `--tables`, `--out`, etc.

## 2. Seeds and randomness

- **Splits, balancing, model seeds and bootstrap:** seeds 0–4 (5 seeds) in every experiment. Seed `s` drives the split, the 1:1 training subsample, the model's `random_state`, and the bootstrap resampling (200 resamples; 100 for tuning; 20 for test sets over 200k rows).
- **E2 grouping:** `StratifiedGroupKFold(shuffle=True, random_state=100·s + attempt)` (`run_benchmark.split`).
- **E3:** deterministic by year; validation = the latest 15% of the training period.
- **E4:** validation is a 15% stratified sample with `random_state=s`.
- **Optuna:** `TPESampler(seed=0)`, 40 trials, searched on the seed-0 split only.
- **E7:** 30 MTA pcaps sampled with `random.Random(0)`.
- **RAID 2024 notebooks:** run unchanged. Their own seeds (`random_state=42`, `np.random.seed(0/42)`), except the C-Behav decision tree, which has no `random_state`. It reproduces exactly only when the grid-search cells run first (`r24_reproduce.py --grid`).
- **Deep models:** `torch.manual_seed(s)`. GPU kernels are not forced deterministic, so CNN/BiLSTM numbers can differ in the third decimal between runs.

## 3. Data: sources, how to obtain them, what we may not redistribute

The download queues (relative path, URL, size) are in `review/datasets/q_*.tsv`; `scripts/fetch.sh` downloads them with resume. Checksums of what we used are on the host in `/data/tls-sok/dl/{MD5SUMS,SHA256SUMS}`.

| Dataset | Source | How we obtained it | Redistribution |
|---|---|---|---|
| RAID 2024 Metasploit C2 (`raid_ms`) and Tranco benign (`raid_tranco`) | OSF projects osf.io/b64e5 (MS: `captures.tar.gz`, `ms-full.csv`, `certificates_length.csv`) and osf.io/zq9vs (Tranco: 7 pcap zips, `dataset.csv`) | `q_osf.tsv` → `fetch.sh`; `unpack_a2.py` | Public on OSF; the authors ask for a citation. We publish only derived per-flow results, not the pcaps |
| RAID 2024 code | github.com/CarlosANovo/extending12to13 at commit 5562b6a (notebooks, `tls_paper_funcs.py`, `processed-datasets.zip`, `data/{mta,doh}.zip`) | `git clone` into `/data/tls-sok/ext/` | Their repository; not copied into ours |
| RAID 2024 UCNet (their campus network) | Raw traces **not released**. The README links an anonymised Joy table for validation: OSF osf.io/x6yjg, "University Network Traffic", one file `processed_all.csv` (3.73 GB, 11.1M TLS flows, no licence set) | Downloaded 4 Nov 2026 with user approval (`/data/tls-sok/dl/q_ucnet.tsv` → `fetch.sh`). Matches OSF's MD5 `48db4e96…` and SHA-256 `7766df1c…` (`dl/ucnet.{md5,sha256}`) | Theirs; not redistributed. Used only to rerun their UCNet cells |
| HIKARI-2021 (attack pcaps, label CSVs, anonymised benign pcaps in `ground-truth.zip`) | Zenodo record 6463389 | `q_zen.tsv`, `q_hikari_labels.tsv` → `fetch.sh`; MD5s were checked against the record | Check the Zenodo record's licence before redistributing; we publish derived results only |
| Malware-Traffic-Analysis.net (MTA), 2019–2026 posts | malware-traffic-analysis.net: pcap zip and IOC text per post (never the malware-sample zips) | `q_mta.tsv` (1,282 posts) + `q_mta_extra.tsv` (`mta_extra.py`); zip passwords follow the site's published scheme (see `unpack_a2.py`) | **Do not redistribute.** No explicit bulk terms, and the pcaps carry live malware traffic. Publish the URL list (`q_mta*.tsv`) and our labels/derived tables only |
| Stratosphere MCFP (CTU malware captures + CTU-Normal) | mcfp.felk.cvut.cz/publicDatasets/ (open directory, no terms file) | `q_mcfp.tsv` (TLS captures ≤ 2 GB, 2013–2018, plus Normal captures) → `fetch.sh` | Cite Stratosphere; republishing their pcaps is not ours to do. Publish the URL list and derived results |
| abuse.ch SSLBL (certificate SHA-1 and JA3 blocklists), E5b only | sslbl.abuse.ch CSV exports, snapshot of 1 Nov 2026 (`/data/tls-sok/raw/sslbl/downloaded_on.txt`) | Manual download of `sslblacklist.csv` and `ja3_fingerprints.csv` | abuse.ch terms; the list changes daily, so record the date |
| Tranco list (MTA background "popular-domain" rule) | tranco-list.eu, list 7462X (`raw/tranco/list_id.txt`), fetched 1 Nov 2026 | Manual | Tranco terms; cite the list ID |
| CIRA-CIC-DoHBrw-2020, lab browser capture | – | **Not used yet** (both need a user decision: the CIC registration form, and a lab capture rig) | – |

**Labels** (our derived data, publishable): MTA labels come from post IOCs and sandbox metadata, never from certificates or JA3/JA4 (`build_tables.py`; `mta/data_card.json`). MCFP labels are capture-level. HIKARI uses the clean-label subset; RAID labels come from the source.

## 4. Pipeline: pcaps → feature tables

| Step | Command (on the host, from `~/tls-sok`) | Input | Runtime on A2 | Output |
|---|---|---|---|---|
| Download | `bash scripts/fetch.sh review/datasets/q_<x>.tsv /data/tls-sok/raw /data/tls-sok/dl/<x>.log 4` | URL queues | Network-bound (the OSF and MCFP parts are the largest: 32 GB and about 40 GB) | `/data/tls-sok/raw/` |
| RAID + HIKARI extraction | `nohup setsid bash scripts/launch_e1e3_extract.sh > /data/tls-sok/out/e1e3.log 2>&1 < /dev/null &` | raw zips/pcaps | About 40 min (6 workers) | `/data/tls-sok/out/{raid_ms,raid_tranco,hikari_*}/…/flows.parquet` + `manifest.csv` |
| MTA + MCFP extraction and tables | `nohup setsid bash scripts/launch_mta_mcfp.sh > /data/tls-sok/out/mta_mcfp.log 2>&1 < /dev/null &` | raw zips/pcaps | About 2 h 15 min | `out/{mta,mcfp}/`, `tables/{mta,mcfp}.parquet` |
| Table (re)build | `nohup setsid bash scripts/launch_tables.sh mta mcfp raid > /data/tls-sok/out/tables.log 2>&1 < /dev/null &` (HIKARI: `build_tables.py hikari`) | `out/` | 2–5 min per dataset | `tables/<ds>.parquet`, `<ds>.card.json` |
| Leaf-certificate SHA-1 (E5b) | `nohup setsid bash scripts/launch_sha1.sh > /data/tls-sok/out/sha1.log 2>&1 < /dev/null &` | Zeek x509 logs | About 11 min | `*_all.parquet` with SHA-1 |
| Record sequences (RAID 2024 baselines) | in `launch_batch5.sh` (`r24_records.py raid_ms raid_tranco mta mcfp --jobs 24`) | manifests + pcaps | About 4 min | `/data/tls-sok/r24rec/<source>/…parquet` |

Per-pipeline checks: `review/datasets/extraction_audit_e1e3.md` (join rates, JA3/JA4 vs Wireshark).

## 5. Experiments → result folders → RESULTS.md / figures

All result folders are under `review/benchmark/`, copied from `/data/tls-sok/benchmark/`. Runtimes are wall-clock on A2 from the batch logs in `/data/tls-sok/out/`.

| RESULTS.md item | Command / launcher step | Runtime | Output folder → summary |
|---|---|---|---|
| RQ1 E1–E3, RAID and HIKARI | `run_benchmark.py raid` · `run_benchmark.py hikari --sets g1g2,g1g2_notime` | A few minutes each | `raid/`, `hikari/` → `SUMMARY.md` |
| RQ1 E1–E3, MTA and MCFP | `launch_bench_mta_mcfp.sh`; MTA rerun as `launch_batch2.sh` step `mta_e123` | 14 min; 2.5 min | `mta/`, `mcfp/` → `SUMMARY_mta_mcfp.md` |
| RQ1 E4 | `launch_e4.sh` (`run_e4.py`); rerun in `launch_batch2.sh` step `e4` | 28–30 min | `e4/` → `SUMMARY_e4.md` |
| RQ1/RQ2 other families | `launch_batch2.sh` steps `rob_*` (LightGBM, LR, RF) | About 33 min | `{mta,hikari,mcfp}_{lgbm,lr,rf}/`, `e4_{lgbm,lr,rf}/` → `SUMMARY_models.md` |
| 1D-CNN | `launch_deep.sh` (`run_deep.py within`, `e4`) | 38 min (GPU) | `deep/`, `e4_deep/` |
| BiLSTM | `launch_batch5.sh` steps `bilstm_within`, `bilstm_e4` (`run_deep.py … --arch bilstm`) | 63 min (GPU) | `deep_bilstm/`, `e4_deep_bilstm/` → `SUMMARY_models.md` |
| RQ2 E5b (origin probe, SSLBL circularity) | `launch_batch2.sh` steps `e5b_*` (`e5b_audit.py origin|sslbl|table`, `run_benchmark.py {mta,mcfp}_sslbl`) | About 10 min | `e5b/`, `mta_sslbl/`, `mcfp_sslbl/` → `SUMMARY_e5b.md` |
| RQ2 E5a ablation | `launch_batch3.sh` steps `e5a_mta`, `e5a_mcfp`, `e5a_e4` | 25 min | `e5a_mta/`, `e5a_mcfp/`, `e5a_e4/` → `SUMMARY_e5a.md` |
| RQ2/RQ5 cross-family fingerprint check | `launch_batch4.sh` steps `cf_*` | 50 min | `cf_mta_*/`, `cf_e4_*/`, `cf_e9_*/` → `SUMMARY_crossfamily.md` |
| RQ3 E6 early detection | `launch_batch2.sh` steps `e6_mta`, `e6_mcfp` | 14 min | `e6_mta/`, `e6_mcfp/` → `SUMMARY_e6.md` |
| RQ4 E7 cost (full pipeline) | `launch_batch3.sh` steps `e7_*` (`run_e7.py prep|prep_cnn|infer|extract`); the edge proxy is `taskset -c 0` / `0,1` | 15 min | `e7/` → `SUMMARY_e7.md` |
| RQ4 E7 Zeek-free option | `launch_batch4.sh` steps `e7_*_lite`, `e7_ext_*_w`, `e7_ext_*_nozeek` (`--set g1g2g3`, `--no-zeek`) | 5 min | `e7/*_nozeek.json`, `e7/*_g1g2g3.json`, `cf_mta_*` (`g1g2g3` rows) |
| RQ5 E8 visibility tiers | `launch_batch2.sh` steps `e8_*` | 19 min | `e8_mta/`, `e8_mcfp/`, `e8_raid/` → `SUMMARY_e8.md` |
| RQ5 E9 fingerprint drift | `launch_batch3.sh` step `e9` (`run_e9.py`) | 8 min | `e9/` → `SUMMARY_e9.md` |
| Tuning, XGBoost | `launch_batch3.sh` step `tune` (`tune.py`) | 40 min | `tuning/` → `SUMMARY_tuning.md` |
| Tuning, LightGBM / RF / LR / CNN / BiLSTM | `launch_batch5.sh` steps `tune_*` (`tune.py --model … [--timeout 600]`) | 30–80 min each (two lanes in parallel) | `tuning_<model>/` → `SUMMARY_tuning.md` |
| Unsupervised baselines | `launch_batch5.sh` step `unsup` (`run_unsup.py`, torch venv) | 11 min | `unsup/` → `SUMMARY_unsup.md` |
| RAID 2024 reproduction | `launch_batch5_r24.sh` steps `r24_repro` (`r24_reproduce.py`) and `r24_repro_grid` (`--grid`) | 3 min; 1 h 52 min | `r24_repro/`, `r24_repro_grid/` (`compare.csv`) → `SUMMARY_r24.md` |
| RAID 2024 under our protocol | `launch_batch5_r24.sh` step `r24_protocol` (`r24_benchmark.py`) | 53 min | `r24_protocol/` (joined tables of about 1 GB stay on the host) → `SUMMARY_r24.md` |
| RAID 2024 UCNet cells | `launch_ucnet.sh`: checksum check, `r24_ucnet_prep.py` (rebuilds the notebooks' three derived UCNet files with the authors' functions), then `--slim` (drops unread columns), then `r24_reproduce.py --only <notebook>` per notebook and `--grid` for 04 | Prep 10 min; slim 2 min; notebooks 5 min; 04 grid pass 1.5 h. Run on an otherwise idle host | `r24_repro_ucnet/ucnet_prep.json`, `r24_repro_ucnet/{02-C-ALL,03-C-CERT,04-C-BEHAV,04-C-BEHAV_grid}/compare.csv` → `SUMMARY_r24.md` |

**Batch 6 robustness checks** (`scripts/run_b6.py <item>`, 8 Nov). Launchers `launch_batch6.sh` (two lanes) and `launch_batch6b–e.sh`. Every launcher log ends with `BATCH <name> DONE|FAILED <steps>`.

| RESULTS.md item | `run_b6.py` item (launcher) | Runtime | Output folder → summary |
|---|---|---|---|
| 20 seeds + paired Wilcoxon | `seeds` (batch6, lane A); saves test predictions to `/data/tls-sok/b6pred/` | 86 min | `b6_seeds/` → `SUMMARY_b6_seeds.md` |
| Realistic base rates | `baserate` (batch6); reads `b6pred/`, runs C-Cert with 20 seeds | 2 min | `b6_baserate/` (`pooled_precision.csv`) → `SUMMARY_b6_baserate.md` |
| Rolling origin (fig_f) | `rolling` (batch6); `rolling_models` and `rolling_enc` (batch6b); `post2026` (batch6b) | 8 + 11 + 11 min; 25 s | `b6_rolling*/`, `b6_post2026/` → `SUMMARY_b6_rolling.md` |
| Fingerprint encodings | `encoding` (batch6, 20 seeds); joins raw handshake lists from `flows.parquet` into `/data/tls-sok/b6/lists_*.parquet` | 34 min | `b6_encoding/` → `SUMMARY_b6_encoding.md` |
| ECH-padded tier | `ech` (batch6) | 1.5 min | `b6_ech/` → `SUMMARY_b6_ech.md` |
| Training-set sensitivity | `training` (batch6, lane A) | 27 min | `b6_training/` → `SUMMARY_b6_training.md` |
| Leave-one-family-out | `family` (batch6); `family_models` (batch6c) | 4 + 8 min | `b6_family*/` (`pcap_family.csv`) → `SUMMARY_b6_family.md` |
| Evasion (corrected padding rule) | `evasion` (batch6d step `b6_evasion_v2`) | 4 min | `b6_evasion/` → `SUMMARY_b6_evasion.md` |
| TLS 1.3 diagnostic | `tls13` (batch6c) | 2 min | `b6_tls13/` → `SUMMARY_b6_tls13.md` |
| Padding vs ECH tier | `padech` (batch6d) | 1 min | `b6_padech/` → `SUMMARY_b6_padech.md` |
| Leave-one-dataset-out | `lodo` (batch6e) | 15 min | `b6_lodo/` → `SUMMARY_b6_lodo.md` |
| Host-level alerting | `hosts` (batch6e) | 1 min | `b6_hosts/` → `SUMMARY_b6_hosts.md` |

`scripts/smoke_b6.py <item> …` runs any item on a reduced scope into `/data/tls-sok/smoke6` (not results).

Batch logs: `/data/tls-sok/out/batch2.log`, `batch3_1509.log`, `batch4_1937.log`, `batch5_1256.log`, `batch5r24_1340.log`, `batch6_1136.log`, `batch6b_1213.log`, `batch6c_1228.log`, `batch6d_1237.log`, `batch6e_1453.log`, `ucnet_*.log`. Each step's own log is `/data/tls-sok/logs/<step>.log`.

**Figures and captions** (any PC, from the committed CSVs only, in a few seconds):
```bash
python review/benchmark/figures/make_figures.py
```
This writes `figures/fig_{a_collapse,b_tiers,c_fingerprints,d_early,e_origin_probe,f_rolling}.{pdf,png}` and `figures/CAPTIONS.md`.

**Re-running everything after the tables exist** takes about 9 h of host time sequentially (batches 2–5 plus E4 and the CNN). About 5 h of that is the two parallel lanes of batch 5 and the RAID 2024 grid search.

## 6. Known non-determinism and deviations

- **Deep models on GPU:** third-decimal variation between reruns. The BiLSTM seed SD (up to 0.15) dominates anyway.
- **RAID 2024 reproduction:**
  - C-Behav RF differs by ≤ 0.97 pp, likely from scikit-learn 1.9.1 vs 1.3.2.
  - matplotlib is not installed on the host, so a no-op stub replaces it (plots only).
  - UCNet: the three derived input files are our reconstruction with the authors' functions (their preparation notebook is not released). On 20 TLS 1.3 flows (0.0003%) their certificate-size inference raises ValueError; those are counted as failed inferences.
  - UCNet: with the full table, the notebooks exceed 30 GB RAM (OOM-killed three times). Input columns no UCNet cell reads are removed, with every kept field byte-identical, and each notebook runs in its own process. The notebooks themselves are unedited.
  - The runner echoes each cell's final bare expression, as Jupyter does (some UCNet results are returned as tuples, not printed).
- **Batch 6 base rates:** precision is pooled over seeds (ratio of mean TP to mean FP), not averaged per seed (`SUMMARY_b6_baserate.md`).
- **Batch 6 padding rule:** only data-carrying packets (G2 frame > 66 B) are padded, capped at 1,514 B. The first item 8 run padded ACKs too and was superseded.
- **The SSLBL snapshot date matters.** Later snapshots contain more entries and will change the E5b hit counts.
- **MTA posts can be updated or removed by the site.** The `q_mta*.tsv` lists and the SHA-256 checksums on the host record exactly what was used.
