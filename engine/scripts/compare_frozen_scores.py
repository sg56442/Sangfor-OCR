#!/usr/bin/env python3
"""Read official score artifacts and compute paired, page-weighted differences.

The full-denominator contribution is a diagnostic quantity. It is not a score
from an independently executed full-set pipeline, nor an extrapolation to
untested pages. No predictions or official evaluator files are modified.
"""
import argparse
import collections
import datetime
import hashlib
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DENOMINATORS = {"text": 1557, "formula": 313, "table": 458}
FILES = {
    "text": "markdown_quick_match_text_block_per_page_edit.json",
    "formula": "markdown_quick_match_display_formula_per_sample_CDM.json",
    "table": "markdown_quick_match_table_per_table_TEDS.json",
}
SUMMARY_KEYS = {
    "text": "text_block_Edit_dist",
    "formula": "display_formula_CDM",
    "table": "table_TEDS",
}


def scores(evaluation):
    evaluation = Path(evaluation).resolve()
    summary = json.loads((evaluation / "score-summary.json").read_text())
    result, fingerprints = {}, {}
    for component, name in FILES.items():
        path = evaluation / "result" / name
        expected = summary["metrics"][SUMMARY_KEYS[component]]
        if not path.exists() and expected["page_denominator"] == 0:
            result[component] = {}
            fingerprints[str(path)] = None  # Official output omitted: no eligible pages.
            continue
        entries = json.loads(path.read_text())
        groups = collections.defaultdict(list)
        for identifier, value in entries.items():
            page = re.sub(r"_\[\d+\]$", "", identifier)
            value = value["TEDS"] if component == "table" else value
            if value is None or not math.isfinite(value):
                raise ValueError(f"Invalid metric: {path} {identifier}: {value}")
            groups[page].append(1.0 - value if component == "text" else value)
        values = {page: sum(v) / len(v) for page, v in groups.items()}
        assert len(values) == expected["page_denominator"], (component, len(values), expected)
        if values:
            expected_mean = 1.0 - expected["raw"] if component == "text" else expected["raw"]
            assert abs(sum(values.values()) / len(values) - expected_mean) < 1e-9, component
        result[component] = values
        fingerprints[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result, summary, fingerprints


def compare(base_dir, candidate_dir):
    baseline, base_summary, base_hashes = scores(base_dir)
    candidate, cand_summary, cand_hashes = scores(candidate_dir)
    components = {}
    all_page_contributions = collections.defaultdict(float)
    total = 0.0
    for component, before in baseline.items():
        after = candidate[component]
        assert before.keys() == after.keys(), f"Coverage changed: {component}"
        delta = {page: after[page] - value for page, value in before.items()}
        contribution = 100.0 * sum(delta.values()) / (3.0 * DENOMINATORS[component])
        total += contribution
        for page, value in delta.items():
            all_page_contributions[page] += 100.0 * value / (3.0 * DENOMINATORS[component])
        components[component] = {
            "observed_valid_pages": len(before),
            "full_valid_pages": DENOMINATORS[component],
            "full_denominator_contribution": contribution,
            "improved_pages": sum(v > 1e-10 for v in delta.values()),
            "regressed_pages": sum(v < -1e-10 for v in delta.values()),
            "unchanged_pages": sum(abs(v) <= 1e-10 for v in delta.values()),
            "per_page_delta_0_to_1": delta,
        }
    before = base_summary.get("overall_notebook")
    after = cand_summary.get("overall_notebook")
    return {
        "at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "scope": "Official frozen-output paired comparison; full-denominator contribution is NOT an end-to-end full-set gain.",
        "baseline_evaluation": str(Path(base_dir).resolve()),
        "candidate_evaluation": str(Path(candidate_dir).resolve()),
        "subset_overall_before": before,
        "subset_overall_after": after,
        "subset_overall_delta": after - before if before is not None and after is not None else None,
        "full_denominator_contribution": total,
        "components": components,
        "per_page_overall_contribution": dict(sorted(all_page_contributions.items(), key=lambda kv: kv[1])),
        "source_sha256": {**base_hashes, **cand_hashes},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    output = Path(args.out).resolve()
    assert output.is_relative_to(ROOT), output
    comparison = compare(args.baseline, args.candidate)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(comparison, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in comparison.items() if k not in ["source_sha256", "per_page_overall_contribution", "components"]}))
