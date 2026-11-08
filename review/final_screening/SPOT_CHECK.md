# PRISMA spot-check of LLM exclusions

- File: `spot_check_120.csv` (120 records the LLM pre-screen excluded, sampled across buckets).
- Human decisions: the `decision`, `exclusion_criterion` and `note` columns. The user confirmed on 8 Nov 2026 that these are their own decisions ("spot-check confirmed"), so they were not redone.
- Result: 120/120 exclusions confirmed. The human found no wrongly excluded record, so the LLM miss rate is 0/120 (95% one-sided upper bound about 2.5%, rule of three: 3/120).
- How to report it: the LLM pre-screen only suggested exclusions; a human checked a random sample of 120 and none were wrong.
