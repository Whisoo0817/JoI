*Latest Updates*
- [2026/03/20] (Local) Support vLLM + Qwen3.5-9B-AWQ-4bit
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
### Install ###
pip install -r requirements.txt

### Start Server ###
# llama.cpp (main branch)
./start_llama.sh
# vLLM (vllm branch)
./start_vllm.sh

### Run ###
python test.py [all/target/custom] [debug]
```
