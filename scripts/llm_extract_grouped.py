"""Field-group extraction with a fixed answer schema and a checking pass (Gemini API).

Evidence must be one verbatim passage; answers whose quote matches the paper text below
QUOTE_MATCH_FLAG, spliced quotes ("...") and answers changed by the check carry review_flags.

For one paper: 5 calls, each filling one group of extraction-form fields under a JSON schema
that restricts categorical fields to their allowed values, then 1 checking call that sees all
draft answers with their evidence quotes and either keeps or corrects each one.

Usage: python scripts/llm_extract_grouped.py PAPER.pdf OUT.json [--model gemini-3.1-flash-lite]
Writes OUT.json (checked answers) and OUT with "__draft" inserted before the run tag
(e.g. P01__grp_r1.json -> P01__grpdraft_r1.json) holding the pre-check answers, so both can be
scored with llm_flag.py.
"""
import argparse
import json
import re
import time
from pathlib import Path

from llm_extract import FIELDS, call_gemini, clean_text, norm, quote_found
from pdf_sections import extract as extract_sections

YN = ["yes", "no", "unclear"]
YN_NA = ["yes", "no", "unclear", "not_applicable"]

# Value schema per field (Gemini responseSchema / OpenAPI subset).
VALUE_SCHEMA = {
    "datasets": {"type": "ARRAY", "items": {"type": "STRING"}},
    "dataset_public": {"type": "STRING", "enum": ["yes", "no", "partly", "unclear"]},
    "label_source": {"type": "ARRAY", "items": {"type": "STRING", "enum": [
        "sandbox", "blacklist_cert", "blacklist_ja3", "ids_alert", "manual", "synthetic_attack", "unknown"]}},
    "label_feature_overlap": {"type": "STRING", "enum": YN_NA},
    "data_released": {"type": "STRING", "enum": ["yes", "no", "partly", "unclear"]},
    "feature_groups": {"type": "ARRAY", "items": {"type": "STRING", "enum": ["G1", "G2", "G3", "G4", "G5"]}},
    "feature_visibility_tier": {"type": "STRING", "enum": ["tls12", "tls13", "tls13_ech", "unclear"]},
    "ja4_used": {"type": "STRING", "enum": YN},
    "ech_considered": {"type": "STRING", "enum": YN},
    "tls_versions": {"type": "ARRAY", "items": {"type": "STRING", "enum": ["1.0", "1.1", "1.2", "1.3", "unclear"]}},
    "model_family": {"type": "STRING"},
    "split_protocol": {"type": "STRING", "enum": [
        "random", "temporal", "host_grouped", "cross_dataset", "mixed", "unclear", "not_applicable"]},
    "host_grouped": {"type": "STRING", "enum": YN_NA},
    "cross_dataset": {"type": "STRING", "enum": YN_NA},
    "temporal": {"type": "STRING", "enum": YN_NA},
    "granularity": {"type": "STRING", "enum": ["packet", "flow", "session", "host", "unclear"]},
    "early_detection": {"type": "STRING", "enum": YN_NA},
    "first_n_packets": {"type": "STRING"},
    "cost_reported": {"type": "STRING", "enum": ["none", "inference_only", "end_to_end", "unclear"]},
    "hardware": {"type": "STRING"},
    "metrics": {"type": "ARRAY", "items": {"type": "STRING"}},
    "best_reported_score": {"type": "STRING"},
    "code_released": {"type": "STRING", "enum": YN},
}

GROUPS = {
    "data_and_labels": ["datasets", "dataset_public", "label_source", "label_feature_overlap", "data_released"],
    "features_and_visibility": ["feature_groups", "feature_visibility_tier", "ja4_used", "ech_considered",
                                "tls_versions"],
    "evaluation_protocol": ["model_family", "split_protocol", "host_grouped", "cross_dataset", "temporal",
                            "granularity"],
    "deployment": ["early_detection", "first_n_packets", "cost_reported", "hardware"],
    "reporting": ["metrics", "best_reported_score", "code_released"],
}

# Extra guidance where single runs went wrong in earlier rounds.
HINTS = {
    "hardware": "only hardware used to MEASURE runtime/latency/throughput of the method; capture or training "
                "machines without timing results do not count",
    "split_protocol": "describe how the paper's own main evaluation splits train and test data; use mixed when "
                      "several protocols are used. The main evaluation is the one behind the paper's headline "
                      "detection results, not side experiments (sensitivity, false-negative or ablation tests)",
    "temporal": "a TLS-version transfer (train on TLS 1.2, test on TLS 1.3) is NOT temporal unless the test "
                "traffic was also collected later",
    "label_source": "the signal used to decide which flows are malicious vs benign (e.g. a certificate blacklist, "
                    "IDS alerts, manual inspection), NOT where the traffic came from: traffic recorded in a sandbox "
                    "counts as sandbox only if every flow of a sandbox run is labelled malicious because of that; "
                    "list every labelling signal used",
    "host_grouped": "answer for the main detection experiment (see split_protocol); yes only if the paper states "
                    "that train and test are separated by host, sample, capture or trace",
    "ech_considered": "yes if the paper evaluates, simulates or explicitly assumes Encrypted Client Hello (e.g. a "
                      "threat model or feature design where ECH hides the SNI/inner ClientHello); no if ECH is only "
                      "mentioned as background or future work",
    "feature_groups": "count only features the classifier or detector actually uses as input; fields extracted "
                      "only to filter, label or group flows do NOT count. G1 = whole-flow statistics (duration, "
                      "byte/packet totals, rates); G2 = sequences of packet/record sizes, directions or timing; "
                      "G3 = ClientHello/ServerHello fields; G4 = certificate fields (incl. certificate size); "
                      "G5 = JA3/JA4-style fingerprints",
    "feature_visibility_tier": "decide from the features the classifier uses as input only (see feature_groups), "
                               "not from fields used for filtering or labelling",
}


def field_schema(names: list[str], check: bool = False) -> dict:
    props = {}
    for n in names:
        p = {"value": VALUE_SCHEMA[n], "evidence": {"type": "STRING"},
             "evidence_source": {"type": "STRING", "enum": ["text", "table", "figure", "none"]}}
        req = ["value", "evidence", "evidence_source"]
        if check:
            p["check"] = {"type": "STRING", "enum": ["kept", "changed"]}
            p["reason"] = {"type": "STRING"}
            req += ["check", "reason"]
        props[n] = {"type": "OBJECT", "properties": p, "required": req}
    return {"type": "OBJECT", "properties": props, "required": names}


def describe(names: list[str]) -> str:
    lines = []
    for n in names:
        line = f"- {n}: {FIELDS[n]}"
        if n in HINTS:
            line += f" ({HINTS[n]})"
        lines.append(line)
    return "\n".join(lines)


QUOTE_RULES = """- "evidence" is ONE contiguous passage (max 40 words) copied character-for-character from the paper.
  Never join separate sentences, never use "..." and never paraphrase or summarise. If the support is spread
  over several places, quote the single most decisive passage.
- "evidence_source" says where it comes from: "text", "table" or "figure" (for a table or figure, copy the
  caption or the row as it appears), or "none" with evidence "" if nothing in the paper supports the value."""

QUOTE_MATCH_FLAG = 0.9  # answers whose quote matches the paper text less than this go to human review

EXTRACT_PROMPT = """You are coding a research paper for a systematic review of malicious TLS traffic detection.
This request covers only the "{group}" part of the coding form. Rules:
- Use only what the paper states about ITS OWN method and experiments (not related work or baselines).
- If it is not stated, use "unclear" (or "none"/"not_applicable" where the definition allows).
{quote_rules}

Fields:
{fields}

PAPER TEXT:
<<<
{text}
>>>"""

CHECK_PROMPT = """You are the second coder in a systematic review of malicious TLS traffic detection.
Below are draft answers for one paper, each with the quote that was given as support, followed by the paper.
For EVERY field: verify the value against the paper and the field definition.
- Keep the draft (check = "kept", value and evidence unchanged) unless you can quote a passage of the paper that
  contradicts it or shows it violates the field definition.
- Only then return the corrected value, that contradicting passage as evidence, and check = "changed", with a
  one-sentence reason. Do not change an answer just because another reading is also possible, and do not
  replace a main-experiment answer with one from a side experiment.
{quote_rules}

Field definitions:
{fields}

DRAFT ANSWERS:
{draft}

PAPER TEXT:
<<<
{text}
>>>"""


def parse(resp: dict) -> dict:
    try:
        return json.loads(resp.get("response", ""))
    except json.JSONDecodeError:
        return {"_parse_error": resp.get("response", "")[:2000]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("paper")
    ap.add_argument("out")
    ap.add_argument("--model", default="gemini-3.1-flash-lite")
    ap.add_argument("--thinking-level", default="high")
    ap.add_argument("--max-chars", type=int, default=90000)
    a = ap.parse_args()

    import fitz  # PyMuPDF

    with fitz.open(a.paper) as doc:
        raw = "\n".join(page.get_text() for page in doc)
    body, report = extract_sections(a.paper)
    text = clean_text(body, a.max_chars)
    raw_norm = norm(raw)

    t0, calls, tokens = time.time(), [], {"prompt": 0, "output": 0}
    draft: dict = {}
    for group, names in GROUPS.items():
        prompt = EXTRACT_PROMPT.format(group=group.replace("_", " "), fields=describe(names), text=text,
                                       quote_rules=QUOTE_RULES)
        resp = call_gemini(a.model, prompt, a.thinking_level, None, field_schema(names))
        ans = parse(resp)
        draft.update({k: v for k, v in ans.items() if k in names})
        calls.append({"group": group, "done_reason": resp.get("done_reason")})
        tokens["prompt"] += resp.get("prompt_eval_count") or 0
        tokens["output"] += resp.get("eval_count") or 0

    all_names = list(FIELDS)
    draft_view = json.dumps({k: draft.get(k, {"value": "MISSING", "evidence": ""}) for k in all_names},
                            indent=1, ensure_ascii=False)
    resp = call_gemini(a.model, CHECK_PROMPT.format(fields=describe(all_names), draft=draft_view, text=text,
                                                    quote_rules=QUOTE_RULES),
                       a.thinking_level, None, field_schema(all_names, check=True))
    checked = parse(resp)
    calls.append({"group": "check", "done_reason": resp.get("done_reason")})
    tokens["prompt"] += resp.get("prompt_eval_count") or 0
    tokens["output"] += resp.get("eval_count") or 0
    if "_parse_error" in checked:  # keep the draft rather than lose the paper
        checked = {k: dict(v, check="check_failed") for k, v in draft.items()}

    for ans in (draft, checked):
        for v in ans.values():
            if isinstance(v, dict):
                ev = str(v.get("evidence", ""))
                v["quote_match"] = quote_found(ev, raw_norm)
                flags = []
                if ev and v["quote_match"] < QUOTE_MATCH_FLAG:
                    flags.append("quote_not_verbatim")
                if "..." in ev or "…" in ev:
                    flags.append("spliced_quote")
                if v.get("check") == "changed":
                    flags.append("changed_by_check")
                v["review_flags"] = flags

    meta = {
        "paper": a.paper, "backend": "gemini", "model": a.model, "method": "grouped+schema+check",
        "elapsed_s": round(time.time() - t0, 1), "calls": calls, "tokens": tokens,
        "sections_dropped": [h for act, h, _ in report if act == "drop"], "chars_sent": len(text),
    }
    changed = [k for k, v in checked.items() if isinstance(v, dict) and v.get("check") == "changed"]
    flagged = {k: v["review_flags"] for k, v in checked.items() if isinstance(v, dict) and v.get("review_flags")}
    out = Path(a.out)
    m = re.match(r"(.+__)([^_]+)(_r\d+\.json)$", out.name)
    draft_out = out.with_name(f"{m.group(1)}{m.group(2)}draft{m.group(3)}") if m else out.with_suffix(".draft.json")
    draft_out.write_text(json.dumps({**meta, "stage": "draft", "missing_fields": [k for k in FIELDS if k not in draft],
                                     "fields": draft}, indent=2, ensure_ascii=False), encoding="utf-8")
    out.write_text(json.dumps({**meta, "stage": "checked", "changed_by_check": changed, "review_flags": flagged,
                               "missing_fields": [k for k in FIELDS if k not in checked], "fields": checked},
                              indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"paper": Path(a.paper).name, "elapsed_s": meta["elapsed_s"], "tokens": tokens,
                      "changed_by_check": changed, "review_flags": flagged,
                      "done_reasons": [c["done_reason"] for c in calls]}))


if __name__ == "__main__":
    main()
