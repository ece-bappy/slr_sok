# E5b shortcut audit (1 Nov 2026)

`scripts/e5b_audit.py` (origin, sslbl, table) plus `run_benchmark.py` on the SSLBL-labelled tables. CSVs are in `e5b/`, `mta_sslbl/` and `mcfp_sslbl/`.

## (i) Dataset-of-origin probe on benign flows only

Benign flows only: RAID Tranco, HIKARI benign, CTU-Normal (MCFP) and MTA background. Each source contributes the same number of rows (≤ 15,000). A multiclass XGBoost predicts which dataset a benign flow came from. "Grouped" holds out whole capture groups (pcap, client or post) per source, using StratifiedGroupKFold. HIKARI has only G1/G2, so the TLS sets use 3 sources. 5 seeds.

| Features | Split | Sources | Balanced acc. (chance) | Per-source recall |
|---|---|---|---|---|
| g1g2 | random | 4 | 0.998 (0.25) | all ≥ 0.998 |
| g1g2 | grouped | 4 | 0.953 ± 0.018 | RAID 0.998, HIKARI 0.82, CTU 0.999, MTA 0.996 |
| g1g2_notime | random | 4 | 0.996 | all ≥ 0.992 |
| g1g2_notime | grouped | 4 | 0.989 ± 0.001 | RAID 0.993, HIKARI 0.98, CTU 0.997, MTA 0.988 |
| tier_tls13 (G1, G2, G3, G5) | grouped | 3 | 0.944 ± 0.014 (0.33) | RAID 1.000, CTU 0.85, MTA 0.98 |
| all | grouped | 3 | 0.944 ± 0.014 | same as tier_tls13 |

**Finding.** Benign traffic alone identifies its dataset with 94–99% balanced accuracy, even on unseen capture groups and without timing features. Any model trained on malware from one dataset and benign traffic from another can therefore separate the classes by environment alone. This is the mechanism behind the E4 negative-swap result. The remaining confusion is mostly CTU-Normal predicted as MTA background (15% with TLS fields) and HIKARI predicted as RAID (with timing). Confusion matrices: `e5b/origin_probe_confusion_seed0.csv`.

## (ii) Circularity: SSLBL labels vs the IOC / capture labels

SSLBL lists (downloaded 1 Nov 2026) contain 11,119 certificate SHA-1s and 97 JA3s. A flow counts as an SSLBL hit when its leaf-certificate SHA-1 (Zeek re-run with SHA-1 hashing) or its JA3 is listed. The `*_sslbl` tables label hits 1 and the main-label negatives that are not hits 0. SSLBL is used only for this comparison and never as the benchmark label.

| | MTA | MCFP |
|---|---|---|
| TLS flows / with leaf SHA-1 | 125,485 / 51,155 | 2,160,728 / 1,712,331 |
| SSLBL hits (cert / JA3) | 26,059 (1,316 / 25,633) | 290,822 (42,207 / 248,615) |
| Main positives that are SSLBL hits | 14,325 of 45,774 (31%) | 247,699 of 1,488,127 (17%) |
| Main negatives that are SSLBL hits | 598 | 1,775 |
| Hits on flows without a main label | 11,136 | 41,348 |

The two labelling schemes overlap only partly. Most hits are JA3 matches (98% on MTA, 85% on MCFP), and these also fire on background and CTU-Normal flows.

| Table | Features | E1 | E2 | E3 | g4+g5 share of gain (`all`, E2) |
|---|---|---|---|---|---|
| MTA, IOC labels | all | 0.9999 | 0.9958 | 0.901 | 0.93 (JA4S top) |
| MTA, SSLBL labels | all | 1.0000 | 1.0000 | 0.68 ± 0.23 | 0.99 (g5 0.92, JA3 top) |
| MTA, SSLBL labels | g1g2_notime | 0.9994 | 0.989 | 0.878 | – |
| MCFP, capture labels | all | 1.0000 | 0.9999 | infeasible | 0.98 (JA4 top) |
| MCFP, SSLBL labels | all | 1.0000 | 0.9998 | – | 1.00 (JA3/JA4 only) |
| MCFP, SSLBL labels | g1g2_notime | 0.9997 | 0.932 | – | – |

(PR-AUC, XGBoost, 5 seeds.)

**Finding.** Labelling with a JA3/certificate blocklist and then training on JA3/certificate features is circular. With SSLBL labels the `all` model reaches PR-AUC 1.000 on unseen posts or captures, and JA3/JA4 take 92–100% of the gain. This is the label being read back from the features. On the MTA temporal split it collapses (PR-AUC 0.68 ± 0.23; TLS 1.3 flows 0.001), because the listed JA3s are tied to their era. Without TLS fields the SSLBL task is harder than the IOC task (MCFP E2 0.93 vs 0.998), which is the opposite of what the `all` numbers suggest. Papers that label with SSLBL or JA3 blocklists and report fingerprint features need this check.

Note that the IOC-labelled MTA model also puts 93% of its gain on certificate and fingerprint features (`all`, E2). Its labels are independent of those features, but the reliance is a case-memorisation risk; `SUMMARY_e8.md` tests it.

## (iii) Combined shortcut table

`e5b/shortcut_table.csv` has 380 rows: every single-feature training AUC from the benchmark screens (top 25 per dataset and feature set), a ≥ 0.99 flag, and the `has_server_hello` AUC with the share of flows lacking a ServerHello per class.

| Dataset | Flagged features (AUC alone ≥ 0.99) | has_server_hello AUC; no-SH share mal / neg |
|---|---|---|
| RAID | JA3, JA4, ALPN, cipher counts (`all`); first-packet IAT and mean IAT (`g1g2`) | 0.55; 0% / 10.5% |
| HIKARI | none (top: RST packet count 0.95) | – (no TLS fields) |
| MCFP | JA3, JA4, JA3S, JA4S, sigalg / extension / group counts, ALPN | **0.70; 40% / 0.9%** |
| MTA | none (top: JA4S / JA3S 0.977, JA3 / JA4 0.97) | 0.50; 0.7% / 1.0% |
| MTA SSLBL | JA4, JA3, JA4S, JA3S | 0.57; 15% / 1.0% |
| MCFP SSLBL | JA3, JA4, JA3S, JA4S, sigalg / extension counts | 0.52; 5% / 1.0% |

**Finding.** In MCFP, 40% of malicious flows never receive a ServerHello (dead C2 servers in sandbox runs), against 0.9% of benign flows. Handshake completion alone separates the classes there. MTA is free of that artefact.

## Caveats
- The origin probe uses benign flows only; the sources differ in year as well as environment, and the probe cannot separate the two.
- SSLBL is a current snapshot, applied retroactively to 2013–2026 traffic, and certificate coverage is limited to flows with a visible leaf certificate (TLS ≤ 1.2).
- The SSLBL negatives are the main-label negatives minus hits, so the SSLBL task keeps the same benign environment as the main task.
