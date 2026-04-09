import os
import json

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Service List (1회 로딩) ───────────────────────────────
_SERVICE_LIST_PATH = os.path.join(_BASE_DIR, "files/service_list_ver2.0.3.json")
try:
    with open(_SERVICE_LIST_PATH, 'r', encoding='utf-8') as f:
        SERVICE_DATA = json.load(f)
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
