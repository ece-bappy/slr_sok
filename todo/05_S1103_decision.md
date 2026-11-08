# Task 5: decide record S1103

**Record:** S1103, *Application of Graph Alignment Double Layer Attention Mechanism in Detecting Malicious Traffic in TLS/SSL Encryption* (Advances in Computer and Communication, 2025).

**Abstract in short:** proposes a graph-attention method for "malicious traffic detection in TLS/SSL encryption". Its only evaluation is on **ISCX VPN-nonVPN 2016** (98.3% accuracy). That dataset has VPN and application classes and no malicious class.

**What the judges said** (same strict prompt, sanity check of 15 records):

| Judge | Decision |
|---|---|
| Claude reference | maybe (needs full text) |
| Claude subagent, blind | exclude, non_tls |
| agy (Gemini 3.8 Flash) | exclude, non_tls |
| Gemini 3.1 Flash Lite | include |

**The rule that decides it** (screening rulebook, inclusion criterion 3): the evaluation data must actually contain TLS/encrypted *malicious* traffic. VPN/app classification datasets such as ISCX VPN-nonVPN don't count unless the paper isolates malicious TLS flows.

**Recommendation:** exclude (non_tls). The title claims malicious-TLS detection, but the evaluation can't measure it.

**Your decision:** write it here, or just tell Claude "S1103: include / exclude / maybe".

Decision: exclude
Note: non_tls; evaluates only on ISCX VPN-nonVPN 2016 which lacks malicious TLS traffic (per screening rulebook section 3, criterion C3 / code non_tls)
