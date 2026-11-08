# Task 1: grade 20 free-text extraction answers

**File:** `todo/01_free_text_grading.csv`. It holds the 20 rows of `review/coding/ensemble_validation.csv` marked "grade by hand", from the 4 blind validation papers (S2338, S1938, S1163, S2008).

**Why:** the extraction method is scored on how many answers are correct. Exact-match fields were scored automatically. Free-text fields (features used, model family, metrics and so on) can't be, so a person has to judge whether each model answer means the same as yours. These grades complete the validation numbers in the methods section.

## What each column is

- `human`: your own blind coding. It is the reference, so don't re-code it.
- `flash_lite`, `gemini38`: the two models' answers.
- Fill in: `grade_flash_lite`, `grade_gemini38`, `invented_flash_lite`, `invented_gemini38`, and `note` where useful.

## How to grade (one grade per model answer)

| Grade | Use when |
|---|---|
| `correct` | Same meaning as `human`. Different wording, abbreviations (MS = Metasploit, DR = detection rate), synonyms, extra detail or a different order are all fine. |
| `partial` | Mostly right, but it misses a main item from `human` (e.g. lists 2 of 3 feature families), or it is broader or narrower in a way that matters for the review. |
| `wrong` | A different answer: the wrong model, the wrong main method, or describes a baseline or related work instead of the paper's own method. |
| `empty` | The model gave nothing or "not reported", but `human` has a value. |

**Invented (yes / no):** write `yes` if the answer contains anything that isn't in the paper at all, even if the rest is right. Check the PDF (`papers/core/`) whenever an item looks unfamiliar. Invented values are the key safety metric; the pass rule is zero.

## Tie-break rules

1. Judge against the paper's **main method** (coding rulebook G2), not against side experiments.
2. Extra items are fine only if they really are in the paper's main method. A correct list plus one baseline model counts as `partial`.
3. Granularity differences ("time-related features" vs "flow duration, IAT") are `correct` if they describe the same set.
4. If you now think your own `human` value was wrong, grade against the paper, and say so in `note` ("human value wrong: …").

**Done:** tell Claude "grading done". Claude computes the final free-text accuracy and invented rate, and updates the validation table.
