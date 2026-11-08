# Batch 6 item 12: host-level alerting on MTA E3 (8 Nov 2026)

`run_b6.py hosts`, launched in `launch_batch6e.sh` (A2, 8 Nov 14:53–14:54 WITA; exit 0). XGBoost, MTA E3 (≤2022 → 2023–26), 5 seeds. CSVs are in `b6_hosts/`.

**Setup:**
- Flow scores from the E3 model are aggregated per source host (pcap × client IP), per **1-hour window** and per **pcap**.
- Aggregates: the maximum flow score, and the mean of the top 3.
- A unit is positive if it holds at least one malicious flow.
- An alert fires when the aggregate reaches the flow-level threshold chosen on validation: FPR 10⁻³ (strict), or max-F1.
- Reported: unit detection rate, false-alarm rate on negative units, and false alarms per benign host-day (negative 1-h windows × 24 / their number).

**What the test set allows (`census.json`):**
- 12,882 test flows in 173 pcaps from 174 hosts; 129 hosts have malicious flows and **only 45 hosts are benign-only**.
- 381 host-hours, of which 254 contain malicious flows and **127 are benign** (≈ 5.3 benign host-days).
- So **one false alarm ≈ 0.19 per benign host-day**, and zero observed false alarms is still compatible with up to ≈ 0.57 per host-day (95% upper bound, 3 / 5.3).
- Another 5,388 benign flows sit on infected hosts and cannot contribute to a host-level false-alarm rate.
- MTA is one infected sandbox host per pcap, so it is a weak basis for host-level false alarms. The numbers below are indicative.

## Results (mean over 5 seeds; aggregate = max)

| Features | Threshold | Flow FPR | Infected host-hours flagged | Benign host-hours flagged | **False alarms per benign host-day** | Infected hosts flagged (per pcap) | Benign hosts flagged |
|---|---|---|---|---|---|---|---|
| G1–G5 | val FPR 10⁻³ | 1.2% | 70% | 10.4% | **2.5** | 53% | 11% |
| G1–G5 | val max-F1 | 2.6% | 79% | 16% | 3.9 | 66% | 16% |
| **No G5** | **val FPR 10⁻³** | 0.2% | **60%** | **0%** | **0 (< 0.57)** | **50%** | **0%** |
| No G5 | val max-F1 | 0.9% | 80% | 1.1% | 0.27 | 68% | 0% |
| G1+G2 (ECH tier) | val FPR 10⁻³ | 0.3% | 58% | 0.2% | 0.04 | 42% | 0% |
| G1+G2 | val max-F1 | 9.4% | 90% | 13% | 3.1 | 86% | 15% |

The top-3 mean lowers both rates: no G5 at FPR 10⁻³ flags 52% of infected host-hours and 38% of infected hosts, again with 0 false alarms. For G1–G5 it brings false alarms to 1.0 per host-day.

## Findings
1. **Operational reading of the flow results.** At the strict threshold, the no-G5 model flags 60% of infected host-hours and half of the infected hosts, with **no false alarm in 127 benign host-hours** (≤ 0.57 per host-day at 95%).
2. **The hash model's extra detections cost false alarms.** G1–G5 flags 70% of infected host-hours, but also 10% of benign host-hours: 2.5 false alarms per benign host per day. Its validated flow threshold does not hold on 2023–26 traffic (flow FPR 1.2% against the 0.1% target).
3. **The ECH tier is quiet but misses more:** 58% of infected host-hours and 42% of hosts at the strict threshold, with ≈ 0.04 false alarms per host-day. At max-F1 it flags 90% of infected hours, but at 3.1 false alarms per host-day.
4. **Per-pcap (whole-capture) detection is lower than per-hour detection** (50% vs 60% for no G5), because hours are weighted by the long, easy captures. Half the infected hosts never cross the strict threshold in any flow.

## Caveats
- Small benign denominator (45 hosts, 127 host-hours); MTA is sandbox traffic with one infected host per capture, so host-level false alarms here are not an enterprise estimate. The base-rate analysis (item 1, `SUMMARY_b6_baserate.md`) gives the flow-level counterpart.
- Thresholds are flow-level thresholds from validation; a host-level threshold tuned on validation hosts could trade differently.
- Time windows use flow start times; flows spanning windows count in their start hour.
