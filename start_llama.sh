#!/bin/bash
~/joi/llama.cpp/build/bin/llama-server --model models/Qwen3.5-9B-Q3_K_M.gguf --ctx-size 16384 --port 8001 --host 0.0.0.0 --flash-attn on --parallel 2
