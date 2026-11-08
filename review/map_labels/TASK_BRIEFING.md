# Task briefing for agy: label 286 papers for the systematic map

You are the second, independent judge in a two-model labelling ensemble for a systematic review.
Work ONLY from the files named here. Your labels are compared with another model's afterwards, so
independence matters more than speed.

## Files

| Role | Path (relative to `D:\new papers\tls-sok`) |
|---|---|
| Rules (read fully first, apply exactly) | `review/coding/map_label_rulebook.txt` |
| Input: 286 papers, one JSON object per line (`id, year, venue, title, abstract`) | `review/map_labels/input_remaining.jsonl` |
| Output: APPEND your labels here | `review/map_labels/gemini38.csv` |

## Hard rules

1. **Do not open** `review/map_labels/flash_lite.csv`, `review/map_labels/*.log`, `todo/07_*`, or any other
   labels, screening or coding files. Use only the rulebook and the input file.
2. **Label every paper yourself by reading its title and abstract.** Do not write or run a script that
   assigns labels by keywords, regexes or another model. A script may only read the input and append
   rows you have already decided.
3. **Do not edit or delete** any file except appending to `review/map_labels/gemini38.csv`. Do not touch
   its header or the 5 rows already in it (S0041, S0044, S0066, S0074, S0090).
4. No internet, no other tools, no other models.

## Output format

`gemini38.csv` already has this header; append one row per paper, same order as the input:

```
id,task,study_type,model_class,reason,judge
```

- `task`: c2_botnet | doh_tunnel | web_attack | dos | malicious_server | malware | multi_attack | anomaly | other
- `study_type`: detection | evasion | evaluation | system
- `model_class`: classical_ml | deep_learning | transformer | llm | graph | hybrid | unclear
- `reason`: at most 20 words from the abstract; wrap it in double quotes, and double any `"` inside it
- `judge`: exactly `agy/gemini-3.8-flash-high`

Use exactly these lowercase values, nothing else. One row per id, no blank lines, UTF-8.

## How to work

- Work in chunks of about 20 papers: read them, decide, append the 20 rows, then continue.
  This keeps progress safe if the session stops; on restart, skip ids already in `gemini38.csv`.
- Apply the tie-breaks (T1–T4, M1–M4) in the rulebook. When unsure between two values, pick the one
  the rulebook's tie-break gives; do not invent new values.
- When all 286 are done, report: the number of rows appended, and any ids you found hard (with one line why).

Done = `gemini38.csv` has 291 data rows (5 existing + 286 new), every id from the input exactly once.
