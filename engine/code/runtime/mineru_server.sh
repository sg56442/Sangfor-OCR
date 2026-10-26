#!/usr/bin/env bash
set -euo pipefail
: "${MODEL:?}"
: "${PORT:?}"
: "${GPU_MEMORY_UTIL:?}"
# GPU_MEMORY_UTIL=auto:<MiB>：vLLM 0.8.5（V1）把同卡其他进程已占显存也计入 util×总显存 的预算，
# 因此按「启动时卡上已用显存 + 本服务目标显存」换算占用比例，便于多个评测同卡并行（推理输出不受影响）。
# 同卡训练的显存随样本长度波动，若在 vLLM 做显存分析时冲高会导致 KV 预算为负、启动失败：auto 模式下失败自动重试，
# 每次重新测量已用显存（最多 4 次）
AUTO_TARGET=""
if [[ "$GPU_MEMORY_UTIL" == auto:* ]]; then AUTO_TARGET=${GPU_MEMORY_UTIL#auto:}; fi
compute_util() {
  read -r USED_MIB TOTAL_MIB < <(nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader,nounits | head -1 | tr -d ',')
  GPU_MEMORY_UTIL=$(python3 -c "import sys; u, t, g = map(float, sys.argv[1:]); print(f'{min(0.95, (u + g) / t):.3f}')" "$USED_MIB" "$TOTAL_MIB" "$AUTO_TARGET")
  echo "auto gpu_memory_utilization: used=${USED_MIB}MiB total=${TOTAL_MIB}MiB target=${AUTO_TARGET}MiB -> ${GPU_MEMORY_UTIL}"
}
VIEW=/opt/p2t10/engine/code/runtime/model-view-${PORT}-${FT1021_VIEW_ID:-${HOSTNAME}}
mkdir -p "$VIEW"
test -z "$(ls -A "$VIEW")"
for file in "$MODEL"/*; do ln -s "$file" "$VIEW/"; done
rm -f "$VIEW/config.json"
python3 - "$MODEL/config.json" "$VIEW/config.json" <<'PY'
import json, pathlib, sys
from safetensors import safe_open
src, dst = map(pathlib.Path, sys.argv[1:])
cfg = json.loads(src.read_text())
text_cfg = cfg.pop('text_config', None)
with safe_open(str(src.parent / 'model.safetensors'), framework='pt', device='cpu') as weights:
    untied = 'lm_head.weight' in weights.keys()
declared = (text_cfg or {}).get('tie_word_embeddings', cfg.get('tie_word_embeddings'))
if declared is not None and declared == untied:
    raise ValueError('Weight tying config contradicts checkpoint tensor inventory')
cfg['tie_word_embeddings'] = not untied
dst.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
PY
if [ -z "$AUTO_TARGET" ]; then
  exec python3 -m vllm.entrypoints.openai.api_server \
  --model "$VIEW" --served-model-name "$MODEL" \
  --host 127.0.0.1 --port "$PORT" --dtype bfloat16 \
  --max-model-len 8192 --gpu-memory-utilization "$GPU_MEMORY_UTIL" \
  --max-num-seqs 45 --max-num-batched-tokens 16384 \
  --disable-log-requests
fi
for attempt in 1 2 3 4; do
  compute_util
  python3 -m vllm.entrypoints.openai.api_server \
    --model "$VIEW" --served-model-name "$MODEL" \
    --host 127.0.0.1 --port "$PORT" --dtype bfloat16 \
    --max-model-len 8192 --gpu-memory-utilization "$GPU_MEMORY_UTIL" \
    --max-num-seqs 45 --max-num-batched-tokens 16384 \
    --disable-log-requests && exit 0
  echo "vLLM 启动失败（第 ${attempt} 次），20 秒后按当前显存重试" >&2
  sleep 20
done
exit 1
