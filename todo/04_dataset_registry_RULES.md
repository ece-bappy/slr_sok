# Task 4: verify the dataset registry

**Why:** the review's "dataset public?" and "contains TLS?" columns come only from `review/dataset_registry.json`. One check per dataset here replaces one check per paper. Claude added 9 entries that no human has checked, and 26 dataset names in the coded papers don't map to any entry yet.

## 4a: 9 unverified entries (`todo/04a_registry_check.csv`)

For each row, open the dataset's own page (the publisher's, a university or lab page, Zenodo or GitHub; not a paper that uses it) and fill:

| Column | Allowed values / rule |
|---|---|
| `your_public` | `yes` (downloadable without asking), `on_request` (a form, e-mail or licence agreement), `no` (not available), `n/a` (not a traffic dataset, e.g. a blocklist) |
| `your_tls` | A short description of what traffic it contains, in the same style as `tls_claimed`, e.g. "DoH (HTTPS)", "mixed, TLS flows not separated", "DNS, not TLS" |
| `source_url` | The page you used |
| `ok_or_fix` | `ok` if the claimed values are right, otherwise `fix` (your values replace them) |

Rules:
- `public` is about access today, not at publication. Registration-only (like the CIC form) counts as `on_request`.
- "Contains TLS" means TLS/HTTPS records in the captures. An "encrypted" label alone (VPN, Tor, IPsec) is not TLS; say what it is.
- If a dataset is gone (dead link, withdrawn), write `no` and note the date you checked.

## 4b: 26 unmapped names (`todo/04b_unmapped_datasets.csv`)

These are dataset names as the papers wrote them. For each row, fill either:
- `maps_to_registry_name`: an existing registry entry it is the same as (e.g. "CTU" → the CTU-13 / Stratosphere entry, "CIC IoT" → CICIoT2023, if the paper confirms it), **or**
- `or_new_dataset_name`, plus `public`, `tls` and `source_url` as in 4a, if it's a real dataset not yet in the registry.

Special cases:
- **The paper's own private capture** (e.g. "Lastline Inc", "large-scale benign DoH data", browser-version rows such as "Google Chrome 81…"): write `own_capture` in `or_new_dataset_name` and `public = no`, unless the paper releases it.
- **Not a dataset** (e.g. "Ren et al. [40] traffic" with no source, or `nan`): write `not_a_dataset` and a note. Check the paper (listed in `review/synthesis/papers.csv`) if unsure.
- Several names for one thing (HTPA, HTPA-RD, HTPA-TS-n): map them all to one name.

**Done:** tell Claude "registry done". Claude merges both sheets into `dataset_registry.json` (status → `ok`) and re-runs the synthesis tables.
