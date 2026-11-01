# E1–E3 benchmark: MTA 2019–2026 and MCFP (1 Nov 2026)

Same protocol as `SUMMARY.md` (XGBoost, fixed hyperparameters, per-feature-set dedup, 1:1 training balance, validation thresholds, 5 seeds). Per-dataset CSVs and data cards are in `mta/` and `mcfp/`.

## Datasets as built

| | MTA 2019–2026 | MCFP |
|---|---|---|
| Source | 889 pcaps from 629 malware-traffic-analysis.net posts | 201 pcaps from 200 CTU captures; 150 have labelled TLS flows (130 malware, 20 Normal) |
| Malicious label | flow to an endpoint in the post's IOC note (IP, SNI or in-pcap DNS name); IOC hosts on Tranco top-10k domains do not count, except IP-lookup services (below) | every TLS flow of a malware capture (weak, capture-level); flows to Tranco top-10k domains dropped (597,949) |
| Negative label | **same-host background:** the infected host's flows to Tranco top-10k domains not named in the IOCs (not verified benign); IP-lookup services (api.ipify.org, ipinfo.io, icanhazip.com and 22 others) are never background | CTU-Normal captures |
| Never used for labels | certificates, SSLBL, JA3/JA4 | same |
| Label coverage | 404 of 629 posts have an IOC note; 57,169 flows in the other 225 posts excluded; 5,971 flows in IOC posts unlabelled, including 864 IP-lookup flows the IOC note does not name | all TLS flows of the 150 captures, minus popular-domain malware flows |
| Labelled flows | 45,774 malicious / 16,573 background | 1,488,127 malicious / 74,652 benign |
| Hosts | malicious: 302 clients → 1,129 servers; background: 286 clients → 3,171 servers | malicious: 34 clients → 5,752 servers; benign: 210 clients → 8,013 servers |
| Years | both classes in every year 2019–2026 (malicious peak 2021–22) | malicious 2013–2018 (72% 2017); benign 93 (2013), 78 (2016), 72,801 (2017), 1,680 unknown |
| TLS versions | malicious 84% 1.2, 14% 1.3; background 84% 1.2, 15% 1.3 | malicious 40% 1.0, 17% 1.2, 43% no ServerHello; benign 98% 1.2 |
| Concentration | largest post = 8% of malicious flows | largest capture = 15% of malicious flows; one server = 293k flows (20%) |
| Duplicates removed | 23 (`all`); 31,439 (`g1g2_notime`, 50%) | 654,163 (`all`, 42%); 1,465,301 (`g1g2_notime`, 94%) |

MCFP pcap timestamps are rebased to 1970 by the publisher, so years come from the date in the pcap name or the MCFP index page (`review/datasets/mcfp_sizes.csv`).

## Results (test set, mean ± SD over 5 seeds)

| Dataset | Features | Exp | PR-AUC | Macro-F1 | Recall malicious | Recall negative | TPR @ val-FPR 10⁻³ (test FPR) |
|---|---|---|---|---|---|---|---|
| MTA | all | E1 random | 0.9999 ± 0.0000 | 0.993 ± 0.001 | 0.994 | 0.997 | 0.989 (0.0006) |
| MTA | all | E2 post-grouped | 0.9958 ± 0.0010 | 0.910 ± 0.004 | 0.904 | 0.981 | 0.885 (0.0020) |
| MTA | all | E3 ≤2022 → 2023–26 | 0.901 ± 0.006 | 0.777 ± 0.024 | 0.587 | 0.974 | 0.532 (0.0117) |
| MTA | g1g2 | E1 | 0.9998 ± 0.0000 | 0.990 ± 0.001 | 0.992 | 0.991 | 0.984 (0.0010) |
| MTA | g1g2 | E2 | 0.9995 ± 0.0002 | 0.982 ± 0.005 | 0.986 | 0.987 | 0.942 (0.0022) |
| MTA | g1g2 | E3 | 0.912 ± 0.005 | 0.813 ± 0.004 | 0.720 | 0.906 | 0.448 (0.0025) |
| MTA | g1g2_notime | E1 | 0.9989 ± 0.0003 | 0.987 ± 0.002 | 0.984 | 0.991 | 0.931 (0.0003) |
| MTA | g1g2_notime | E2 | 0.9945 ± 0.0013 | 0.956 ± 0.010 | 0.969 | 0.944 | 0.894 (0.0051) |
| MTA | g1g2_notime | E3 | 0.859 ± 0.013 | 0.791 ± 0.009 | 0.754 | 0.831 | 0.415 (0.0115) |
| MCFP | all | E1 random | 1.0000 ± 0 | 0.999 ± 0.000 | 1.000 | 0.997 | 1.000 (0.0010) |
| MCFP | all | E2 capture-grouped | 0.9999 ± 0.0001 | 0.954 ± 0.001 | 0.999 | **0.849** | 0.999 (**0.151**) |
| MCFP | g1g2 | E1 | 1.0000 ± 0 | 0.998 ± 0.000 | 0.999 | 1.000 | 1.000 (0.0009) |
| MCFP | g1g2 | E2 | 1.0000 ± 0 | 0.998 ± 0.001 | 0.999 | 1.000 | 1.000 (0.0004) |
| MCFP | g1g2_notime | E1 | 0.9995 ± 0.0001 | 0.994 ± 0.000 | 0.990 | 0.996 | 0.980 (0.0012) |
| MCFP | g1g2_notime | E2 | 0.998 ± 0.000 | 0.985 ± 0.002 | 0.964 | 0.998 | 0.951 (0.0016) |
| MCFP | any | E3 | infeasible: benign is 97.5% from 2017 (171 flows earlier) | | | | |

Per TLS version (MTA, g1g2, E3, mean over seeds): TLS 1.2 PR-AUC 0.98 (≈9.2k test flows), TLS 1.3 0.68 (≈3.5k), no ServerHello 0.69 (≈160).

## Changes after the IP-lookup fix (rerun 1 Nov 2026, 20:33)

The first MTA run put api.ipify.org and similar IP-lookup flows into the background class, because they are popular domains. Malware often calls these services, so they are no longer background:
- Background: 17,418 → 16,573 flows (845 lookup flows removed). Malicious: 45,769 → 45,774 (6 lookup flows named in an IOC note added).
- 864 lookup flows are now unlabelled and excluded.

E1–E3 were rerun on the rebuilt table. MTA numbers in the table above are the rerun; MCFP is unchanged. Changes larger than 0.01:

| Features | Exp | Metric | Before | After |
|---|---|---|---|---|
| all | E3 | macro-F1 | 0.760 | 0.777 |
| all | E3 | recall malicious | 0.549 | 0.587 |
| all | E3 | TPR @ val-FPR 10⁻³ (test FPR) | 0.514 (0.0074) | 0.532 (0.0117) |
| g1g2 | E2 | TPR @ val-FPR 10⁻³ | 0.980 | 0.942 |
| g1g2 | E3 | TPR @ val-FPR 10⁻³ | 0.392 | 0.448 |
| g1g2_notime | E2 | macro-F1 / recall negative | 0.968 / 0.960 | 0.956 / 0.944 |
| g1g2_notime | E3 | TPR @ val-FPR 10⁻³ | 0.395 | 0.415 |

Every PR-AUC moved by less than 0.003, and every conclusion below stands. The background class was about 5% IP-lookup flows, which is too few to drive the headline numbers.

## Findings and flags

1. **MTA: grouping by infection case barely hurts; time does.**
   - E1 → E2 changes little (g1g2 PR-AUC 0.9998 → 0.9996).
   - E3 (train ≤2022, test 2023–2026) drops to PR-AUC 0.86–0.91. Recall at the 10⁻³ operating point falls to ≈0.39–0.51.
   - The drop is concentrated in TLS 1.3 (PR-AUC 0.68 vs 0.98 for TLS 1.2).
2. **The MTA negative class is easy and narrow.**
   - The most frequent background names are Windows telemetry, settings and Bing endpoints. E1/E2 therefore largely measure "malware C2 vs OS background on the same host".
   - IP-lookup services that malware often calls (api.ipify.org and others) are excluded from the background class since the rerun (section above).
   - These numbers are an upper bound on real-network performance, not an estimate of it.
3. **Fingerprints memorise cases.**
   - MTA: adding G3–G5 lowers E2 malicious recall from 0.989 (g1g2) to 0.907 (all). JA4S/JA3S/JA3/JA4 alone reach training AUC 0.97–0.98 and lead feature gain.
   - MCFP: JA3/JA4/JA3S/JA4S, signature-algorithm count and extension count each reach AUC ≥ 0.99 alone (flagged). In E2, `all` misclassifies 15% of benign flows from unseen Normal captures (test FPR 0.15), while `g1g2` does not.
4. **MCFP is near-trivially separable and heavily duplicated.**
   - The two sides differ by era and environment: malware is 40% TLS 1.0 with 43% no-ServerHello flows (sandbox VMs, dead C2); benign is 98% TLS 1.2 browsing from 2017.
   - Dedup removes 42% of rows (`all`) and 94% without timing.
   - Labels are weak and capture-level: malware captures also contain non-C2 TLS that is not on the Tranco list.
   - MCFP is best used as a training source for cross-dataset tests, not as a within-dataset benchmark.

## Benign sources available for E4 (E4 has since been run: see `SUMMARY_e4.md`)

| Source | Nature | Verified benign? |
|---|---|---|
| RAID 2024 Tranco | scripted browser visits, Jan 2024, one client configuration | yes, but one environment |
| HIKARI clean subset | background traffic from the attack pcaps, 2021–22 | per released labels (partial) |
| MTA background | infected host → popular domains, 2019–26 | no (same-host background) |
| CTU-Normal (MCFP) | real user hosts, mostly 2017 | yes (capture-level) |

## Proposed E4 pairings (train → test; run, see `SUMMARY_e4.md`)

1. **MCFP (malware + CTU-Normal) → MTA (IOC + background)**, and the reverse. Both are real Windows malware with independent labelling; this tests 2013–18 → 2019–26 transfer and sandbox → MTA environments.
2. **RAID C2 + RAID Tranco → MTA**. Tests whether a single-tool, single-environment C2 model detects real-world malware C2. The prediction is that it will not.
3. **Swap the negatives:** train MTA malicious vs CTU-Normal, test on MTA malicious vs MTA background (and vice versa). This separates "learned the malware" from "learned the benign environment".
4. **HIKARI → others:** not proposed. Its attacks are brute force, not C2, and its usable attack set is 2 hosts.

The models need feature-set intersections (MCFP/MTA/RAID share G1–G5; HIKARI only G1/G2). Run `g1g2_notime` as the primary set, because it is least tied to the capture network.
