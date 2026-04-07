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

# ── Joi Syntax Docs ───────────────────────────────────────
def get_joi_syntax():
    """skills.md (joi 문법 설명) 반환"""
    path = os.path.join(_BASE_DIR, "skills.md")
    if os.path.isfile(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""

# ── Device Capability (SERVICE_DATA 기반) ─────────────────
def get_device_capability(category: str):
    """SERVICE_DATA에서 특정 카테고리의 서비스 목록 반환"""
    services = SERVICE_DATA.get(category, {})
    if not services:
        return None
    return {
        "category": category,
        "services": {
            name: {
                "type": info.get("type"),
                "argument_type": info.get("argument_type"),
                "return_type": info.get("return_type"),
                "description": info.get("description", ""),
            }
            for name, info in services.items()
        }
    }
