# Remaining datasets: survey and proposed subset (27 Oct 2026)

Nothing below has been downloaded yet. Sizes come from the sources' own listings or APIs unless marked *estimate*.
Space on A2 `/data`: 493 GB free (HIKARI and RAID 2024 already downloaded and verified).

| Source | What is there | Size | Access / terms | Proposed subset | Subset size |
|---|---|---|---|---|---|
| Stratosphere MCFP, malware captures | 400 indexed captures (2009–2020); 377 have listings, 211 have a Zeek `ssl.log` | 211 TLS captures = 201 GB of pcap (single captures up to 61 GB) | Open HTTP directory, no login; no terms file at top level | TLS captures with pcap ≤ 2 GB, 2013–2018 (the "old" slice for E3/E9) | ≈ 40 GB |
| Stratosphere MCFP, Normal + Mixed | 26 Normal, 10 Mixed folders | Normal with TLS ≈ 8 GB; Mixed ≈ 19 GB | Same | All Normal captures that have TLS (benign from the same environment); Mixed optional | ≈ 8 GB |
| Malware-Traffic-Analysis.net | 2,436 posts (2013–2026; 54 in 2024, 52 so far in 2026) | Sample post: pcap zip 12.6 MB, IOC text 2.8 kB | Open; password-protected zips; no explicit bulk-download terms; the site disclaims responsibility | pcap zip + IOC text only (never the malware-artifact zips), 2019–2026 first (≈ 780 posts), older years only if needed | *estimate* 10–15 GB (2019–2026) |
| CESNET-TLS22 (optional) | Flow CSV with first-30-packet sequences, not pcaps | 9.48 GB zip (42 GB uncompressed) | Zenodo 10610895, CC-BY-4.0 | Only if we run the packet-sequence side check | 9.5 GB (+42 GB unpacked) |
| CIRA-CIC-DoHBrw-2020 (benign part) | Chrome + Firefox benign HTTPS/DoH pcaps (≈ 49 M packets) and DoH tunnel pcaps | Not listed publicly | **Download needs the CIC registration form (name, e-mail, organisation)**: the user must fill it in; redistribution allowed with citation | Benign Chrome/Firefox pcaps only | unknown until the form is filled |

**Total for the proposed subset:** about 60–75 GB without CESNET, about 110–125 GB with CESNET unpacked. That fits comfortably on `/data`.

Notes
- Malware pcaps (MTA, MCFP) contain live malicious traffic and payloads. They are stored only on A2 `/data` and processed only by Zeek/NFStream/dpkt, never opened or executed. Malware-binary archives are not downloaded.
- MTA labelling uses the IOC files (C2 domains/IPs), not certificates or JA3, as required by plan §5.1 (avoids label circularity, E5b).
- A2 reboots every night at about 01:48, which kills downloads. `fetch.sh` resumes, but it has to be restarted after each reboot (manually, or with an `@reboot` cron entry if the user approves that standing change on A2).
- Tables: `mcfp_sizes.csv` (malware captures: pcap bytes, ssl.log bytes), `mcfp_normal_sizes.csv` (Normal/Mixed).
