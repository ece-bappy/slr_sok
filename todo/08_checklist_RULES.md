# Task 8: decide the disputed checklist codes

**Why:** two checklist items in Section 8.2 (Figure 12) had no coded data. Flash Lite and Gemini 3.8 coded them blind for the 67 core papers, from the same rulebook: `rulebooks/checklist_rulebook.txt` (also at `review/coding/checklist_rulebook.txt`).

| Field | Checklist item | Values |
|---|---|---|
| `tuning_data` | C2: tuning decisions made without the test set | `validation` / `test` / `not_stated` |
| `per_tls_version` | C6: results reported by TLS version | `yes` / `no` |

## What to do

**File:** `todo/08_checklist_review.csv`. The `DISPUTED` rows come first, followed by the agreed rows.

- **DISPUTED rows:** open the paper (`pdf` column, relative to `D:\new papers`), check both models' evidence, and write the correct value in `your_value`. Add a reason in `your_note` if it isn't obvious.
- **Agreed rows:** leave `your_value` empty to accept the agreed value. Write a value there only if you notice an agreed answer is wrong.
- `False` in `quotes_verified` also appears when a model gave no quote, which is allowed for `not_stated` / `no`.
- `quotes_verified` shows whether each model's quote was found in the paper text (Flash Lite / Gemini 3.8). An answer whose quote wasn't found deserves a closer look.

Rules: decide from the paper and the rulebook. The key points:
- `tuning_data = validation` needs the paper to **say** a validation split or inner fold was used. Default settings or "we tuned it" without saying on what data = `not_stated`.
- `per_tls_version = yes` needs **separate results** by TLS version, or an evaluation explicitly restricted to TLS 1.3. Just stating which versions are in the data = `no`.

**Done:** tell Claude "checklist done". Claude merges the sheet, recomputes the checklist scores with all 8 items, and updates the figure data.
