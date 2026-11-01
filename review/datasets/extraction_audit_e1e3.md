# E1–E3 extraction audit (A2, 1 Nov 2026)

Run: `scripts/launch_e1e3_extract.sh`, 14:55–15:33 A2 time, 6 workers. 2,064 pcaps, 0 failures.
Output: `/data/tls-sok/out/<dataset>/` (per-pcap folders + `manifest.csv`), 5.5 GB.

| Dataset | pcaps | Input GB | TCP flows | TLS flows (ClientHello) | with ServerHello | with certificate | TLS 1.2 | TLS 1.3 | Handshake features |
|---|---|---|---|---|---|---|---|---|---|
| RAID MS (Metasploit C2) | 48 | 6.5 | 791,226 | 791,226 | 791,226 | 396,325 | 396,325 | 394,901 | all 48 pcaps |
| HIKARI benign | 6 | 0.4 | 86,150 | 0 | 0 | 0 | — | — | none: header-only (all 6 flagged) |
| HIKARI attacks | 10 | 26.9 | 2,714,665 | 1,557,126 | 1,547,882 | 558,581 | 558,654 | 989,227 | all 10 pcaps |
| RAID Tranco (benign) | 2,000 | 32.4 | 565,848 | 503,087 | 450,127 | 223,960 | 226,322 | 223,742 | all 2,000 pcaps |

Join quality: Zeek–NFStream flow match per pcap ≥ 0.93 (median 0.97–1.00); TLS rows joined to flows 100% in every pcap.
TLS 1.0 appears only in RAID Tranco (63 flows) and HIKARI attacks (1). No truncated pcaps in these datasets (that issue is MCFP only).

Points for E1–E3 design
- Certificates appear only in TLS 1.2 flows (TLS 1.3 encrypts them), so certificate features (G4) are TLS 1.2-only by construction.
- HIKARI: benign traffic has no TLS records at all, while attacks do. Any handshake feature would separate the classes by "capture has payload"; use G1/G2 only (or attacks-only), and use it as the shortcut example in E5b. The classes are also very unbalanced: 86k benign vs 2.7M attack TCP flows.
- RAID: 791k C2 flows vs 503k benign TLS flows; every RAID MS TCP flow is a TLS flow (the captures are C2 sessions only).
- RAID Tranco: 52,960 TLS flows (10.5%) have a ClientHello but no ServerHello (failed or incomplete handshakes); decide whether to keep them before E1.
