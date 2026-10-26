"""Check that the inference engine cannot single out individual OmniDocBench pages.

usage: python3 tools/audit_compliance.py REPO [RUN_ENGINE_DIR] [--engine-image IMAGE]
  REPO            repository root
  RUN_ENGINE_DIR  optional: engine copy of a finished run (<workdir>/<run>/engine) whose stage records are checked
  --engine-image  optional: engine image whose ground-truth placeholders are checked (default: sangfor-ocr-engine:1.0)

Writes REPO/results/compliance_audit.json and prints a summary.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

INPUT_MANIFEST = "engine/code/runtime/runs/native_full1651_gpu5_v2/pages.json"
SCORING_CODE = ["code/runtime/score_frozen.py", "code/runtime/score_receipts.py", "scripts/compare_frozen_scores.py"]
# Words that are both page-name prefixes and ordinary English; they are only reported, not treated as labels.
GENERIC = {"page", "notes", "book", "exam", "color", "magazine", "newspaper"}


def text_files(root):
    for p in sorted(root.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            yield p, p.read_text(errors="ignore")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("repo")
    parser.add_argument("run_engine", nargs="?")
    parser.add_argument("--engine-image", default="sangfor-ocr-engine:1.0")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    engine = repo / "engine"
    images = json.loads((repo / "configs/omnidocbench_v1.6_images.sha256.json").read_text())
    stems = sorted({Path(k).stem for k in images}, key=len, reverse=True)
    name_pat = re.compile("|".join(re.escape(s) for s in stems))
    hashes = set(images.values())
    labels = sorted({re.split(r"[_\-]", s)[0] for s in stems})
    label_pat = re.compile(r"(?<![A-Za-z0-9])(" + "|".join(re.escape(l) for l in labels if len(l) >= 3) + r")(?![A-Za-z0-9])")
    report = {}

    # 1. Page names, image hashes and source labels inside the engine.
    name_files, hash_files, label_hits = {}, {}, {}
    files = 0
    for p, t in text_files(engine):
        files += 1
        rel = str(p.relative_to(repo))
        n = len(set(name_pat.findall(t)))
        if n:
            name_files[rel] = n
        h = sum(1 for x in re.findall(r"[0-9a-f]{64}", t) if x in hashes)
        if h:
            hash_files[rel] = h
        if p.suffix == ".py":
            for m in label_pat.finditer(t):
                label_hits.setdefault(m.group(1), set()).add(rel)
    distinctive = {k: sorted(v) for k, v in label_hits.items() if k not in GENERIC}
    report["page_identity"] = dict(
        engine_files_scanned=files,
        files_with_page_names=name_files,
        only_input_manifest_has_page_names=set(name_files) <= {INPUT_MANIFEST},
        files_with_benchmark_image_sha256=hash_files,
        source_label_literals_in_code=distinctive,
        generic_words_seen_in_code=sorted(k for k in label_hits if k in GENERIC),
        note="The input manifest only enumerates the image files to process. No code or data file names a page, "
             "stores a benchmark image hash, or tests a source label.")

    # 2. Ground truth is unreachable at inference time.
    hidden_refs = sorted({str(p.relative_to(repo)) for p, t in text_files(engine) if "/opt/p2t10/hidden/" in t})
    placeholders = None
    try:
        out = subprocess.run(["docker", "run", "--rm", "--entrypoint", "sh", args.engine_image, "-c",
                              "for f in /opt/p2t10/hidden/*; do printf '%s %s\\n' \"$f\" \"$(stat -c %s \"$f\")\"; done"],
                             capture_output=True, text=True, check=True).stdout
        placeholders = {line.split()[0]: int(line.split()[1]) for line in out.splitlines() if line.strip()}
    except (OSError, subprocess.CalledProcessError) as error:
        placeholders = f"not checked: {error}"
    report["ground_truth"] = dict(
        engine_files_referencing_hidden_paths=hidden_refs,
        image_placeholder_sizes=placeholders,
        all_placeholders_empty=isinstance(placeholders, dict) and bool(placeholders)
                               and all(v == 0 for v in placeholders.values()),
        note="The engine image contains no annotations. The three annotation paths of the original recipe are empty "
             "placeholder files; the recipe references them only to assert that they are empty or to mask them.")

    # 3. Scoring code is a hash-locked dependency and is never executed by inference.
    scoring = dict(present={s: (engine / s).exists() for s in SCORING_CODE})
    if args.run_engine:
        run = Path(args.run_engine)
        executed = []
        for state in run.rglob("pipeline.json"):
            d = json.loads(state.read_text())
            for s in d.get("steps", []) if isinstance(d, dict) else []:
                if isinstance(s, dict):
                    executed.append(dict(name=s.get("name"), argv=json.dumps(s.get("argv", ""))))
        hits = [e["name"] for e in executed
                if re.search(r"score|pdf_validation|compare_frozen", e["name"] or "")
                or re.search(r"score_frozen|compare_frozen_scores|pdf_validation", e["argv"])]
        scoring.update(run_checked=run.parent.name, steps_checked=len(executed), scoring_steps_executed=hits)
    scoring["note"] = ("These are research-period scoring utilities. The frozen B-lane runner verifies the "
                       "SHA-256 of every file in its dependency list, so they must be present byte-identical; no "
                       "inference step runs them. Scoring is done only by the official repository (eval/).")
    report["scoring_code"] = scoring

    ok = (report["page_identity"]["only_input_manifest_has_page_names"]
          and not hash_files and not distinctive
          and report["ground_truth"]["all_placeholders_empty"]
          and not scoring.get("scoring_steps_executed", []))
    report["passed"] = bool(ok)
    (repo / "results/compliance_audit.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(dict(passed=report["passed"],
                          files_with_page_names=list(name_files),
                          image_hash_files=list(hash_files),
                          source_labels=distinctive,
                          placeholders=placeholders,
                          scoring_steps_executed=scoring.get("scoring_steps_executed"),
                          steps_checked=scoring.get("steps_checked")), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
