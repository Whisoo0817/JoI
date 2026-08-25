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


_OWN_OFF = {}
def own_off(cat):
    """그 기기 종류가 **스스로 끄는 방법**이 있나 → (서비스, enum 인자 이름) 또는 (None, None).
    값 목록에 off 가 있는 Set* 함수(선풍기 Mode=off)나, 인자 없는 Stop/Off 함수
    (커피포트 Stop)를 카탈로그에서 찾는다. 손으로 적은 표가 아니다.

    쓰는 곳 둘 — 켰다 끄기의 두 번째 수(builder.off_node), 그리고 "꺼" 라는 말에
    Switch.Off 를 밀어 줄지 말지(rerank). 스스로 끄는 기기는 Switch 로 끄지 않는다."""
    if cat not in _OWN_OFF:
        d = SERVICE_DATA.get(cat) or {}
        hit = (None, None)
        for f in (d.get("functions") or []):
            for a in (f.get("arguments") or []):
                if a.get("type") == "ENUM" and "off" in members_of(cat, a.get("format")):
                    hit = (f"{cat}.{f['id']}", a["id"]); break
            if hit[0]: break
        if not hit[0]:
            for f in (d.get("functions") or []):
                if f["id"] in ("Stop", "Off", "TurnOff") and not (f.get("arguments") or []):
                    hit = (f"{cat}.{f['id']}", None); break
        _OWN_OFF[cat] = hit
    return _OWN_OFF[cat]

def switch_categories(connected_devices):
    """켜고 끄기를 Switch 로 할 수 있는 기기 종류 — 같은 기기에 Switch 가 함께 붙어 있는 것들.
    (집에 스위치 달린 기기가 하나 있다고 제습기까지 Switch.On 으로 켤 수 있는 건 아니다.)"""
    if not connected_devices: return None
    out = set()
    for d in connected_devices.values():
        cats = d.get("category", [])
        if "Switch" in cats: out |= set(cats)
    return out

def conn_categories(connected_devices):
    """connected_devices dict → 연결 기기 카테고리 집합(*Control 제외). None이면 조인 필터 없음."""
    if not connected_devices: return None
    return {c for d in connected_devices.values() for c in d.get("category", []) if not c.endswith("Control")}
