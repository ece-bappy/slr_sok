# E1–E3 benchmark: MTA 2019–2026 and MCFP (1 Nov 2026)

Same protocol as `SUMMARY.md` (XGBoost, fixed hyperparameters, per-feature-set dedup, 1:1 training balance, validation thresholds, 5 seeds). Per-dataset CSVs and data cards are in `mta/` and `mcfp/`.

## Datasets as built

| | MTA 2019–2026 | MCFP |
|---|---|---|
| Source | 889 pcaps from 629 malware-traffic-analysis.net posts | 201 pcaps from 200 CTU captures; 150 have labelled TLS flows (130 malware, 20 Normal) |
| Malicious label | flow to an endpoint in the post's IOC note (IP, SNI or in-pcap DNS name); IOC hosts on Tranco top-10k domains do not count | every TLS flow of a malware capture (weak, capture-level); flows to Tranco top-10k domains dropped (597,949) |
| Negative label | **same-host background:** the infected host's flows to Tranco top-10k domains not named in the IOCs (not verified benign) | CTU-Normal captures |
| Never used for labels | certificates, SSLBL, JA3/JA4 | same |
| Label coverage | 404 of 629 posts have an IOC note; 57,169 flows in the other 225 posts excluded; 5,131 flows in IOC posts unlabelled | all TLS flows of the 150 captures, minus popular-domain malware flows |
| Labelled flows | 45,769 malicious / 17,418 background | 1,488,127 malicious / 74,652 benign |
| Hosts | malicious: 301 clients → 1,125 servers; background: 289 clients → 3,221 servers | malicious: 34 clients → 5,752 servers; benign: 210 clients → 8,013 servers |
| Years | both classes in every year 2019–2026 (malicious peak 2021–22) | malicious 2013–2018 (72% 2017); benign 93 (2013), 78 (2016), 72,801 (2017), 1,680 unknown |
| TLS versions | malicious 84% 1.2, 14% 1.3; background 84% 1.2, 15% 1.3 | malicious 40% 1.0, 17% 1.2, 43% no ServerHello; benign 98% 1.2 |
| Concentration | largest post = 8% of malicious flows | largest capture = 15% of malicious flows; one server = 293k flows (20%) |
| Duplicates removed | 23 (`all`); 31,863 (`g1g2_notime`, 50%) | 654,163 (`all`, 42%); 1,465,301 (`g1g2_notime`, 94%) |

MCFP pcap timestamps are rebased to 1970 by the publisher, so years come from the date in the pcap name or the MCFP index page (`review/datasets/mcfp_sizes.csv`).

## Results (test set, mean ± SD over 5 seeds)

| Dataset | Features | Exp | PR-AUC | Macro-F1 | Recall malicious | Recall negative | TPR @ val-FPR 10⁻³ (test FPR) |
|---|---|---|---|---|---|---|---|
| MTA | all | E1 random | 0.9999 ± 0.0000 | 0.994 ± 0.001 | 0.995 | 0.995 | 0.986 (0.0008) |
| MTA | all | E2 post-grouped | 0.995 ± 0.002 | 0.915 ± 0.003 | 0.907 | 0.982 | 0.878 (0.0021) |
| MTA | all | E3 ≤2022 → 2023–26 | 0.900 ± 0.006 | 0.760 ± 0.008 | 0.549 | 0.982 | 0.514 (0.0074) |
| MTA | g1g2 | E1 | 0.9998 ± 0.0000 | 0.992 ± 0.000 | 0.994 | 0.991 | 0.987 (0.0009) |
| MTA | g1g2 | E2 | 0.9996 ± 0.0001 | 0.986 ± 0.002 | 0.989 | 0.988 | 0.980 (0.0031) |
| MTA | g1g2 | E3 | 0.912 ± 0.006 | 0.812 ± 0.008 | 0.712 | 0.910 | 0.392 (0.0011) |
| MTA | g1g2_notime | E1 | 0.9987 ± 0.0002 | 0.986 ± 0.002 | 0.980 | 0.993 | 0.934 (0.0002) |
| MTA | g1g2_notime | E2 | 0.997 ± 0.000 | 0.968 ± 0.008 | 0.976 | 0.960 | 0.903 (0.0015) |
| MTA | g1g2_notime | E3 | 0.859 ± 0.015 | 0.796 ± 0.009 | 0.762 | 0.834 | 0.395 (0.0067) |
| MCFP | all | E1 random | 1.0000 ± 0 | 0.999 ± 0.000 | 1.000 | 0.997 | 1.000 (0.0010) |
| MCFP | all | E2 capture-grouped | 0.9999 ± 0.0001 | 0.954 ± 0.001 | 0.999 | **0.849** | 0.999 (**0.151**) |
| MCFP | g1g2 | E1 | 1.0000 ± 0 | 0.998 ± 0.000 | 0.999 | 1.000 | 1.000 (0.0009) |
| MCFP | g1g2 | E2 | 1.0000 ± 0 | 0.998 ± 0.001 | 0.999 | 1.000 | 1.000 (0.0004) |
| MCFP | g1g2_notime | E1 | 0.9995 ± 0.0001 | 0.994 ± 0.000 | 0.990 | 0.996 | 0.980 (0.0012) |
| MCFP | g1g2_notime | E2 | 0.998 ± 0.000 | 0.985 ± 0.002 | 0.964 | 0.998 | 0.951 (0.0016) |
| MCFP | any | E3 | infeasible: benign is 97.5% from 2017 (171 flows earlier) | | | | |

Per TLS version (MTA, g1g2, E3, mean over seeds): TLS 1.2 PR-AUC 0.98 (≈9.2k test flows), TLS 1.3 0.68 (≈3.5k), no ServerHello 0.65 (≈160).

## Findings and flags

1. **MTA: grouping by infection case barely hurts; time does.**
   - E1 → E2 changes little (g1g2 PR-AUC 0.9998 → 0.9996).
   - E3 (train ≤2022, test 2023–2026) drops to PR-AUC 0.86–0.91. Recall at the 10⁻³ operating point falls to ≈0.39–0.51.
   - The drop is concentrated in TLS 1.3 (PR-AUC 0.68 vs 0.98 for TLS 1.2).
2. **The MTA negative class is easy and narrow.**
   - The most frequent background names are Windows telemetry, settings and Bing endpoints. E1/E2 therefore largely measure "malware C2 vs OS background on the same host".
   - api.ipify.org (842 flows), an IP-lookup service malware often calls, falls in the background class under the popular-domain rule.
   - These numbers are an upper bound on real-network performance, not an estimate of it.
3. **Fingerprints memorise cases.**
   - MTA: adding G3–G5 lowers E2 malicious recall from 0.989 (g1g2) to 0.907 (all). JA4S/JA3S/JA3/JA4 alone reach training AUC 0.97–0.98 and lead feature gain.
   - MCFP: JA3/JA4/JA3S/JA4S, signature-algorithm count and extension count each reach AUC ≥ 0.99 alone (flagged). In E2, `all` misclassifies 15% of benign flows from unseen Normal captures (test FPR 0.15), while `g1g2` does not.
4. **MCFP is near-trivially separable and heavily duplicated.**
   - The two sides differ by era and environment: malware is 40% TLS 1.0 with 43% no-ServerHello flows (sandbox VMs, dead C2); benign is 98% TLS 1.2 browsing from 2017.
   - Dedup removes 42% of rows (`all`) and 94% without timing.
   - Labels are weak and capture-level: malware captures also contain non-C2 TLS that is not on the Tranco list.
   - MCFP is best used as a training source for cross-dataset tests, not as a within-dataset benchmark.

## Benign sources available for E4 (not run)

| Source | Nature | Verified benign? |
|---|---|---|
| RAID 2024 Tranco | scripted browser visits, Jan 2024, one client configuration | yes, but one environment |
| HIKARI clean subset | background traffic from the attack pcaps, 2021–22 | per released labels (partial) |
| MTA background | infected host → popular domains, 2019–26 | no (same-host background) |
| CTU-Normal (MCFP) | real user hosts, mostly 2017 | yes (capture-level) |

## Proposed E4 pairings (train → test, not run)

1. **MCFP (malware + CTU-Normal) → MTA (IOC + background)**, and the reverse. Both are real Windows malware with independent labelling; this tests 2013–18 → 2019–26 transfer and sandbox → MTA environments.
2. **RAID C2 + RAID Tranco → MTA**. Tests whether a single-tool, single-environment C2 model detects real-world malware C2. The prediction is that it will not.
3. **Swap the negatives:** train MTA malicious vs CTU-Normal, test on MTA malicious vs MTA background (and vice versa). This separates "learned the malware" from "learned the benign environment".
4. **HIKARI → others:** not proposed. Its attacks are brute force, not C2, and its usable attack set is 2 hosts.

The models need feature-set intersections (MCFP/MTA/RAID share G1–G5; HIKARI only G1/G2). Run `g1g2_notime` as the primary set, because it is least tied to the capture network.
