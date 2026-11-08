# Task brief for agy: code two checklist fields for 67 papers

You are the second, independent coder for a systematic review. Another model has already coded the same fields; you must work **blind**: do not open anything under `review/checklist_coding/` except this brief and `paper_ids.txt`, and do not open `review/synthesis/`.

## Rules

- **No shell.** Do not run any commands or scripts. Use only file reading and writing.
- Write **only** the output files described below. Do not change any other file.
- Read the rulebook first and apply it exactly: `review/coding/checklist_rulebook.txt`.

## Input

- Paper list: `review/checklist_coding/paper_ids.txt`, 67 ids, one per line.
- Paper text: `results/sonnet/<id>.txt`, the cleaned full text of each paper. Use only this text.

## What to do, for each id in `paper_ids.txt`

1. If `results/checklist_agy/<id>.json` already exists, **skip** that paper. Three are done: S0066, S0095, S3347.
2. Read `results/sonnet/<id>.txt` and decide the two fields from the rulebook:
   - `tuning_data`: `validation`, `test` or `not_stated`
   - `per_tls_version`: `yes` or `no`
3. Write `results/checklist_agy/<id>.json` containing only this JSON:

```json
{
  "tuning_data": {"value": "validation|test|not_stated", "evidence": "<one verbatim passage>"},
  "per_tls_version": {"value": "yes|no", "evidence": "<one verbatim passage>"}
}
```

- Use one value per field, exactly as spelled above.
- `evidence` is one passage of at most about 40 words, copied **character for character** from the paper text: no "...", no paraphrase. Use `""` only when the value is `not_stated` or `no`.
- Code the paper's own main method (rulebook G2), not related work or baselines.
- Decide each paper on its own. Don't reuse a decision from another paper.

## Reminders from the rulebook

- `validation` needs the paper to **say** that a validation set, validation fold, inner cross-validation or held-out part of the training data was used for tuning. "We tuned the hyperparameters" without saying on what data = `not_stated`. A default 0.5 threshold with no tuning stated = `not_stated`.
- `test` = tuned, early-stopped or selected on the data the headline result is reported on, or the best of several test runs.
- `per_tls_version = yes` needs **separate results** by TLS version, or an evaluation explicitly restricted to TLS 1.3. Just stating which TLS versions the data contains = `no`. A breakdown by protocol (TLS vs QUIC vs DoH) = `no`.

## When finished

Reply with: the number of JSON files written, any ids you skipped or could not code (and why), and nothing else. Claude then validates the files and builds the comparison.
