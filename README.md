*Latest Updates* 🔥
- [2026/03/16] (Local) Support Qwen3.5-9B-Q4_K_M

---
## Getting Started

<details>
<summary>Required Inputs</summary>

- command
- service_list.json
- connected_devices (Option)
- other_params (Option)

</details>

```bash
### Install llama.cpp ###
pip install -r requirements.txt
~/llama.cpp/build/bin/llama-server --model ~/models/Qwen3.5-9B-Q4_K_M.gguf --ctx-size 16384 --port 8001 --host 0.0.0.0 --flash-attn on --parallel 2
python test.py [all/target/custom] [debug]
```
