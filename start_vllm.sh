#!/bin/bash
~/temp/bin/vllm serve cyankiwi/Qwen3.5-9B-AWQ-4bit   --host 0.0.0.0 --port 8000   --gpu-memory-utilization 0.5 --max_num_batched_tokens 8192   --max_model_len 8192 --language-model-only --enable-prefix-caching --max-num-seqs 2
