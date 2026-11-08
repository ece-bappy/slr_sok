# Task 7: check the map labels for the 291 included papers

**Why:** section 4.1 and Figure 3 map all 291 papers by threat (task), study type and model class. Two models labelled every paper blind from its title and abstract, using the same rulebook. Where they agree, the label is accepted. You decide every label where they disagree, plus a 30-paper spot check of agreed labels so we can report how often agreed labels are wrong.

**File:** `todo/07_map_labels.csv`. Rules: `review/coding/map_label_rulebook.txt` (copy in `rulebooks/`).

## What to do

Each row is one field of one paper:
- `why_here` = `disputed` (the models disagree) or `spot_check` (they agree; check it anyway).
- `flash_lite`, `gemini38`: the two suggestions, with each model's reason.
- `title`, `abstract`: what to judge from. Don't open the PDF; the map is title/abstract-based by design.

Fill `my_label` with the correct value from the rulebook's list, even if it equals one of the suggestions. Use `note` for anything odd (e.g. a rule that didn't fit).

Allowed values:
- **task:** c2_botnet, doh_tunnel, web_attack, dos, malicious_server, malware, multi_attack, anomaly, other
- **study_type:** detection, evasion, evaluation, system
- **model_class:** classical_ml, deep_learning, transformer, llm, graph, hybrid, unclear

## Two patterns cover 41 of the 119 disputes

- **task: malware vs other (17 rows).** Mostly general "encrypted traffic classification" papers. Rule T1: "malicious encrypted traffic" with no narrower threat → `malware`. Keep `other` only when the abstract names a threat outside the list (e.g. I2P/darknet traffic, data exfiltration) or no threat at all; say which in `note`.
- **model_class: classical_ml vs unclear (24 rows).** Usually the abstract says only "machine learning". The rulebook says `unclear` when the abstract doesn't name the model, so pick `classical_ml` only if a classical model is actually named.

If a rule turns out ambiguous, tell Claude. It gets a dated rule in the rulebook, as with R1.

**Done:** tell Claude "map labels done". Claude merges the labels, reports the spot-check error rate, and draws Figure 3.
