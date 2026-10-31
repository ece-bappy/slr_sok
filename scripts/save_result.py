"""Save agent extraction results to JSON and validate structure.

After the agent codes a paper, call save_result(paper_id, run, data_dict) directly.

The JSON schema mirrors extract_v2.py field structure so vote_final.py can
process all three runs together.

Run names: 'sonnet' | 'gemini38'
"""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

SCRIPTS = Path(__file__).parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

RESULTS_DIR = ROOT / "results"

ALLOWED_VALUES = {
    "label_source": {"sandbox", "blocklist_cert", "blocklist_ja3", "ids_alerts",
                     "dataset_provided", "manual", "generated", "other", "unclear"},
    "label_feature_overlap": {"yes", "no", "unclear", "not_applicable"},
    "feature_groups": {"G1", "G2", "G3", "G4", "G5"},
    "cert_fields_read": {"yes", "no", "not_applicable"},
    "fingerprints_used": {"none", "JA3", "JA3S", "JA4", "JA4S", "other"},
    "tls_versions_stated": {"1.0", "1.1", "1.2", "1.3", "not_stated"},
    "ech_considered": {"yes", "no"},
    "split_protocols": {"random", "stratified_random", "per_packet", "host_grouped",
                        "temporal", "cross_dataset", "not_applicable", "unclear"},
    "main_split": {"random", "stratified_random", "per_packet", "host_grouped",
                   "temporal", "cross_dataset", "not_applicable", "unclear"},
    "easy_vs_hard_reported": {"yes", "no", "not_applicable"},
    "shortcut_check": {"none", "identifier_removal", "ablation", "probe", "other"},
    "granularity": {"packet", "flow", "session", "host", "unclear"},
    "cost_reported": {"none", "inference_only", "end_to_end", "unclear"},
    "code_released": {"yes", "no"},
    "data_released": {"yes", "no"},
}

REQUIRED_FIELDS = [
    "datasets_evaluated", "label_source", "label_feature_overlap",
    "features_used", "feature_groups", "cert_fields_read", "fingerprints_used",
    "tls_versions_stated", "ech_considered", "model_family",
    "split_protocols", "main_split", "easy_vs_hard_reported", "shortcut_check",
    "metrics", "granularity", "first_n_packets", "cost_reported", "hardware",
    "code_released", "data_released",
]

# Values that legitimately have no supporting quote
NO_EVIDENCE_OK = {
    "none", "not_applicable", "not_stated", "unclear", "whole flow", "", "no",
    str(["none"]), str(["not_stated"]),
}


def validate(data: dict) -> list:
    warnings = []
    fields = data.get("fields", {})
    for f in REQUIRED_FIELDS:
        if f not in fields:
            warnings.append(f"MISSING field: {f}")
            continue
        entry = fields[f]
        if not isinstance(entry, dict):
            warnings.append(f"{f}: expected dict, got {type(entry).__name__}")
            continue
        val = entry.get("value")
        ev = entry.get("evidence", "")
        # Check evidence presence (negative/absent answers don't need quotes)
        val_str = str(val).strip()
        if not ev and val_str not in NO_EVIDENCE_OK and val != ["none"] and val != ["not_stated"]:
            warnings.append(f"{f}: value={val!r} but evidence is empty")
        # Check allowed values
        if f in ALLOWED_VALUES:
            vals = val if isinstance(val, list) else [val]
            for v in vals:
                if str(v) not in ALLOWED_VALUES[f]:
                    warnings.append(f"{f}: value {v!r} not in allowed set")
    return warnings


def save_result(paper_id: str, run: str, data: dict) -> Path:
    """Save extraction result; returns path to saved file."""
    run_dir = RESULTS_DIR / run
    run_dir.mkdir(parents=True, exist_ok=True)
    out_path = run_dir / f"{paper_id}.json"

    data.setdefault("paper_id", paper_id)
    data.setdefault("run", run)
    data.setdefault("saved_at", datetime.now(timezone.utc).isoformat())
    data.setdefault("model", "claude-sonnet-4.6" if run == "sonnet" else "gemini-3.8-flash")

    warnings = validate(data)
    data["validation_warnings"] = warnings

    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    if warnings:
        print(f"  [WARN] {len(warnings)} validation warning(s):")
        for w in warnings:
            print(f"     {w}")
    else:
        print(f"  [OK] All 21 fields present and valid")

    print(f"  Saved -> {out_path}")
    return out_path


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--paper", required=True)
    ap.add_argument("--run", required=True, choices=["sonnet", "gemini38"])
    ap.add_argument("--data", required=True, help="JSON string of extraction result")
    a = ap.parse_args()
    data = json.loads(a.data)
    save_result(a.paper, a.run, data)


if __name__ == "__main__":
    main()
