# Task 3: confirm or redo the PRISMA spot-check

**File:** `review/final_screening/spot_check_120.csv` (rules: `rulebooks/screening_rulebook.txt`).

**What it is:** 120 random records the LLM pre-screening excluded (about 60 from bucket C, "Gemini strict excluded", and 60 from bucket D, "Gemma excluded"), re-screened by a human. The share a human would have included is the pre-screening's **miss rate**, which the PRISMA methods section must report.

**Current state:** every row has `decision = exclude`, and the notes read like "LLM exclusion confirmed: …". The file was last changed on 28 Oct, and `review/coding/todo_for_me.csv` marks it done, but the Screening session still listed it as yours on 3 Nov.

## Answer one question

Did you make these 120 decisions yourself, from the title and abstract?

- **Yes:** tell Claude "spot-check confirmed". The reported miss rate is then 0/120 (95% upper bound ≈ 2.5%).
- **No, or not sure:** redo it as below. A miss rate checked only by the model that made the exclusions is not a valid check.

## How to (re)do it

1. Hide the columns `gemma`, `gemma_reason`, `gemini_strict`, `gemini_criterion`, `gemini_reason`, `decision`, `exclusion_criterion` and `note` before you start, so the LLM's view doesn't anchor you.
2. For each record, read the title and `abstract` (open `doi` / `oa_url` if the abstract is missing). Apply the screening rulebook exactly:
   - **include** only if every inclusion criterion is clearly met;
   - **exclude** with the first exclusion code that applies;
   - **maybe** if one key criterion can't be determined from the abstract.
3. Write your answers in new columns `my_decision`, `my_criterion` and `my_note`. Don't overwrite the old columns, so both stay auditable.
4. A missing abstract is never a reason to exclude (rulebook rule).
5. Any `include` or `maybe` is a miss. Claude will check whether those papers belong in the review.

About 2–3 hours. Then tell Claude "spot-check redone".
