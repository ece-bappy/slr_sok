# Task 6: optional and housekeeping

## 6a: CIRA-CIC-DoHBrw-2020 (optional)

The only planned dataset not yet downloaded. The CIC site requires a registration form with your name, e-mail and organisation. Claude can't fill that in for you. The benchmark is complete without it; it would add browser variety on the benign side.
- If you want it: fill in the form on the CIC dataset page, then tell Claude "DoHBrw form done" and pass on the download link you receive.
- If not: tell Claude "skip DoHBrw". It is then listed as a limitation.

## 6b: delete an unrelated file

`review/ranks/dhaka_hsc_2026_108256.pdf` sits in the project folder (untracked, unrelated to the paper). Delete it yourself, or tell Claude "delete the dhaka pdf".

## 6c: put plan.md under version control

`D:\new papers\plan.md` holds the decision record (§5.5 data decisions, §12 checklist) but is outside git, so changes have no history. Tell Claude "version plan.md" and Claude will copy it into the repo and commit it. Edit only the repo copy after that.
