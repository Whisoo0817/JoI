#!/usr/bin/env bash
# Serve Hyper-AI/Qwen3.5-9B-fp8 on a SINGLE RTX 5090 (GPU 1, sm_120) via vLLM.
# Lightweight single-GPU variant for quick tests (the 35B NVFP4 model uses both GPUs
# via start_qwen36_5090.sh).
#
# The three exports below are required on sm_120 (RTX 5090), same as the 35B script:
#   - CUDA_HOME/PATH -> pip nvcc 13.2 : else FlashInfer can't detect the GPU and dies
#                                       with "FlashInfer requires GPUs with sm75 or
#                                       higher" (the stock nvcc 12.0 can't target sm_120).
#   - PYTHONPATH=joi-agent            : else "No module named 'tools'" — the worker
#                                       can't import the CJK logits-processor plugin.
#
# NOTE: --language-model-only was REMOVED in modern vLLM (0.24) — do not re-add it.
#
# Usage:  ./start_qwen35_9b_5090.sh
# Override:  VLLM_PORT=8003 GPU_ID=0 ./start_qwen35_9b_5090.sh
set -euo pipefail

VENV=/home/ikess/joi-llm/venv_llama
# shellcheck source=/dev/null
source "$VENV/bin/activate"

export CUDA_HOME="$VENV/lib/python3.12/site-packages/nvidia/cu13"
export PATH="$CUDA_HOME/bin:$PATH"
export PYTHONPATH="/home/tester/joi-agent:${PYTHONPATH:-}"

GPU_ID="${GPU_ID:-1}"
export CUDA_VISIBLE_DEVICES="$GPU_ID"

VLLM_HOST="${VLLM_HOST:-0.0.0.0}"
VLLM_PORT="${VLLM_PORT:-8002}"

if command -v ss >/dev/null 2>&1 && ss -tln 2>/dev/null | grep -qE ":${VLLM_PORT}([[:space:]]|$)"; then
  echo "[start_qwen35_9b] Port ${VLLM_PORT} already in use. Stop the old server first:"
  echo "    pkill -9 -f 'vllm serve Hyper-AI/Qwen3.5-9B'"
  exit 1
fi

echo "[start_qwen35_9b] CUDA_HOME=$CUDA_HOME"
echo "[start_qwen35_9b] nvcc: $(nvcc --version | tail -1)"
echo "[start_qwen35_9b] GPU: $CUDA_VISIBLE_DEVICES  |  Serving on http://${VLLM_HOST}:${VLLM_PORT}/v1"

exec vllm serve Hyper-AI/Qwen3.5-9B-fp8 \
  --host "$VLLM_HOST" --port "$VLLM_PORT" \
  --gpu-memory-utilization 0.9 \
  --max-num-batched-tokens 8192 \
  --max-model-len 65536 \
  --enable-prefix-caching \
  --max-num-seqs 1 \
  --enable-auto-tool-choice \
  --trust-remote-code \
  --tool-call-parser qwen3_xml \
  --reasoning-parser qwen3 \
  --logits-processors tools.vllm_cjk.cjk_suppressor:CJKSuppressor
