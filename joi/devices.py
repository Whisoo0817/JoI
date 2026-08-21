# -*- coding: utf-8 -*-
"""IR 서비스 × 연결 기기 → 기기 고르기 + 수량 + 셀렉터 (LLM 없음, 순수 파이썬).

joi_slm 이 만든 Timeline IR 은 서비스 수준(`Category.Method`)이고 기기를 안 고른다.
여기서 서비스마다 "어느 기기들인지"를 어휘 조인으로 고른다 — mapping_v2 방식을
런타임으로 옮긴 것 (실험: slm/experiments/map/select_devices.py 0.982, hub_test 45/45).

절차 (서비스마다):
  1. 후보     : 서비스 카테고리를 가진 연결 기기 전부
  2. 기기 명사: 절 텍스트의 명사("에어컨", "불", "문")를 카테고리 별칭 + 태그 어휘로 대조
               → 가리킨 기기 집합으로 좁힘. 태그 집합이 별칭 집합의 진부분집합이면
               태그가 이김("문"→ContactSensor 4대 ⊃ Door 1대 → Door). 서로소면 합집합
               ("불"→Light ∪ LightSwitch).
  3. 한정어   : 장소·구역·브랜드 태그("거실", "구역1", "삼성") + 닉네임 어절("6구 3",
               "큰거") 매칭으로 더 좁힘. 절에 없으면 명령 전체에서 상속(coref).
               오타는 자모 퍼지 매칭(정확 매칭이 하나도 없을 때만).
  4. 수량     : 사용자가 말한 수량어가 우선(모두→all, 하나라도→any, 하나만→one).
               없으면 기기 1대→없음 / 조건·읽기→any / 실행→all.
               예외: 부재 조건("사람이 없으면", "감지되지 않")은 모든 센서가 부재여야
               하므로 all (mapping_v2 정책 그대로 — 다른 센서로 일반화하지 않음).
  5. 셀렉터   : 고른 집합을 정확히 잡는 최소 태그 조합 → `(#거실 #Light)` 꼴.
               태그로 못 잡는 1대는 기기 id 태그로.

절↔서비스 연결은 매핑 결과(ranked/parts)에서 역추적한다 — IR 을 바꾸지 않는다.

자리(등장)별 기기: 같은 서비스가 조건 안에 두 번 이상 나오고("거실 온도가 28도
이상이거나 침실 온도가 30도 이상이면" → TemperatureSensor.Temperature 두 번)
조건 조각도 그 수만큼 있으면, 등장마다 자기 조각으로 기기를 따로 고른다
(자리1=거실, 자리2=침실). 한 조각에 장소 둘을 한 번에 부른 글("거실과 침실에 모두")은
장소마다 한 벌씩 나눠 조각을 만든다. 조각 수가 안 맞으면 지금처럼 한 묶음(병합)으로 둔다.
자리 순서는 게이트가 IR 을 걷는 순서와 같다(occurrences_in_ir).
기기 없는 서비스가 하나라도 있으면 `MissingDevices` (부분 실현 금지).
Clock·GlobalVariable 은 기기가 아니므로 셀렉터를 만들지 않는다.
"""

from __future__ import annotations

import difflib
import json
import os
import re
from itertools import combinations
from typing import Any

# ── 어휘 자산 (joi_slm/assets — 컴파일 산출물) ──────────────────────────────
_ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "joi_slm", "assets")
ALIASES: dict[str, list] = json.load(open(os.path.join(_ASSETS, "category_aliases.json")))["aliases"]
TAG_KIND: dict[str, dict] = json.load(open(os.path.join(_ASSETS, "tag_lexicon.json")))["tags"]
TAG_KO: dict[str, list] = json.load(open(os.path.join(_ASSETS, "tag_ko.json")))["tags"]
for _t, _v in list(TAG_KO.items()):            # "구역 1" ↔ "1 구역" 숫자 변형 양방향 생성
    for _tr in list(_v):
        m = re.match(r"^(\d+)\s*(\S+)$", _tr)
        if m: _v.append(m.group(2) + m.group(1))
        m = re.match(r"^(\S+?)\s*(\d+)$", _tr)
        if m: _v.append(m.group(2) + m.group(1))

# 카테고리 이름 자체는 기기 종류이지 한정어가 아님. 능력 태그(LightSwitch)·규약 태그도 한정어 제외.
CAT_TAGS = set(ALIASES.keys()) | {"Switch", "Light"}
AFFORD = {t for t, v in TAG_KIND.items() if v.get("kind") in ("affordance", "fixture")}
NOT_QUALIFIER = {"NoneNecessary"} | AFFORD          # Main 은 규약 태그지만 "메인"을 직접 말하면 한정어로 침
BRAND_TAGS = {t for t, v in TAG_KIND.items() if v.get("kind") == "brand"}
BRAND_KO = {"삼성": ["삼성", "samsung"], "kt": ["kt", "케이티"], "lg": ["lg", "엘지"], "미로": ["미로"],
            "hue": ["휴", "hue", "필립스"], "aqara": ["아카라", "aqara"], "스카이라이트": ["스카이라이트"],
            "스마트빌": ["스마트빌"], "헤이홈": ["헤이홈", "hejhome"]}

# 서비스 이름 `Category.Method` — 조건식(cond/until) 안에서도 이 모양으로 나온다.
_SVC_RE = re.compile(r"\b([A-Z][A-Za-z0-9]*)\.([A-Za-z][A-Za-z0-9]*)\b")
NON_DEVICE = {"Clock", "GlobalVariable"}


class MissingDevices(ValueError):
    """IR 이 쓰는 서비스의 카테고리를 가진 연결 기기가 없다."""
    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__("연결된 기기 없음: " + ", ".join(missing))


# ── 문자 정규화 + 퍼지 매칭 (hub_test 검증) ────────────────────────────────
_NUM = {"일": "1", "이": "2", "삼": "3", "사": "4", "오": "5", "육": "6", "칠": "7", "팔": "8", "구": "9"}
_ORD = {"첫번째": "1", "첫": "1", "두번째": "2", "둘째": "2", "세번째": "3", "셋째": "3",
        "네번째": "4", "넷째": "4", "다섯번째": "5", "여섯번째": "6"}
_ENKO = {"lamp": "램프", "switch": "스위치", "plug": "플러그", "sensor": "센서", "dial": "다이얼", "tap": "탭",
         "dimmer": "디머", "light": "라이트", "wifi": "와이파이", "kt": "케이티", "lg": "엘지"}


def _norm(x: str) -> str:
    x = x.lower()
    for k, v in _ORD.items(): x = x.replace(k, v)
    x = re.sub(r"(?<=구역)\s*([일이삼사오육칠팔구])", lambda m: _NUM[m.group(1)], x)
    x = re.sub(r"([일이삼사오육칠팔구])(?=\s*(번|층|호|구))", lambda m: _NUM[m.group(1)], x)
    x = re.sub(r"[\s_\-()]", "", x)
    for k, v in _ENKO.items(): x = re.sub(rf"(?<![a-z]){k}(?![a-z])", v, x)
    return x


def _camel(t: str) -> str:
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Za-z])(?=[0-9])", " ", t).replace("_", " ")


_PARTICLE = re.compile(r"(에서는|에서|으로|로|은|는|이|가|을|를|의|에|과|와|도|만|들|이라도|라도)$")


def _words(text: str) -> list[str]:
    out = []
    for w in re.split(r"[\s,.\"'()]+", text):
        if not w: continue
        out.append(w)
        w2 = _PARTICLE.sub("", w)
        if w2 and w2 != w: out.append(w2)
    return list(dict.fromkeys(out))


_CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"; _JUNG = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
_JONG = " ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ"


def _jamo(s: str) -> str:
    out = []
    for ch in s:
        c = ord(ch)
        if 0xAC00 <= c <= 0xD7A3:
            c -= 0xAC00; out += [_CHO[c // 588], _JUNG[(c % 588) // 28]] + ([_JONG[c % 28]] if c % 28 else [])
        else: out.append(ch)
    return "".join(out)


_FUZZ = 0.84


def _fuzzy_hit(text: str, triggers: list[str]) -> bool:
    """트리거가 절의 어절(또는 인접 2어절)과 자모 편집거리 유사 ≥ 0.84 면 매칭. 3자 미만은 정확 일치만."""
    ws = [_norm(w) for w in re.split(r"[\s,.]+", text) if w]
    ws2 = ws + [ws[i] + ws[i + 1] for i in range(len(ws) - 1)]
    for tr in triggers:
        tn = _norm(tr)
        if len(tn) < 3: continue
        for w in ws2:
            w2 = _PARTICLE.sub("", w)
            for cand in (w, w2):
                if len(cand) < 3 or abs(len(cand) - len(tn)) > 2: continue
                if re.findall(r"\d", cand) != re.findall(r"\d", tn): continue          # 숫자는 정확히
                if bool(re.search(r"[a-z]", cand)) != bool(re.search(r"[a-z]", tn)): continue
                if difflib.SequenceMatcher(None, _jamo(cand), _jamo(tn)).ratio() >= _FUZZ:
                    return True
    return False


def _hit_text(text: str, triggers: list[str]) -> bool:
    """2자 이상 트리거는 정규화 문자열 포함, 1자('불','문','등')는 조사 뗀 어절과 정확 일치만
    ('문'이 '창문'의 부분문자열로 오염되는 것 방지)."""
    tn_text = _norm(text)
    ws = {_norm(w) for w in _words(text)}
    for tr in triggers:
        tn = _norm(tr)
        if not tn: continue
        if len(tn) >= 2 and tn in tn_text: return True
        if len(tn) == 1 and tn in ws: return True
    return False


def _tags_of(dev: dict) -> set[str]:
    cats = dev.get("category", [])
    if isinstance(cats, str): cats = [cats]
    return set(cats) | set(dev.get("tags", []))


def _cats_of(dev: dict) -> set[str]:
    cats = dev.get("category", [])
    if isinstance(cats, str): cats = [cats]
    return {c for c in cats if isinstance(c, str)}


# ── 2. 기기 명사 좁히기: "에어컨", "불", "문" → 가리킨 기기 집합 ────────────
def noun_buckets(text: str, devices: dict) -> list[tuple[str, set[str]]]:
    """절 텍스트가 이름으로 가리킨 기기 묶음들 [(이름표, 기기 집합), ...].
    별칭(카테고리) 묶음과 태그(능력·붙박이) 묶음 — 셀렉터를 묶음별로 쪼갤 때도 쓴다."""
    buckets: list[tuple[str, set[str]]] = []
    for cat, names in ALIASES.items():
        if _hit_text(text, names + [cat]):
            ids = {d for d, v in devices.items() if cat in _cats_of(v)}
            if ids: buckets.append((cat, ids))
    for t in AFFORD:
        if _hit_text(text, TAG_KO.get(t, []) + [t]):
            hosts = {d for d, v in devices.items() if t in v.get("tags", [])}
            host_cat = TAG_KIND.get(t, {}).get("host_category")
            if host_cat: hosts = {d for d in hosts if host_cat in _cats_of(devices[d])}
            if hosts: buckets.append((t, hosts))
    return buckets


def noun_devices(text: str, devices: dict) -> set[str]:
    """가리킨 기기 집합 (비면 명사 없음 = 안 좁힘).
    태그 집합 ⊂ 별칭 집합이면 태그가 이김("문"→ContactSensor 4대 ⊃ Door 1대), 아니면 합집합."""
    B = noun_buckets(text, devices)
    cat_ids = set().union(*(ids for name, ids in B if name in ALIASES)) if B else set()
    tag_ids = set().union(*(ids for name, ids in B if name not in ALIASES)) if B else set()
    if tag_ids and cat_ids and tag_ids < cat_ids:
        return tag_ids
    return tag_ids | cat_ids


# ── 3. 한정어 좁히기: 장소·구역·브랜드 태그 + 닉네임 ───────────────────────
def _tag_hits(text: str, cand_tags: set[str], fuzzy: bool = True) -> set[str]:
    hits = set()
    for t in cand_tags:
        trig = TAG_KO.get(t, []) + [t, _camel(t)]
        if t == "Main":                                    # 규약 태그: 정확 발화("메인")만, 퍼지 금지
            if _hit_text(text, trig): hits.add(t)
            continue
        if _hit_text(text, trig) or (fuzzy and _fuzzy_hit(text, trig)):
            hits.add(t)
    return hits


def _nick_score(text: str, dev: dict, skip_brand: bool, fuzzy: bool) -> int:
    """닉네임 어절이 절에 나오면 점수. 숫자 어절은 다른 어절 자리를 지운 뒤 독립 숫자로만 대조
    ('6구 3' vs '6구 6'). 브랜드 어절은 태그가 이미 잡았으면 중복 계산 안 함."""
    nick = dev.get("nickname", "")
    if not nick: return 0
    tn = _norm(text).replace("에이컨", "에어컨")
    toks = [t for t in re.split(r"[\s()]+", nick) if t]
    for t in list(toks):                                   # "큰거/작은거" → "큰/작은" 변형
        m = re.match(r"^(.+?)(거|것)$", t)
        if m and len(m.group(1)) >= 1: toks.append(m.group(1))
    score, rest = 0, tn
    for t in toks:
        t2 = _norm(t)
        if t2.isdigit(): continue
        brand = any(t2 == k or t2 in vs for k, vs in BRAND_KO.items())
        if (len(t2) >= 2 and t2 in tn) or (len(t2) == 1 and t2 in {_norm(w) for w in re.split(r"\s+", text)}):
            if not (brand and skip_brand): score += len(t2) if len(t2) >= 2 else 2
            rest = rest.replace(t2, "#")
        elif brand and not skip_brand:
            for k, vs in BRAND_KO.items():
                if (t2 == k or t2 in vs) and any(_norm(v) in tn for v in vs): score += len(t2)
    for t in toks:
        t2 = _norm(t)
        if t2.isdigit() and re.search(rf"(?<!\d){t2}(?!\d)", rest): score += 1
    if score == 0 and fuzzy:
        for t in toks:
            t2 = _norm(t)
            if len(t2) >= 3 and not (skip_brand and any(t2 == k or t2 in vs for k, vs in BRAND_KO.items())) \
                    and _fuzzy_hit(text, [t2]):
                score += len(t2) - 1
    return score


def qualifier_devices(text: str, cands: set[str], devices: dict) -> tuple[set[str], set[str]]:
    """한정어(태그+닉네임)로 후보를 좁힌다 → (좁힌 집합, 맞은 태그). 못 좁히면 (cands, ∅)."""
    cand_tags = {t for d in cands for t in devices[d].get("tags", [])
                 if not str(t).startswith("tc0_")} - CAT_TAGS - NOT_QUALIFIER
    thits = _tag_hits(text, cand_tags)
    by_tag = {d for d in cands if set(devices[d].get("tags", [])) & thits}
    if len(thits) >= 2:                                    # 여러 태그: 교집합 우선("섹터 비의 홀수 금고"), 서로소면 합집합
        inter = {d for d in cands if thits <= set(devices[d].get("tags", []))}
        if inter: by_tag = inter
    skip_brand = bool(thits & BRAND_TAGS)
    ns = {d: _nick_score(text, devices[d], skip_brand, fuzzy=False) for d in cands}
    if max(ns.values(), default=0) == 0:                   # 정확 매칭이 하나도 없을 때만 퍼지
        ns = {d: _nick_score(text, devices[d], skip_brand, fuzzy=True) for d in cands}
    top = max(ns.values()) if ns else 0
    by_nick = {d for d, v in ns.items() if v == top and v > 0}
    if by_tag and by_nick and by_tag & by_nick: return by_tag & by_nick, thits
    if by_nick and top >= 2: return by_nick, thits
    if by_tag: return by_tag, thits
    return cands, set()


# ── 4. 수량 ─────────────────────────────────────────────────────────────────
_Q_ALL = re.compile(r"모두|모든|전부|전체|둘 다|셋 다|양쪽|각각|싹|(?<![가-힣])다(?=\s*(꺼|켜|끄|열|닫|잠|올|내|틀))")
_Q_ANY = re.compile(r"(하나|한\s*곳|한\s*개|한\s*대|어느\s*것|어떤\s*것|어느\s*하나)이?라도|중\s*하나|어느\s*\S{0,6}(라도|든)")
_Q_ONE = re.compile(r"하나만|한\s*개만|한\s*대만|아무거나\s*하나")
_ABSENT = re.compile(r"없으면|없는|없을|부재|비어|안\s*보이|감지되지\s*않|감지\s*안\s*되|않으면|않았")
_ABSENT_CATS = ("PresenceSensor", "MotionSensor")          # 부재 조건 all 예외 대상 (일반화 금지 — mapping_v2 정책)


def quantifier(text: str, role: str, pred: set[str], devices: dict) -> str:
    """수량 접두사 '', 'all', 'any'. 사용자 수량어가 우선, 없으면 (기기 수, 자리)로.
    any 를 all 보다 먼저 본다 — "모든 조명이 하나라도 켜져 있으면"은 any."""
    if _Q_ONE.search(text): return ""
    if _Q_ANY.search(text): return "any" if len(pred) > 1 else ""
    if _Q_ALL.search(text): return "all" if len(pred) > 1 else ""
    if len(pred) <= 1: return ""
    if role in ("condition", "read"):
        if _ABSENT.search(text) and any(c in _cats_of(devices[d]) for d in pred for c in _ABSENT_CATS):
            return "all"                                    # 부재는 모든 센서가 부재여야 함
        return "any"
    return "all"


# ── 5. 최소 태그 조합 → 셀렉터 ─────────────────────────────────────────────
def min_tags(pred: set[str], devices: dict) -> tuple[list[str], bool]:
    """pred 를 정확히 잡는 가장 작은 태그 조합 → (tags, exact). 없으면 ([], False).
    tc0_ 실 id·인프라 태그와 NoneNecessary 는 후보에서 뺀다. 크기 3까지만 탐색."""
    M = set(pred)
    if not M: return [], False
    common = set.intersection(*(_tags_of(devices[k]) for k in M))
    cands = [t for t in common if not str(t).startswith("tc0_") and t != "NoneNecessary"]
    cands.sort(key=lambda t: (t in ("Switch", "Matter"), str(t)))      # 범용 태그는 뒤로

    def select(T):
        T = set(T)
        return {k for k in devices if T <= _tags_of(devices[k])}

    for size in range(1, min(len(cands), 3) + 1):
        for combo in combinations(cands, size):
            if select(combo) == M:
                return list(combo), True
    if len(M) == 1: return [], False                        # 1대는 호출자가 id 로 잡음
    return cands[:3], False                                 # 근사: 공통 태그(상위집합일 수 있음)


# ── 절↔서비스 연결: 매핑 결과에서 역추적 ───────────────────────────────────
def svc_texts(slm_out: dict) -> dict[str, str]:
    """서비스 → 그 서비스를 낳은 절 텍스트(들). ranked top-5 와 조건 부분 재질의(parts)에서 찾는다."""
    if not slm_out: return {}
    segs = {s["j"]: s.get("text", "") for s in slm_out.get("segments", [])}
    ranked = (slm_out.get("mapping") or {}).get("ranked") or {}
    parts = (slm_out.get("mapping") or {}).get("parts") or {}
    out: dict[str, list] = {}
    for j, lst in ranked.items():
        for s in lst:
            out.setdefault(s, []).append(segs.get(int(j), ""))
    for j, plist in parts.items():
        for p in plist or []:
            for s in p.get("ranked", []):
                out.setdefault(s, []).append(p.get("part") or segs.get(int(j), ""))
    return {s: " ".join(dict.fromkeys(t for t in v if t)) for s, v in out.items()}


def services_in_ir(ir: dict) -> dict[str, str]:
    """IR 안의 서비스 → 자리(role) 표. 순서는 IR 등장 순.
    role: 'action'(call.target) / 'condition'(if.cond, wait.cond, cycle.until) / 'read'(read.src)
    한 서비스가 여러 자리에 나오면 먼저 나온 자리를 유지하되 action 이 있으면 action."""
    roles: dict[str, str] = {}

    def put(svc: str, role: str) -> None:
        if svc not in roles or (role == "action" and roles[svc] != "action"):
            roles[svc] = role

    def scan_expr(src: Any, role: str) -> None:
        if isinstance(src, str):
            for cat, name in _SVC_RE.findall(src):
                put(f"{cat}.{name}", role)

    def walk(steps: list) -> None:
        for s in steps or []:
            if not isinstance(s, dict): continue
            op = s.get("op")
            if op == "call":
                t = s.get("target", "")
                if isinstance(t, str) and "." in t:
                    put(t, "action")
                for v in (s.get("args") or {}).values():
                    scan_expr(v, "read")
            elif op == "read":
                if isinstance(s.get("src"), str): put(s["src"], "read")
            elif op == "if":
                scan_expr(s.get("cond"), "condition")
                walk(s.get("then") or []); walk(s.get("else") or [])
            elif op == "wait":
                scan_expr(s.get("cond"), "condition")
            elif op == "cycle":
                scan_expr(s.get("until"), "condition")
                walk(s.get("body") or [])

    walk((ir or {}).get("timeline") or [])
    return roles


def _unquoted(src: str) -> str:
    """따옴표 안 글은 서비스 이름으로 안 센다(게이트와 같은 규칙)."""
    return re.sub(r'"[^"]*"|\'[^\']*\'', '""', src)


def occurrences_in_ir(ir: dict) -> list[tuple[str, str]]:
    """IR 안의 서비스 등장(자리)을 게이트가 걷는 순서 그대로 → [(svc, role), ...].
    순서: 줄 순서대로, 한 줄 안에서는 cond/until(왼→오) → read src → call target → call 인자
    → 딸린 줄(then/else/body). 게이트(gate._Rewriter.walk)와 같아야 자리 번호(Cat, Cat#2 …)가 맞는다."""
    out: list[tuple[str, str]] = []

    def scan(src: Any, role: str) -> None:
        if isinstance(src, str):
            for cat, name in _SVC_RE.findall(_unquoted(src)):
                out.append((f"{cat}.{name}", role))

    def walk(steps: list) -> None:
        for s in steps or []:
            if not isinstance(s, dict): continue
            for f in ("cond", "until"):
                if s.get(f): scan(s[f], "condition")
            if s.get("op") == "read" and isinstance(s.get("src"), str) and "." in s["src"]:
                out.append((s["src"], "read"))
            if s.get("op") == "call":
                t = s.get("target", "")
                if isinstance(t, str) and "." in t: out.append((t, "action"))
                for v in (s.get("args") or {}).values(): scan(v, "read")
            for v in s.values():
                if isinstance(v, list): walk(v)

    walk((ir or {}).get("timeline") or [])
    return out


def cond_pieces(slm_out: dict | None) -> list[tuple[str, list[str]]]:
    """조건(·읽기) 절들을 조각 단위로 IR 순서대로 → [(조각 글, 그 조각의 후보 서비스들)].
    매핑이 조각(parts)을 남긴 절은 조각마다, 아니면 절 하나가 조각 하나."""
    segs = (slm_out or {}).get("segments") or []
    mp = (slm_out or {}).get("mapping") or {}
    parts, ranked = mp.get("parts") or {}, mp.get("ranked") or {}
    out = []
    for s in segs:
        if s.get("type") not in ("COND", "TRIG", "READ"): continue
        j = s.get("j")
        ps = parts.get(j) or parts.get(str(j))
        if ps:
            out += [(p.get("part") or s.get("text", ""), list(p.get("ranked") or [])) for p in ps]
        else:
            out.append((s.get("text", ""), list(ranked.get(j) or ranked.get(str(j)) or [])))
    return out


_PAIR = re.compile(r"(\S+?)(과|와|랑|및|이나|나)\s+(\S+?)(?=에|의|이|가|은|는|도|\s|,)")


def split_place_pair(text: str, cand_tags: set[str]) -> list[str] | None:
    """"거실과 침실에 모두 …" 처럼 장소 둘을 한 번에 부른 글 → 장소마다 한 벌씩
    ["거실에 모두 …", "침실에 모두 …"]. 두 낱말이 서로 다른 한정어 태그에 맞을 때만."""
    for m in _PAIR.finditer(text):
        a, b = m.group(1), m.group(3)
        ha, hb = _tag_hits(a, cand_tags, fuzzy=False), _tag_hits(b, cand_tags, fuzzy=False)
        if ha and hb and ha != hb:
            rest = text[m.end():]
            return [text[:m.start()] + a + rest, text[:m.start()] + b + rest]
    return None


# ── 능력 검사: 전원 의도인데 가리킨 기기가 서비스 카테고리 밖이면 Switch 로 ──
_POWER_ON = re.compile(r"켜|틀어|가동|점등")
_POWER_OFF = re.compile(r"꺼|끄|소등")
_BRIGHT_COLOR = re.compile(r"\d+\s*(%|퍼센트)|밝기|밝게|어둡|색")


def capability_fix(ir: dict, connected_devices: dict, texts: dict[str, str], full_text: str) -> list[tuple[str, str]]:
    """IR 의 call 을 제자리에서 고친다 → [(원래 svc, 바꾼 svc)].
    "전등 스위치 6구 3번 켜줘": 매핑 관례는 조명 켜기=Light.MoveToBrightness 지만 가리킨 기기
    (벽스위치)는 Switch 뿐 → 전원 의도(켜/꺼, 밝기·색 지정 없음)이고 가리킨 기기 전부가 Switch 를
    가지면 Switch.On/Off 로 바꾼다. 가리킨 기기가 서비스 카테고리로 다 커버되면 안 바꾼다."""
    swaps: list[tuple[str, str]] = []

    def fix(steps: list) -> None:
        for s in steps or []:
            if not isinstance(s, dict): continue
            op = s.get("op")
            if op == "call":
                svc = s.get("target", "")
                if isinstance(svc, str) and "." in svc and not svc.startswith("Switch."):
                    text = texts.get(svc) or full_text
                    if not _BRIGHT_COLOR.search(text):
                        want = "Switch.Off" if _POWER_OFF.search(text) else \
                               "Switch.On" if _POWER_ON.search(text) else None
                        nouns = noun_devices(text, connected_devices)
                        if want and nouns:
                            cat = svc.split(".", 1)[0]
                            covered = {d for d in nouns if cat in _cats_of(connected_devices[d])}
                            with_sw = {d for d in nouns if "Switch" in _cats_of(connected_devices[d])}
                            if covered != nouns and with_sw == nouns:
                                swaps.append((svc, want))
                                s["target"] = want; s["args"] = {}
                                texts.setdefault(want, text)
            elif op == "if":
                fix(s.get("then") or []); fix(s.get("else") or [])
            elif op == "cycle":
                fix(s.get("body") or [])

    fix((ir or {}).get("timeline") or [])
    return swaps


# ── 본체 ────────────────────────────────────────────────────────────────────
def pick_devices(text: str, full_text: str, cands: set[str], devices: dict) -> tuple[set[str], set[str]]:
    """절 텍스트로 후보를 좁힌다: 기기 명사 → 한정어(절에 없으면 명령 전체 상속)."""
    nouns = noun_devices(text, devices)
    if nouns and nouns & cands:
        cands = nouns & cands
    pred, thits = qualifier_devices(text, cands, devices)
    # coref: 절에 한정어가 없으면 명령 전체에서 상속. 단 절에 수량어("모든 불", "하나라도")가
    # 있으면 전체를 뜻하므로 다른 절의 장소로 좁히면 안 됨.
    if pred == cands and full_text and full_text != text \
            and not (_Q_ALL.search(text) or _Q_ANY.search(text)):
        pred, thits = qualifier_devices(full_text, cands, devices)
    return pred, thits


def _selector_parts(pred: set[str], text: str, cat: str, devices: dict) -> list[list[str]]:
    """pred 를 잡는 태그 조합(들). 한 조합으로 정확히 안 잡히면(합집합: "조명"=Light ∪ 벽스위치)
    명사 묶음별로 쪼개 여러 조합으로 — 셀렉터 여러 개는 합집합으로 읽힌다."""
    tags, exact = min_tags(pred, devices)
    if exact or len(pred) == 1:
        return [tags or sorted(pred)]                       # 1대인데 태그로 못 잡으면 기기 id 태그
    parts, rest = [], set(pred)
    for _, ids in noun_buckets(text, devices):
        c = rest & ids
        if not c: continue
        t2, e2 = min_tags(c, devices)
        if e2:
            parts.append(t2); rest -= c
    if rest:
        t3, _ = min_tags(rest, devices)
        parts.append(t3 or [cat])
    return parts if parts else [tags or [cat]]


def build_selectors(ir: dict, connected_devices: dict, slm_out: dict | None = None) -> dict:
    """→ {"selectors": {svc: ["<quant>(#태그 ...)", ...]}, "resolved": {svc: {"q", "devices", "tags", "text"}},
          "selected_services": [...], "roles": {...}, "ir": (능력 검사로 고친) IR, "swaps": [...]}"""
    texts = svc_texts(slm_out or {})
    full_text = " ".join(s.get("text", "") for s in (slm_out or {}).get("segments", []))
    swaps = capability_fix(ir, connected_devices or {}, texts, full_text)
    roles = services_in_ir(ir)
    occ = occurrences_in_ir(ir)
    pieces = cond_pieces(slm_out)
    selectors, resolved, slots, missing = {}, {}, {}, []
    for svc, role in roles.items():
        cat = svc.split(".", 1)[0]
        if cat in NON_DEVICE: continue
        cands = {k for k, d in (connected_devices or {}).items()
                 if isinstance(d, dict) and cat in _cats_of(d)}
        if not cands:
            missing.append(svc); continue
        text = texts.get(svc) or full_text
        pred, thits = pick_devices(text, full_text, cands, connected_devices)
        q = quantifier(text, role, pred, connected_devices)
        parts = _selector_parts(pred, text, cat, connected_devices)
        selectors[svc] = [f"{q}(#" + " #".join(p) + ")" for p in parts]
        resolved[svc] = {"q": q or "one", "devices": sorted(pred),
                         "tags": [t for p in parts for t in p], "text": text}
        # 자리별 기기: 조건·읽기 자리에 같은 서비스가 여러 번 + 조각도 그만큼
        n_occ = [r for s_, r in occ if s_ == svc]
        if len(n_occ) >= 2 and all(r in ("condition", "read") for r in n_occ) and len(cands) >= 2:
            ptexts = [t for t, rk in pieces if svc in rk] or [text]
            if len(ptexts) == 1 and len(n_occ) == 2:
                cand_tags = {t for d in cands for t in connected_devices[d].get("tags", [])
                             if not str(t).startswith("tc0_")} - CAT_TAGS - NOT_QUALIFIER
                ptexts = split_place_pair(ptexts[0], cand_tags) or ptexts
            if len(ptexts) == len(n_occ):
                infos = []
                for t in ptexts:
                    p_i, _ = pick_devices(t, full_text, cands, connected_devices)
                    q_i = quantifier(t, role, p_i, connected_devices)
                    parts_i = _selector_parts(p_i, t, cat, connected_devices)
                    if len(parts_i) != 1: infos = []; break
                    infos.append({"text": t, "q": q_i or "one", "devices": sorted(p_i),
                                  "tags": parts_i[0], "selector": f"{q_i}(#" + " #".join(parts_i[0]) + ")"})
                # 자리마다 고른 게 서로 다를 때만 쪼갠 값을 쓴다(다 같으면 병합과 같다)
                if infos and len({tuple(i["devices"]) for i in infos}) > 1:
                    resolved[svc]["slots"] = infos
                    slots[svc] = [i["selector"] for i in infos]
    if missing:
        raise MissingDevices(missing)
    # 자리 목록(게이트 걷기 순서): 바인딩 표(Cat, Cat#2 …)를 이 순서로 적는다
    occurrences, used = [], {}
    for svc, role in occ:
        info = resolved.get(svc)
        if info is None: continue
        k = used.get(svc, 0); used[svc] = k + 1
        sl = info.get("slots") or []
        src = sl[k] if k < len(sl) else info
        occurrences.append({"svc": svc, "role": role, "q": src["q"], "devices": list(src["devices"])})
    return {"selectors": selectors, "resolved": resolved, "slots": slots,
            "occurrences": occurrences,
            "selected_services": list(roles.keys()), "roles": roles,
            "ir": ir, "swaps": swaps}


def render_selectors(selectors: dict) -> str:
    """lowering 프롬프트의 `[Precision Selectors]` 블록 — 서비스마다 한 줄."""
    lines = [f"{svc}: " + " / ".join(sel) for svc, sel in (selectors or {}).items() if sel]
    return "\n".join(lines) if lines else "(none)"
