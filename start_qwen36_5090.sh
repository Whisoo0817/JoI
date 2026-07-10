#!/usr/bin/env bash
# Serve nvidia/Qwen3.6-35B-A3B-NVFP4 on this box's 2x RTX 5090 (sm_120) via vLLM.
#
# The three exports below are the fix for three errors hit while bringing this up:
#   - CUDA_HOME/PATH -> pip nvcc 13.2  : else "No supported CUDA architectures for
#                                        major versions [12]" (system nvcc 12.0 can't
#                                        build sm_120 flashinfer fp8 kernels).
#   - PYTHONPATH=joi-agent             : else "No module named 'tools'" — the TP
#                                        workers spawn with a different cwd and can't
#                                        import the CJK logits-processor plugin.
# (A fourth fix was aligning nvidia-cuda-runtime/nvrtc to 13.2 so nvcc and the CUDA
#  toolkit headers match — that's a one-time pip change, already applied to venv_llama.)
#
# Usage:  ./start_qwen36_5090.sh
# Override port:  VLLM_PORT=8003 ./start_qwen36_5090.sh
set -euo pipefail

VENV=/home/ikess/joi-llm/venv_llama
# shellcheck source=/dev/null
source "$VENV/bin/activate"

export CUDA_HOME="$VENV/lib/python3.12/site-packages/nvidia/cu13"
export PATH="$CUDA_HOME/bin:$PATH"
export PYTHONPATH="/home/tester/joi-agent:${PYTHONPATH:-}"

VLLM_HOST="${VLLM_HOST:-0.0.0.0}"
VLLM_PORT="${VLLM_PORT:-8002}"

# Refuse to start if the port is already serving (avoids a confusing bind error).
if command -v ss >/dev/null 2>&1 && ss -tln 2>/dev/null | grep -qE ":${VLLM_PORT}([[:space:]]|$)"; then
  echo "[start_qwen36_5090] Port ${VLLM_PORT} already in use. Stop the old server first:"
  echo "    pkill -9 -f 'vllm serve nvidia/Qwen3.6'"
  exit 1
fi

echo "[start_qwen36_5090] CUDA_HOME=$CUDA_HOME"
echo "[start_qwen36_5090] nvcc: $(nvcc --version | tail -1)"
echo "[start_qwen36_5090] Serving on http://${VLLM_HOST}:${VLLM_PORT}/v1"

exec vllm serve nvidia/Qwen3.6-35B-A3B-NVFP4 \
  --host "$VLLM_HOST" --port "$VLLM_PORT" \
  --tensor-parallel-size 2 \
  --trust-remote-code \
  --kv-cache-dtype fp8 \
  --gpu-memory-utilization 0.60 \
  --max-model-len 65536 \
  --max-num-seqs 2 \
  --max-num-batched-tokens 8192 \
  --enable-chunked-prefill \
  --async-scheduling \
  --enable-prefix-caching \
  --load-format fastsafetensors \
  --reasoning-parser qwen3 \
  --tool-call-parser qwen3_xml \
  --enable-auto-tool-choice \
  --speculative-config '{"method":"mtp","num_speculative_tokens":3,"moe_backend":"triton"}'
  # NOTE: MTP speculative decoding CANNOT coexist with a custom --logits-processors
  # (vLLM: "Custom logits processors are not supported when speculative decoding is
  # enabled"). So the CJK suppressor is dropped in this MTP variant. Attention backend
  # is left unset -> vLLM auto-selects (on sm_120 + fp8 it picks FlashInfer anyway).
