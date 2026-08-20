import os
import json
import re

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Service List (1회 로딩) ───────────────────────────────
# service_list 2.1.0 은 카테고리별 평면 dict 다 — 값/함수가 한 자리에 섞여 있고,
# 인자는 이름 없이 위치와 형식 힌트("DOUBLE | DOUBLE", "brightness | transition_rate")로만 온다.
# 여기서 예전 모양({values, functions, enums_map})으로 되돌려 아래 코드는 그대로 쓴다.
# 인자 이름은 files/argument_names.json 이름표에서 가져온다(2.0.7 이름 승계 + 형식 힌트 유도).
_SERVICE_LIST_PATH = os.path.join(_BASE_DIR, "files/service_list_ver2.1.0.json")
_ARG_NAMES_PATH = os.path.join(_BASE_DIR, "files/argument_names.json")

_ARG_NAMES = {}
try:
    with open(_ARG_NAMES_PATH, 'r', encoding='utf-8') as f:
        _ARG_NAMES = json.load(f).get("arguments", {})
except FileNotFoundError:
    print(f"Warning: {_ARG_NAMES_PATH} not found — 인자 이름을 형식 힌트로만 짓는다.")

_ARG_DEFAULT = {"ENUM": "Mode", "STRING": "Text", "BINARY": "Data"}


def _split(v):
    """ "A | B" → ["A", "B"] (단일 값이면 1개짜리 목록)."""
    return [x.strip() for x in str(v).split("|")] if v is not None else []


def _per_arg(v, n, i):
    """인자별 값 꺼내기 — 다인자는 배열로, 단일 인자는 통째로 온다."""
    if v is None: return None
    if n > 1: return v[i] if isinstance(v, list) and i < len(v) else None
    return v


def _arg_names(svc, types, fmt):
    """인자 이름: 이름표 → 형식 힌트(CamelCase) → 타입 기본값."""
    named = _ARG_NAMES.get(svc)
    if named and len(named) == len(types):
        return list(named)
    toks = _split(fmt)
    if len(toks) == len(types) and all(toks):
        return ["".join(w[:1].upper() + w[1:] for w in re.split(r"[^0-9a-zA-Z]+", t) if w) or "Value" for t in toks]
    if len(types) == 1:
        return [_ARG_DEFAULT.get(types[0], "Value")]
    return [f"Arg{i + 1}" for i in range(len(types))]


def _to_service_data(raw):
    """2.1.0 평면 dict → { 카테고리: {descriptor, values, functions, enums_map} }."""
    data = {}
    for cat, members in raw.items():
        if cat.startswith("$") or not isinstance(members, dict):
            continue
        values, functions, enums_map = [], [], {}
        for name, m in members.items():
            if not isinstance(m, dict): continue
            if m.get("type") == "function":
                types = _split(m.get("argument_type"))
                names = _arg_names(f"{cat}.{name}", types, m.get("argument_format"))
                args = []
                for i, (aid, at) in enumerate(zip(names, types)):
                    a = {"id": aid, "type": at,
                         "descriptor": m.get("argument_descriptor", ""),
                         "unit": _per_arg(m.get("argument_unit"), len(types), i),
                         "bound": _per_arg(m.get("argument_bounds"), len(types), i)}
                    if at == "ENUM":                                   # enum 은 서비스마다 인라인 — 자리 이름을 키로 삼는다
                        key = f"{name}.{aid}"
                        a["format"] = key
                        enums_map[key] = list(m.get("argument_enums") or [])
                    args.append({k: v for k, v in a.items() if v is not None})
                functions.append({"id": name, "descriptor": m.get("descriptor", ""),
                                  "arguments": args, "return_type": m.get("return_type", "VOID")})
            else:
                v = {"id": name, "type": m.get("return_type"),
                     "descriptor": m.get("descriptor", ""),
                     "unit": m.get("unit"), "bound": m.get("return_bounds")}
                if m.get("return_type") == "ENUM":
                    v["format"] = name
                    enums_map[name] = list(m.get("enums_descriptor") or [])
                values.append({k: val for k, val in v.items() if val is not None})
        # enum 목록을 한 자리에만 적어둔 경우가 있다 — 빈 자리는 형제한테서 빌린다.
        #   ① 이름에서 끝 숫자를 뗀 형제 (Button2 → Button1)
        #   ② 그래도 없으면 그 카테고리에 하나뿐인 값 enum (SetCookingParameters → RiceCookerMode)
        stem = lambda k: k.rstrip("0123456789")
        filled = {k: v for k, v in enums_map.items() if v}
        only_value = [v["format"] for v in values if v.get("format") and enums_map.get(v["format"])]
        for key, mem in enums_map.items():
            if mem: continue
            sib = next((v for k, v in filled.items() if stem(k) == stem(key.split(".")[0]) and v), None)
            if sib is None and len(only_value) == 1: sib = enums_map[only_value[0]]
            if sib: enums_map[key] = list(sib)
        data[cat] = {"descriptor": members.get("$descriptor", cat),
                     "values": values, "functions": functions, "enums_map": enums_map}
    return data


try:
    with open(_SERVICE_LIST_PATH, 'r', encoding='utf-8') as f:
        SERVICE_DATA = _to_service_data(json.load(f))
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


# ── Catalog sub-skill capability tags (single source of truth) ────────────
# Skills that are not standalone devices but capability mixins always attached
# to a parent device (e.g. Light has Switch + LevelControl + ColorControl).
# pipeline_helpers.py _build_service_category_map lets these categories
# overwrite primary mappings for shared service names.
SUB_SKILL_TAGS = {"Switch", "LevelControl", "ColorControl", "RotaryControl"}
