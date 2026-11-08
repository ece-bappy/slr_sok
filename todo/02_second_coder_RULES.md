# Task 2: confirm the second coder

**File:** `review/coding/second_coder_14_papers.csv` (guide: `rulebooks/rulebooktask9.txt`).

**Current state:** all 295 rows are filled in (last changed 30 Oct 2026), and `review/coding/todo_for_me.csv` marks task 9 "done". The Screening session's 3 Nov status still listed "second-coder κ (needs a real person)" as open, so Claude can't tell how the sheet was filled.

**Why it matters:** Cohen's κ only means something if the second coder is an independent human who coded blind. A sheet filled by an AI model, or by you, isn't inter-rater reliability. Reporting it as such would be a methods error that reviewers can catch.

## Answer one question

Who filled `second_coder_14_papers.csv`?

- **A colleague, coding blind with the rulebook:** tell Claude "second coder confirmed: <their initials>". Claude computes κ per field and overall, and lists the disagreements for you to adjudicate.
- **An AI model, or not sure:** tell Claude. The sheet becomes an LLM-agreement check (still useful, but reported as such), and you need a colleague to code the 14 papers again.

## If a colleague has to (re)do it

- Give them only `rulebooks/rulebooktask9.txt`, `rulebooks/coding_rulebook.txt`, a blank copy of the sheet (Claude can make one) and the PDFs in `papers/core/`.
- They must not see your coding or any LLM output for those papers.
- About 6 hours for 14 papers. They fill `your_value`, `page` and `quote` for every row; `unsure` plus a note is allowed.
- Disagreements are then adjudicated by you, with the paper open, after κ is computed (never before).
