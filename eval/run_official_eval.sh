#!/usr/bin/env bash
# Official OmniDocBench v1.6 end2end evaluation of a prediction directory.
#
# Uses the unmodified official repository at the leaderboard-pinned commit f133a71 and the
# official evaluation image recommended by its README; runs `python pdf_validation.py`.
#
# usage: eval/run_official_eval.sh GT_JSON PRED_DIR OUT_DIR [OMNIDOCBENCH_SRC]
#   GT_JSON           OmniDocBench.json from the v1.6 dataset release
#   PRED_DIR          one <image stem>.md per page (e.g. the B/ directory written by infer.py)
#   OUT_DIR           new directory for the official result files
#   OMNIDOCBENCH_SRC  checkout of github.com/opendatalab/OmniDocBench at f133a71 (default: ./OmniDocBench)
# env: EVAL_IMAGE (default ghcr.io/zeng-weijun/omnidocbench-eval:repro-ubuntu2204), EVAL_CPUS (default 16)
set -euo pipefail
GT=$(realpath "$1"); PRED=$(realpath "$2"); OUT=$3
SRC=$(realpath "${4:-$(dirname "$0")/../OmniDocBench}")
IMAGE=${EVAL_IMAGE:-ghcr.io/zeng-weijun/omnidocbench-eval:repro-ubuntu2204}
COMMIT=f133a71e9e91c3621c7ce8994200a7b394a06eb3

test -f "$SRC/pdf_validation.py" || { echo "official source not found at $SRC" >&2; exit 2; }
if git -C "$SRC" rev-parse HEAD >/dev/null 2>&1; then
  test "$(git -C "$SRC" rev-parse HEAD)" = "$COMMIT" || { echo "official source must be at $COMMIT" >&2; exit 2; }
fi
test ! -e "$OUT" || { echo "$OUT exists; use a new output directory" >&2; exit 2; }
mkdir -p "$OUT"
OUT=$(realpath "$OUT")
cp -a "$SRC" "$OUT/workspace"
rm -rf "$OUT/workspace/.git"
mkdir -p "$OUT/workspace/gt" "$OUT/workspace/data_md/predictions"

# The official configs/end2end.yaml with only the two data paths replaced.
sed -e 's#data_path: ./demo_data/omnidocbench_demo/OmniDocBench_demo.json#data_path: ./gt/OmniDocBench.json#' \
    -e 's#data_path: ./demo_data/end2end#data_path: ./data_md/predictions#' \
    "$OUT/workspace/configs/end2end.yaml" > "$OUT/workspace/configs/p2t10_end2end.yaml"
grep -q "./gt/OmniDocBench.json" "$OUT/workspace/configs/p2t10_end2end.yaml"
grep -q "./data_md/predictions" "$OUT/workspace/configs/p2t10_end2end.yaml"

# Optional (default: official values 300 / 420 s): relax the quick_match time limits; README recommends 2400 s.
if [ -n "${QUICK_MATCH_TRUNCATED_TIMEOUT_SEC:-}${MATCH_TIMEOUT_SEC:-}" ]; then
  sed -i -e "s#quick_match_truncated_timeout_sec: 300#quick_match_truncated_timeout_sec: ${QUICK_MATCH_TRUNCATED_TIMEOUT_SEC:-300}#" \
         -e "s#match_timeout_sec: 420#match_timeout_sec: ${MATCH_TIMEOUT_SEC:-420}#" \
         "$OUT/workspace/configs/p2t10_end2end.yaml"
  echo "NON-DEFAULT time limits:"; grep -E "quick_match_truncated_timeout_sec|match_timeout_sec" "$OUT/workspace/configs/p2t10_end2end.yaml"
fi

docker run --rm --network none --cpus "${EVAL_CPUS:-16}" --entrypoint bash \
  -v "$OUT/workspace:/workspace" \
  -v "$GT:/workspace/gt/OmniDocBench.json:ro" \
  -v "$PRED:/workspace/data_md/predictions:ro" \
  "$IMAGE" -lc 'cd /workspace && python pdf_validation.py --config configs/p2t10_end2end.yaml' \
  2>&1 | tee "$OUT/eval.log"

python3 - "$OUT" <<'PY'
import glob, json, sys
out = sys.argv[1]
summaries = glob.glob(f"{out}/workspace/result/*score*summary*.json") + glob.glob(f"{out}/workspace/result/*run_summary*.json")
print("result files:", sorted(p.split('/')[-1] for p in glob.glob(f"{out}/workspace/result/*.json")))
for p in summaries:
    print(p.split('/')[-1], json.dumps(json.load(open(p)), ensure_ascii=False)[:800])
PY
