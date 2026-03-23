#!/bin/bash
export LD_LIBRARY_PATH=~/JoI/llama.cpp/build/bin:$LD_LIBRARY_PATH
~/JoI/llama.cpp/build/bin/llama-server \
  --model models/Qwen3-4B-Q4_K_M.gguf \
  --flash-attn on \
  --cache-type-k q8_0 \
  --cache-type-v q8_0 \
  --ctx-size 12000 \
  --port 8002 --host 0.0.0.0 --parallel 2
