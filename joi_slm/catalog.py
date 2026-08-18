# -*- coding: utf-8 -*-
"""서비스 카탈로그 접근 — service_list(loader.SERVICE_DATA), assets/effects.json(문서·역할·한국어 표지), assets/category_aliases.json.
사용자 결정: *Control 계열(LevelControl·ColorControl·RotaryControl)은 쓰지 않는다."""
import json, os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))          # joi/ (리포 루트)
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
if ROOT not in sys.path: sys.path.insert(0, ROOT)
from loader import SERVICE_DATA                                                # files/service_list_ver*.json

NO_CAT = ("ColorControl", "LevelControl", "RotaryControl")
def allowed(svc): return svc.split(".")[0] not in NO_CAT
AL = json.load(open(os.path.join(ASSETS, "category_aliases.json")))["aliases"]
SERVICES = [s for s in json.load(open(os.path.join(ASSETS, "effects.json")))["services"] if allowed(s["svc"])]
EFF = {s["svc"]: s for s in SERVICES}
ROLE = {s["svc"]: s["role"] for s in SERVICES}

def svc_doc(s):
    """검색 문서: "카테고리 별칭 | svc | ko_triggers | effects" """
    cat = s["svc"].split(".")[0]
    return f"{' '.join(AL.get(cat, [])[:4])} | {s['svc']} | " + " / ".join(s.get("ko_triggers", [])) + " | " + "; ".join(s.get("effects", []))

def svc_info(svc):
    """서비스 → (kind, spec): value(values 항목) 또는 function(functions 항목)"""
    if not svc or "." not in svc: return None, None
    cat, name = svc.split(".", 1); d = SERVICE_DATA.get(cat)
    if not d: return None, None
    for v in d.get("values", []):
        if v["id"] == name: return "value", v
    for f in d.get("functions", []):
        if f["id"] == name: return "function", f
    return None, None

def members_of(cat, fmt):
    return SERVICE_DATA.get(cat, {}).get("enums_map", {}).get(fmt, [])

def conn_categories(connected_devices):
    """connected_devices dict → 연결 기기 카테고리 집합(*Control 제외). None이면 조인 필터 없음."""
    if not connected_devices: return None
    return {c for d in connected_devices.values() for c in d.get("category", []) if not c.endswith("Control")}
