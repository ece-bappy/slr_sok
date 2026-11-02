# E7 deployment cost (2 Nov 2026)

`scripts/run_e7.py`, launched in `scripts/launch_batch3.sh` (A2, 2 Nov 15:09 WITA, log `/data/tls-sok/out/batch3_1509.log`). All 21 E7 steps exited 0. JSON/CSV results are in `e7/`.

## Setup

**Hardware:**
- Server: 2× Intel Xeon Silver 4410T (20 cores / 40 threads), 30 GB RAM.
- GPU: NVIDIA A2 (16 GB).
- **Edge proxy:** the same server pinned with `taskset` to 1 core (`edge1`) or 2 cores (`edge2`), with library thread counts set to match. This is *not* a real edge device. It caps core count, but keeps server-class clock speed, cache, memory bandwidth and disk. A real ARM gateway or SBC would be slower per core.

**Models:**
- XGBoost, LightGBM, RF and LR were trained on MTA `all` features, E2 split seed 0, 1:1 balanced, with the benchmark hyperparameters.
- The 1D-CNN uses the first-20-packet sequence.
- All are scored on the same 12,436-flow test set.

**Inference measurements:**
- Batch=1 latency: 2,000 single-flow calls on random test rows (median and p99).
- Throughput: the test set in batches of 1,024, and in one full batch.
- CPU %: process CPU time / wall time (100% = one core busy).
- Peak RSS: `ru_maxrss` of the process, including the Python, pandas and torch runtime.
- Model size: XGBoost UBJ, LightGBM text, pickled RF and LR, CNN `state_dict`.

**Extraction measurements:** 30 MTA pcaps (random, seed 0; 592 MB, 809k packets, 17,076 TCP flows, 8,780 TLS flows), each processed **offline from a pcap file** by the real pipeline in a fresh child process: Zeek (for x509) → tlsfp handshake parser → NFStream → join → G1–G5 feature build. This is not live capture.

## Inference (per flow, model only, features already extracted)

| Model | Size | Hardware | Batch=1 median / p99 (ms) | Flows/s, batch 1,024 | CPU % (batch 1,024) | Flows/s, full batch | Peak RSS (MB) |
|---|---|---|---|---|---|---|---|
| XGBoost | 0.98 MB | server 16 thr | 6.96 / 8.61 | 122,574 | 951 | 1,037,836 | 391 |
| | | edge2 | 6.39 / 7.35 | 116,510 | 160 | 463,603 | 391 |
| | | edge1 | 6.31 / 6.92 | 106,308 | 100 | 316,549 | 391 |
| | | A2 GPU | 8.95 / 11.28 | 89,804 | 951 | 274,144 | 444 |
| LightGBM | 0.96 MB | server | 3.11 / 3.50 | 230,423 | 1,590 | 808,169 | 228 |
| | | edge2 | 2.85 / 4.17 | 159,337 | 199 | 313,709 | 228 |
| | | edge1 | 2.86 / 3.21 | 123,084 | 100 | 186,836 | 228 |
| RF | 9.6 MB | server | 130.0 / 148.9 | 3,319 | 114 | 36,456 | 280 |
| | | edge2 | 40.0 / 72.6 | 17,129 | 94 | 55,820 | 279 |
| | | edge1 | 13.6 / 20.4 | 41,893 | 100 | 94,026 | 278 |
| LR | 33 KB | server | 39.9 / 64.4 | 18,231 | 100 | 80,380 | 274 |
| | | edge1 | 40.2 / 67.3 | 18,013 | 100 | 80,300 | 273 |
| 1D-CNN | 55 KB | server 16 thr | 0.078 / 0.168 | 259,585 | 1,602 | 209,365 | 912 |
| | | edge2 | 0.066 / 0.077 | 94,760 | 200 | 68,341 | 914 |
| | | edge1 | **0.047** / 0.055 | 77,142 | 100 | 53,757 | 914 |
| | | A2 GPU | 0.115 / 0.125 | **413,467** | 100 | **434,285** | 1,246 |

Test PR-AUC (sanity check that the right model was timed): XGBoost 0.996, LightGBM 0.998, RF 0.999, LR 0.997, CNN 0.996. LR edge2 is in `e7/` and matches edge1.

## Feature extraction (offline, pcap → G1–G5)

| Hardware | Wall time (30 pcaps) | ms per TCP flow | ms per TLS flow | TCP flows/s | Mbit/s of pcap | Zeek / tlsfp / NFStream / join / features (s) | Peak RSS (MB) |
|---|---|---|---|---|---|---|---|
| server (auto threads) | 41.2 s | 2.42 | 4.70 | 414 | 115 | 19.5 / 12.0 / 4.9 / 3.0 / 1.8 | 293 |
| edge2 | 46.9 s | 2.75 | 5.34 | 364 | 101 | 21.6 / 13.7 / 6.1 / 3.5 / 2.0 | 285 |
| edge1 | 29.1 s | **1.71** | 3.32 | 586 | 163 | 12.4 / 9.2 / 4.1 / 2.2 / 1.2 | 256 |

## End to end (extraction + inference, per flow)

Extraction dominates. It costs about 1.7–2.7 ms per TCP flow (3.3–5.3 ms per TLS flow) on one or two cores. Model inference in batches costs 0.002–0.06 ms per flow for every model.

- **Per core, end-to-end throughput is about 350–590 TCP flows/s.** XGBoost, LightGBM and the CNN add less than 1% to that.
- **At batch=1 (score each flow as it completes), the model is a visible part of the cost:**
  - XGBoost (6.3 ms) and LR (40 ms) exceed the extraction cost; LightGBM (2.9 ms) roughly matches it.
  - The CNN (0.05 ms) is negligible.
  - Much of this per-call cost is Python and pandas wrapper overhead, not tree evaluation (see caveats).
- A 1–2-core box can therefore handle a few hundred new TLS flows per second through the full pipeline, provided flows are scored in micro-batches.

## Findings

1. **Feature extraction, not the model, is the bottleneck.**
   - Zeek is about 45% and the tlsfp handshake parser about 30% of extraction time; NFStream about 12%.
   - Zeek is used only for the certificate group (G4). A G1/G2/G3/G5-only deployment could drop it and roughly halve extraction cost; per E5a/E8 that loses little accuracy.
2. **The GPU does not pay off at this model size.**
   - XGBoost on the A2 is slower than on CPU: 274k vs 1.04M flows/s at full batch, and 9.0 vs 7.0 ms at batch=1.
   - The CNN gains 1.6–2× in batched throughput over 16 CPU threads, but its batch=1 latency is higher (0.115 vs 0.047 ms) because of the host-to-device copy.
3. **All models are small.** Sizes range from 33 KB (LR) and 55 KB (CNN) through about 1 MB (XGBoost, LightGBM) to 9.6 MB (RF). Peak RSS is 230–390 MB for tree models; the CNN needs about 900 MB, almost all of it the PyTorch runtime.
4. **More threads hurt at small batch sizes.**
   - RF with 16 joblib workers is 10× slower at batch=1 than with 1 (130 vs 13.6 ms).
   - XGBoost and LightGBM batch=1 latency does not improve with threads.
   - Parallelism helps only for large batches (XGBoost full batch: 317k → 1.04M flows/s from 1 → 16 threads).

## Caveats
- **Edge = taskset proxy on a Xeon**, not an embedded device: it gives an upper bound for a 1–2-core box.
- **Extraction run order and page cache.** The three runs read the same 30 pcaps in the order server → edge2 → edge1, so edge1 ran with a warm page cache. This, plus Zeek's and NFStream's multi-thread start-up cost on small pcaps, probably explains why edge1 is fastest. Read the three rows as one range (1.7–2.7 ms per TCP flow), not as a ranking.
- **Zeek start-up overhead.** Zeek is launched once per pcap. On small pcaps its start-up (about 0.5–0.7 s per run in the smoke test) is a large part of its time, so per-flow extraction cost is overstated compared with a long-running live sensor.
- **Offline pcap processing**, not live capture: there is no packet loss, NIC or ring-buffer behaviour, and no flow-timeout delay. In a live deployment a flow can only be scored after its first 20 packets (G2) or after it ends (G1 whole-flow statistics).
- **Batch=1 latencies include Python, pandas and sklearn wrapper overhead.**
  - LR's 40 ms is mostly the sklearn `ColumnTransformer` (imputer, scaler, one-hot) on a one-row DataFrame.
  - XGBoost's and LightGBM's few ms are mostly `predict_proba` on a pandas frame with categorical columns.
  - A compiled or native predictor (Treelite, the XGBoost C API, ONNX) would be orders of magnitude faster per call. The numbers are faithful to this Python implementation, not to the models' intrinsic cost.
- **Extraction CPU %** (127–523%; in `e7/extract_*.json`) counts each child's Python import time and Zeek's helper processes, while wall time starts after imports. It overstates CPU use, so it is not shown in the table.
- Throughput was measured on one dataset (MTA) with one feature set (`all`). Fewer features (for example `g1g2_notime`) would make inference cheaper, but not extraction, unless Zeek and tlsfp are dropped.
