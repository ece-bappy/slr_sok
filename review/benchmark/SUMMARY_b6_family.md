# Batch 6 item 7: leave-one-family-out on MTA (8 Nov 2026)

`run_b6.py family`, launched in `launch_batch6.sh` (A2, 8 Nov 14:20–14:24 WITA; exit 0). XGBoost, 5 seeds. CSVs are in `b6_family/` (`pcap_family.csv` holds the label of every pcap).

## Family labels (no new downloads)
- **Source.** Each MTA pcap is labelled from its own title (e.g. `2026-01-14-…-Lumma-Stealer…`) against a fixed list of 44 family names and aliases (`run_b6.py` `FAMILIES`).
- **Coverage.** Of 371 pcaps with malicious flows:
  - **200** name exactly one family and are used;
  - **129** name two or more (e.g. "IcedID with Cobalt Strike"), so their flows cannot be attributed and are excluded;
  - **42** name none and are excluded.
- **Reliability.** The labels are the MTA author's own identification in the title. Two-family titles are the main ambiguity and are dropped rather than guessed. Follow-up malware *not* named in a title would be a label error we cannot detect.
- **Held-out families.** The 14 families with at least 5 posts. ZLoader (5 posts) was skipped, because its held-out set had a single class. 13 are reported.
- **Split.** All flows of the held-out family's pcaps (malicious and their same-host background) form the test set. Every post containing a pcap of that family is removed from training. Training and validation use the other single-family pcaps only (85/15 stratified).

## Results (mean over 5 seeds)

Recall on the held-out family's malicious flows at the validation max-F1 threshold ("recall") and at the validation-FPR-10⁻³ threshold ("TPR@10⁻³"), plus recall on the same posts' background flows ("benign recall").

| Held-out family (posts; malicious flows) | Recall, G1–G5 | Recall, no G5 | TPR@10⁻³, G1–G5 | TPR@10⁻³, no G5 | Benign recall, G1–G5 / no G5 | ROC, G1–G5 / no G5 |
|---|---|---|---|---|---|---|
| IcedID (40; 993) | **0.43** | **0.99** | 0.24 | 0.96 | 0.99 / 0.98 | 0.97 / 1.00 |
| Lumma (11; 1,356) | **0.49** | **0.90** | 0.21 | 0.42 | 0.97 / 0.99 | 0.96 / 1.00 |
| Cobalt Strike (6; 419) | 0.63 | 0.98 | 0.57 | 0.95 | 1.00 / 0.99 | 0.97 / 1.00 |
| Ursnif (15; 195) | 0.82 | 0.99 | 0.41 | 0.99 | 1.00 / 0.97 | 1.00 / 1.00 |
| Gootloader (5; 258) | 0.57 | 0.72 | 0.35 | 0.57 | 1.00 / 1.00 | 0.99 / 0.99 |
| ClickFix (5; 20) | 0.35 | 0.57 | 0.23 | 0.39 | 0.97 / 0.99 | 0.83 / 0.97 |
| DarkGate (6; 10) | 0.26 | 0.42 | 0.18 | 0.30 | 1.00 / 1.00 | 0.92 / 0.98 |
| Qakbot (17; 1,003) | 0.98 | 0.99 | 0.90 | 0.98 | 0.84 / 0.93 | 0.97 / 0.99 |
| Dridex (12; 147) | 0.98 | 1.00 | 0.92 | 0.99 | 1.00 / 1.00 | 1.00 / 1.00 |
| Trickbot (7; 208) | 0.99 | 1.00 | 0.99 | 1.00 | 0.99 / 1.00 | 1.00 / 1.00 |
| BazarLoader (5; 199) | 0.99 | 1.00 | 0.99 | 0.99 | 1.00 / 0.99 | 1.00 / 1.00 |
| Hancitor (7; 1,994) | 1.00 | 1.00 | 1.00 | 1.00 | **0.99 / 0.94** | 1.00 / 1.00 |
| Emotet (13; 979) | 1.00 | 1.00 | 0.99 | 0.99 | **0.82 / 0.66** | 1.00 / 1.00 |

## Findings
1. **Unseen families are where the fingerprint model fails.**
   - With G1–G5, recall on a never-seen family drops to 0.26–0.63 for 6 of 13 families (IcedID, Lumma, Cobalt Strike, Gootloader, ClickFix, DarkGate).
   - Without G5, the same families reach 0.42–0.99. Detection improves for 10 of 13 families and is never worse by more than 0.003.
   - At the strict operating point (TPR at val-FPR 10⁻³) the gap is larger: IcedID 0.24 → 0.96, Ursnif 0.41 → 0.99.
2. **The no-G5 model pays on the background of two families.** Emotet posts' benign recall is 0.82 → 0.66, and Hancitor's 0.99 → 0.94. Those posts' background traffic resembles other families' C2 in flow and handshake terms.
3. **Some families are hard regardless.** ClickFix (20 malicious flows) and DarkGate (10) stay below 0.6 recall. They are small and recent (2024–26), and both are delivery chains rather than one C2 protocol.
4. **This is the family-level version of the E3/E9 result:** a hash-based model recognises the families it has seen; flow and handshake features generalise to new ones.

## Caveats
- Labels come from titles; 35% of malicious pcaps are excluded as two-family titles, which removes many IcedID/Qakbot-plus-Cobalt-Strike chains.
- Small families (ClickFix, DarkGate) have 10–20 malicious test flows: read their recall as indicative.
- Background flows in a held-out post are from the same infected host, so benign recall here is a same-host false-positive rate, not an enterprise one.
