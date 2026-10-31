"""Vote across 3 runs and produce final verified values for the CSV.

Runs:
  - gemini_lite: the original llm_draft_value from core_67_papers_verification.csv
  - sonnet:      results/sonnet/<paper_id>.json  (this agent's run)
  - gemini38:    results/gemini38/<paper_id>.json (Gemini 3.8 run)

Voting logic:
  - For scalar fields: majority of 3; if all differ, use sonnet (most recent strong model).
  - For list fields: union with majority-endorsed items (item kept if ≥2 runs have it).
  - Records which runs agreed (vote_count) and disagreements.

Output:
  results/vote/<paper_id>.json           <- per-paper voted result
  review/coding/core_67_papers_verification_voted.csv  <- full updated sheet
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

SCRIPTS = Path(__file__).parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

CSV_IN  = ROOT / "review" / "coding" / "core_67_papers_verification.csv"
CSV_OUT = ROOT / "review" / "coding" / "core_67_papers_verification_voted.csv"
RESULTS_DIR = ROOT / "results"

SCALAR_FIELDS = [
    "label_feature_overlap", "cert_fields_read", "ech_considered", "model_family",
    "main_split", "easy_vs_hard_reported", "granularity", "first_n_packets",
    "cost_reported", "hardware", "code_released", "data_released",
]
LIST_FIELDS = [
    "datasets_evaluated", "label_source", "features_used", "feature_groups",
    "fingerprints_used", "tls_versions_stated", "split_protocols",
    "shortcut_check", "metrics",
]

UNCERTAIN = {"unclear", "not_stated", "none", "not_applicable", "", None}


def load_gemini_lite_values(df: pd.DataFrame, paper_id: str) -> dict:
    """Extract the existing llm_draft_value from the CSV for a paper."""
    paper_rows = df[df["paper_id"] == paper_id]
    result = {}
    for _, row in paper_rows.iterrows():
        field = row["field"]
        val = row["llm_draft_value"]
        evidence = row["llm_evidence_quote"] if pd.notna(row["llm_evidence_quote"]) else ""
        result[field] = {"value": val, "evidence": evidence, "source": "gemini_lite"}
    return result


def normalize_list_val(val):
    """Normalize a list value from any run format."""
    if isinstance(val, list):
        return [str(v).strip() for v in val if str(v).strip()]
    if isinstance(val, str):
        # Handle semicolon-separated strings from gemini_lite CSV
        parts = [p.strip() for p in re.split(r"[;,]", val) if p.strip()]
        return parts
    return []


def vote_scalar(values: list) -> tuple[str, int]:
    """Return (majority_value, vote_count). Ties go to sonnet."""
    non_empty = [str(v).strip() for v in values if str(v).strip() not in {"", "nan", "None"}]
    if not non_empty:
        return "unclear", 0
    c = Counter(non_empty)
    best_val, best_count = c.most_common(1)[0]
    return best_val, best_count


def vote_list(values_by_run: list[list]) -> tuple[list, int]:
    """Return (voted_list, min_agreement). Item kept if present in ≥2 runs."""
    if len(values_by_run) <= 1:
        return values_by_run[0] if values_by_run else [], 1
    # Collect all unique items and count how many runs mention each
    item_counts = Counter()
    all_items_ordered = []
    seen = set()
    for lst in values_by_run:
        for item in lst:
            item_counts[str(item).strip()] += 1
            if str(item).strip() not in seen:
                all_items_ordered.append(str(item).strip())
                seen.add(str(item).strip())
    # Keep if ≥2 runs, or keep all if no clear majority
    threshold = 2 if len(values_by_run) >= 2 else 1
    voted = [item for item in all_items_ordered if item_counts[item] >= threshold]
    if not voted:
        voted = all_items_ordered  # fallback: keep all
    min_agreement = min(item_counts[i] for i in voted) if voted else 0
    return voted, min_agreement


def vote_paper(paper_id: str, df: pd.DataFrame) -> dict:
    """Vote across 3 runs for one paper. Returns dict of field -> voted result."""
    # Load all 3 run sources
    gemini_lite = load_gemini_lite_values(df, paper_id)

    sonnet_path = RESULTS_DIR / "sonnet" / f"{paper_id}.json"
    gemini38_path = RESULTS_DIR / "gemini38" / f"{paper_id}.json"

    sonnet = json.loads(sonnet_path.read_text(encoding="utf-8"))["fields"] if sonnet_path.exists() else {}
    gemini38 = json.loads(gemini38_path.read_text(encoding="utf-8"))["fields"] if gemini38_path.exists() else {}

    available_runs = {"gemini_lite": gemini_lite}
    if sonnet: available_runs["sonnet"] = sonnet
    if gemini38: available_runs["gemini38"] = gemini38

    n_runs = len(available_runs)
    voted = {}

    all_fields = set(gemini_lite.keys()) | set(sonnet.keys()) | set(gemini38.keys())

    for field in all_fields:
        vals_by_run = {}
        for run_name, run_data in available_runs.items():
            entry = run_data.get(field, {})
            if isinstance(entry, dict):
                vals_by_run[run_name] = entry.get("value"), entry.get("evidence", "")
            else:
                vals_by_run[run_name] = str(entry), ""

        if field in LIST_FIELDS:
            lists = [normalize_list_val(v) for v, _ in vals_by_run.values()]
            voted_val, agree = vote_list(lists)
            # Pick best evidence from the run with most agreement
            best_ev = ""
            for run_name, (v, ev) in vals_by_run.items():
                if ev and not best_ev:
                    best_ev = ev
            voted[field] = {
                "value": "; ".join(voted_val) if voted_val else "none",
                "evidence": best_ev,
                "vote_agreement": f"{agree}/{n_runs}",
                "runs": {r: str(v) for r, (v, _) in vals_by_run.items()},
            }
        else:
            scalar_vals = [str(v) for v, _ in vals_by_run.values()]
            voted_val, agree = vote_scalar(scalar_vals)
            # Get evidence from the winning run
            best_ev = ""
            for run_name, (v, ev) in vals_by_run.items():
                if str(v) == voted_val and ev:
                    best_ev = ev
                    break
            if not best_ev:
                best_ev = next((ev for _, (_, ev) in vals_by_run.items() if ev), "")
            voted[field] = {
                "value": voted_val,
                "evidence": best_ev,
                "vote_agreement": f"{agree}/{n_runs}",
                "runs": {r: str(v) for r, (v, _) in vals_by_run.items()},
            }

    return {"paper_id": paper_id, "n_runs": n_runs, "fields": voted}


def update_csv(vote_results: list[dict]) -> pd.DataFrame:
    """Update the verification CSV with voted values."""
    df = pd.read_csv(CSV_IN)

    for result in vote_results:
        pid = result["paper_id"]
        fields = result["fields"]
        for field, info in fields.items():
            mask = (df["paper_id"] == pid) & (df["field"] == field)
            if not mask.any():
                continue
            voted_val = info["value"]
            agree = info.get("vote_agreement", "?")
            runs = info.get("runs", {})
            runs_str = " | ".join(f"{r}={v}" for r, v in runs.items())

            df.loc[mask, "verified_value"] = voted_val
            df.loc[mask, "user_note"] = f"3-model vote ({agree}): {runs_str}"
            df.loc[mask, "verification_status"] = "voted"
            # Keep evidence from the best run
            best_ev = info.get("evidence", "")
            if best_ev and (df.loc[mask, "user_quote"].isna().all() or
                            df.loc[mask, "user_quote"].eq("").all()):
                df.loc[mask, "user_quote"] = str(best_ev)[:500]

    df.to_csv(CSV_OUT, index=False)
    print(f"Updated CSV saved to: {CSV_OUT}")
    return df


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--paper", default=None, help="Vote single paper (default: all available)")
    ap.add_argument("--update-csv", action="store_true", help="Write voted values to CSV")
    a = ap.parse_args()

    df = pd.read_csv(CSV_IN)
    paper_ids = [a.paper] if a.paper else df["paper_id"].unique().tolist()

    results = []
    for pid in paper_ids:
        sonnet_done = (RESULTS_DIR / "sonnet" / f"{pid}.json").exists()
        gemini38_done = (RESULTS_DIR / "gemini38" / f"{pid}.json").exists()
        if not (sonnet_done or gemini38_done):
            continue
        result = vote_paper(pid, df)
        out = RESULTS_DIR / "vote" / f"{pid}.json"
        out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        results.append(result)
        n = result["n_runs"]
        print(f"{pid}: voted across {n} runs → {out.name}")

    print(f"\nTotal voted: {len(results)}")
    if a.update_csv and results:
        update_csv(results)


if __name__ == "__main__":
    main()
