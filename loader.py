import os
import json

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Service List (1회 로딩) ───────────────────────────────
_SERVICE_LIST_PATH = os.path.join(_BASE_DIR, "files/service_list_ver2.0.4.json")
try:
    with open(_SERVICE_LIST_PATH, 'r', encoding='utf-8') as f:
        _raw = json.load(f)
    # skills 배열 → { id: { descriptor, values, functions, enums_map } } dict
    SERVICE_DATA = {}
    for item in _raw.get("skills", []):
        dev_id = item["id"]
        enums_map = {
            e["id"]: [f"{m['value']} - {m['description']}" for m in e.get("members", [])]
            for e in item.get("enums", [])
        }
        SERVICE_DATA[dev_id] = {
            "descriptor": item.get("descriptor", ""),
            "values": item.get("values", []),
            "functions": item.get("functions", []),
            "enums_map": enums_map,
        }
except FileNotFoundError:
    print(f"Warning: {_SERVICE_LIST_PATH} not found.")
    SERVICE_DATA = {}

# ── Prompts (1회 로딩) ────────────────────────────────────
def _load_all_prompts(base_dir):
    prompts = {}
    for root, dirs, files in os.walk(base_dir):
        for f in files:
            if f.endswith(".md"):
                prompts[f[:-3]] = open(os.path.join(root, f), "r", encoding='utf-8').read()
    return prompts

PROMPTS = _load_all_prompts(os.path.join(_BASE_DIR, "files"))
