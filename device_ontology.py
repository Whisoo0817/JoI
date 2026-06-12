"""Deterministic device ontology + embedding-based category narrowing.

This module replaces two costly/flaky pieces of the device path:

  1. Nickname → device id  — DETERMINISTIC (no LLM). A command that names a
     specific device by its nickname is pinned to that device's real id by a
     normalized-substring lookup. (Replaces the flaky `device_grounding` LLM.)

  2. Command → candidate categories — EMBEDDING retrieval. Instead of dumping
     EVERY connected category's `device_rules_*.md` into service_plan (~19k
     tokens), we embed each category's catalog doc once and keep only the top-K
     most similar to the (translated) command. service_plan then sees ~3 rule
     blocks instead of ~27.

Both layers degrade gracefully: if the embedding server is unreachable the
narrower returns None and the caller falls back to the full category set
(i.e. exactly the pre-existing behavior). Sub-skills (Switch/LevelControl/…)
and nickname-pinned categories are always force-included so on/off and pinned
devices never get narrowed away.
"""

import os
import re

from loader import SERVICE_DATA, SUB_SKILL_TAGS, get_device_rules_section

# ── Embedding endpoint (separate vLLM `--task embed` server) ──────────────
# Kept distinct from the chat model so the light HTTP-only pipeline venv never
# needs torch. Launch e.g.:
#   vllm serve Qwen/Qwen3-Embedding-0.6B --runner pooling --port 8004 \
#       --served-model-name qwen3-embed --gpu-memory-utilization 0.12 \
#       --max-model-len 2048
# (vllm 0.19: use --runner pooling, not the old --task embed. The low
#  gpu-memory-utilization is REQUIRED — the 5090 already hosts the chat vLLM
#  (8002) + voice engine (8003), and vLLM's default 0.9 reservation overshoots
#  free VRAM. 0.12 → ~3.8GB, plenty for a 0.6B embedder. 8004 is free.)
_EMBED_BASE_URL = os.environ.get("JOI_EMBED_BASE_URL", "http://localhost:8004/v1")
_EMBED_MODEL = os.environ.get("JOI_EMBED_MODEL", "qwen3-embed")


# ── 1. Deterministic nickname resolution ──────────────────────────────────
def _norm(s: str) -> str:
    """Lowercase + strip all whitespace so '6구 1' and '6구1' compare equal."""
    return re.sub(r"\s+", "", (s or "").lower())


def build_nickname_index(connected_devices: dict) -> dict:
    """{normalized_nickname: real_id}. Nicknames < 2 chars are skipped (too
    generic to anchor a match)."""
    idx = {}
    for rid, v in connected_devices.items():
        nn = (v.get("nickname") or "").strip()
        if len(nn) >= 2:
            idx[_norm(nn)] = rid
    return idx


def resolve_nicknames(sentence: str, nickname_index: dict) -> list:
    """Return [(real_id, nickname_norm)] for every nickname that appears, as a
    normalized substring, in the command. Longest nicknames are tested first so
    the most specific device wins and is not shadowed by a shorter prefix.
    High precision by design: a partial/group reference with no exact nickname
    match simply yields nothing and falls through to the tag-based flow."""
    s = _norm(sentence)
    hits, claimed = [], []
    for nn in sorted(nickname_index, key=len, reverse=True):
        if nn and nn in s:
            # avoid double-counting a nickname fully contained in a longer one
            # that already matched (e.g. '...6구1' contains '...6구')
            if any(nn in longer for longer in claimed):
                continue
            hits.append((nickname_index[nn], nn))
            claimed.append(nn)
    return hits


# ── 2. Category embedding docs + narrowing ─────────────────────────────────
_RULE_DOC_CAP = 400  # chars of device_rules to fold into the embedding doc

# Natural-language trigger words (Korean + English) per category. The bare
# SERVICE_DATA descriptors are English & technical ('numerical representation of
# brightness') and miss the everyday nouns/verbs a command actually uses ('문',
# '사람', '알려줘', 'door', 'announce'), so Speaker/ContactSensor/PresenceSensor
# etc. ranked poorly. Folding these in is the synonym-table idea delivered as
# embedding signal — embedding still handles fuzz, but the core trigger words
# are guaranteed present. Extend freely; unknown categories just skip.
_CATEGORY_KEYWORDS = {
    "Light": "조명 불 전등 라이트 밝기 light lamp brightness dim illuminate 켜 꺼",
    "Switch": "켜 꺼 켜줘 꺼줘 켜기 끄기 전원 스위치 on off turn on turn off toggle power switch",
    "LevelControl": "밝기 레벨 단계 세기 brightness level dim intensity percent 퍼센트",
    "ColorControl": "색 색상 컬러 color hue saturation",
    "RotaryControl": "다이얼 회전 dial rotary knob",
    "Speaker": "스피커 알려줘 말해줘 안내 알림 음성 소리 speaker announce say speak voice tell notify audio",
    "ToastPublisher": "토스트 알림 알려줘 표시 띄워 보여줘 toast notification popup show notify display",
    "MenuProvider": "메뉴 menu option",
    "EmailProvider": "이메일 메일 email mail send 보내 전송",
    "PresenceSensor": "사람 재실 누군가 감지 있으면 presence person occupancy someone detected 재실센서",
    "MotionSensor": "움직임 모션 동작 motion movement",
    "ContactSensor": "문 창문 도어 열림 닫힘 열려 닫혀 열리면 door window open close contact",
    "AirQualitySensor": "미세먼지 초미세먼지 이산화탄소 공기질 먼지 co2 air quality dust carbon dioxide fine dust tvoc",
    "AirConditioner": "에어컨 냉방 난방 air conditioner ac cooling heating temperature 온도",
    "AirPurifier": "공기청정기 청정 air purifier clean",
    "Humidifier": "가습기 가습 humidifier humidity 습도",
    "Dehumidifier": "제습기 제습 dehumidifier",
    "TemperatureSensor": "온도 더우면 추우면 temperature degrees hot cold thermometer",
    "HumiditySensor": "습도 humidity moisture",
    "LightSensor": "조도 밝기 럭스 lux illuminance light level brightness 어두우면 밝으면",
    "Camera": "카메라 촬영 녹화 영상 사진 capture record video photo camera stream",
    "Clock": "시간 시각 정각 매시간 time clock hour minute 알람",
    "Button": "버튼 누르면 누를 button press click 단추",
    "MultiButton": "버튼 멀티버튼 다이얼 button multi buttons",
    "SmokeDetector": "연기 화재 불 smoke fire detector",
    "Plug": "플러그 콘센트 plug outlet socket",
    "PowerMeter": "전력 소비전력 watt power consumption",
    "EnergyMeter": "에너지 전력량 energy kwh usage",
    "WeatherProvider": "날씨 기상 weather forecast rain temperature",
    "RobotVacuumCleaner": "로봇청소기 청소 vacuum robot clean",
    "Battery": "배터리 battery charge",
}


def category_doc(cat: str) -> str:
    """Keyword-rich text embedded to represent a category. Combines the category
    name, hand-curated natural-language trigger words (KR+EN), the SERVICE_DATA
    descriptor, function/value member names, and the head of the service_plan
    rule section — so everyday command wording matches even when the catalog
    descriptor is technical."""
    d = SERVICE_DATA.get(cat, {})
    parts = [cat]
    kw = _CATEGORY_KEYWORDS.get(cat)
    if kw:
        parts.append("Triggers: " + kw)
    if d.get("descriptor"):
        parts.append(d["descriptor"])
    funcs = [f.get("id") for f in d.get("functions", []) if f.get("id")]
    vals = [v.get("id") for v in d.get("values", []) if v.get("id")]
    if funcs:
        parts.append("Functions: " + ", ".join(funcs))
    if vals:
        parts.append("Values: " + ", ".join(vals))
    rule = get_device_rules_section(cat, "service_plan")
    if rule:
        parts.append(rule[:_RULE_DOC_CAP])
    return "\n".join(p for p in parts if p)


def _embed_texts(texts: list):
    """Call the vLLM embeddings endpoint. Raises on any transport/server error
    so callers can fall back. Returns list[list[float]]."""
    from openai import OpenAI
    client = OpenAI(base_url=_EMBED_BASE_URL, api_key="EMPTY")
    resp = client.embeddings.create(model=_EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data]


_cat_emb_cache = {}  # cat -> np.ndarray (L2-normalized)


def _ensure_cat_embeddings(cats: list):
    import numpy as np
    missing = [c for c in cats if c not in _cat_emb_cache]
    if not missing:
        return
    vecs = _embed_texts([category_doc(c) for c in missing])
    for c, v in zip(missing, vecs):
        arr = np.asarray(v, dtype="float32")
        _cat_emb_cache[c] = arr / (np.linalg.norm(arr) + 1e-9)


def narrow_categories(query: str, connected_categories, top_k: int = 8,
                      min_sim: float = 0.0):
    """Rank connected categories by cosine similarity to `query`; return
    (picked_categories, scored) where scored = [(sim, cat)] desc. Returns
    (None, None) if embedding is unavailable so the caller can fall back to the
    full set. Pure ranking only — sub-skill / nickname force-includes are
    applied by `select_categories_for_command`."""
    import numpy as np
    cats = list(dict.fromkeys(connected_categories))
    if not cats:
        return [], []
    try:
        _ensure_cat_embeddings(cats)
        q = np.asarray(_embed_texts([query])[0], dtype="float32")
        q = q / (np.linalg.norm(q) + 1e-9)
    except Exception:
        return None, None
    scored = sorted(((float(q @ _cat_emb_cache[c]), c) for c in cats),
                    reverse=True)
    picked = [c for s, c in scored[:top_k] if s >= min_sim]
    return picked, scored


def select_categories_for_command(query: str, connected_categories,
                                  pinned_categories=None, top_k: int = 8):
    """High-level narrower used by the pipeline.

    Returns (categories, info_str). `categories` is the narrowed set with
    connected sub-skills and any nickname-pinned categories force-included;
    order is similarity-desc with force-includes appended. Falls back to ALL
    connected categories (returns them unchanged) when embedding is unavailable.
    `info_str` is a one-line log of what happened."""
    connected = list(dict.fromkeys(connected_categories))
    picked, scored = narrow_categories(query, connected, top_k=top_k)
    if picked is None:  # embedding down → no narrowing
        return connected, "narrow: embedding unavailable → full set"

    forced = []
    # always keep Switch when connected (on/off lives in Switch and a bare
    # '켜줘'/'turn on' may not rank it). Other sub-skills (LevelControl/
    # ColorControl/RotaryControl) ride along with their parent device in
    # device_match, so we don't force-include them and waste a slot.
    if "Switch" in connected and "Switch" not in picked:
        forced.append("Switch")
    # always keep categories of nickname-pinned devices
    for c in (pinned_categories or []):
        if c in connected and c not in picked and c not in forced:
            forced.append(c)

    result = picked + forced
    top_str = ", ".join(f"{c}:{s:.2f}" for s, c in (scored or [])[:top_k])
    info = (f"narrow: {len(connected)}→{len(result)} "
            f"[{', '.join(result)}]"
            + (f" +forced[{', '.join(forced)}]" if forced else "")
            + f"  (top: {top_str})")
    return result, info


# ── 3. Device-first targets → concrete devices (deterministic) ─────────────
# device_retrieve emits semi-structured target lines:
#   - role=action   | by=label:Tuya
#   - role=condition| by=label:PresenceSensor
#   - role=notify   | by=channel:speaker,toast
#   - role=action   | by=nickname:삼성 공기청정기 큰거
# We apply each `by` criterion to the connected devices in PYTHON — no LLM —
# producing the matched device ids + their categories. This makes the
# category-narrowing for device_resolve free and exact (no extra stage).

# Notification channels → the category that realizes each.
_CHANNEL_CATEGORY = {"speaker": "Speaker", "toast": "ToastPublisher"}


def parse_targets(block: str) -> list:
    """Parse a <targets> block body into [{role, by_kind, by_val, scope}].
    Tolerant of spacing; ignores non-matching lines."""
    out = []
    for ln in (block or "").splitlines():
        ln = ln.strip().lstrip("-").strip()
        if not ln or "by=" not in ln:
            continue
        role_m = re.search(r'role\s*=\s*(\w+)', ln)
        scope_m = re.search(r'scope\s*=\s*(\w+)', ln)
        # by= must stop at the next " | " so it doesn't swallow "| scope=..."
        by_m = re.search(r'by\s*=\s*([a-zA-Z]+)\s*:\s*([^|]+)', ln)
        if not by_m:
            continue
        out.append({
            "role": (role_m.group(1).strip().lower() if role_m else "action"),
            "by_kind": by_m.group(1).strip().lower(),     # label | nickname | channel
            "by_val": by_m.group(2).strip(),
            "scope": (scope_m.group(1).strip().lower() if scope_m else "one"),  # all|one|cond
        })
    return out


def quantifier_for(scope: str, role: str, n: int) -> str:
    """Deterministic quantifier prefix from (scope, role, match count): '', 'all',
    or 'any'. The LLM's `scope` already settled the ambiguous Korean 'all' part;
    this just assembles the rule the resolver kept violating.
      - n <= 1                  → '' (one)
      - role==condition, n>=2   → 'any'
      - scope==all              → 'all'
      - else                    → '' (one)"""
    if n <= 1:
        return ""
    if role == "condition":
        return "any"
    return "all" if scope == "all" else ""


def resolve_targets(targets: list, connected_devices: dict) -> list:
    """Apply each target's `by` criterion to connected_devices. Returns a list of
    resolved groups: {role, by_kind, by_val, ids:[real_id...], categories:[...]}.
    A group that matches no device gets ids=[] (caller decides error)."""
    nick_idx = build_nickname_index(connected_devices)
    resolved = []
    for t in targets:
        kind, val = t["by_kind"], t["by_val"]
        ids = []
        if kind == "label":
            needle = _norm(val)
            for rid, dev in connected_devices.items():
                labels = list(dev.get("category", [])) + list(dev.get("tags", []))
                if any(_norm(x) == needle for x in labels):
                    ids.append(rid)
        elif kind == "nickname":
            n = _norm(val)
            # exact first, else substring (handles minor wording)
            hit = nick_idx.get(n) or next(
                (rid for nn, rid in nick_idx.items() if n in nn or nn in n), None)
            if hit:
                ids.append(hit)
        elif kind == "channel":
            wanted = {_CHANNEL_CATEGORY.get(c.strip().lower())
                      for c in val.split(",") if c.strip()}
            for rid, dev in connected_devices.items():
                if set(dev.get("category", [])) & wanted:
                    ids.append(rid)
        cats = sorted({c for rid in ids
                       for c in connected_devices.get(rid, {}).get("category", [])})
        resolved.append({**t, "ids": ids, "categories": cats})
    return resolved
