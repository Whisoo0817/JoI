#!/bin/bash
CUDA_VISIBLE_DEVICES=1 vllm serve cyankiwi/Qwen3.5-9B-AWQ-4bit   --host 0.0.0.0 --port 8002   --gpu-memory-utilization 0.85   --max_num_batched_tokens 16384   --max_model_len 8192   --language-model-only   --enable-prefix-caching   --max-num-seqs 8   --enable-auto-tool-choice   --tool-call-parser hermes
