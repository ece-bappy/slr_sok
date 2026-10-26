# Coding rules

Screening log: `screening_log.csv`, one row per record after deduplication.

- `stage`: `title_abstract` or `full_text`
- `decision`: `include`, `exclude`, `maybe`
- `exclusion_reason`: `decryption`, `benign_only`, `non_tls`, `secondary`, `no_ml`, `out_of_range`, `no_eval`, `duplicate`
- `agree`: filled only for the 20% double-coded sample (`yes`/`no`); report Cohen's kappa from these rows

Extraction form: `extraction_form.csv`, one row per included study.

| Field | Values |
|---|---|
| `label_source` | `sandbox`, `blacklist_cert`, `blacklist_ja3`, `ids_alert`, `manual`, `synthetic_attack`, `unknown` |
| `label_feature_overlap` | `yes` if a feature uses the same signal as the label source (e.g. certificate features with SSLBL labels) |
| `feature_groups` | semicolon list of `G1`..`G5` (see `../../plan.md` §5.2) |
| `feature_visibility_tier` | weakest tier at which all used features remain visible: `tls12`, `tls13`, `tls13_ech` |
| `split_protocol` | `random`, `temporal`, `host_grouped`, `cross_dataset`, `mixed`, `unclear` |
| `granularity` | `packet`, `flow`, `session`, `host` |
| `cost_reported` | `none`, `inference_only`, `end_to_end` |
| booleans | `yes` / `no` / `unclear` |

Rules: a human makes every include/exclude decision; AI suggestions go in `notes` only.
