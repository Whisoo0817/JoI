"""Deterministic candidate matching and service selection."""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))

from .extractor import STOP, norm

SVCS = json.load(open(os.path.join(HERE, "effects.json")))["services"]
SVC_BY_ID = {s["svc"]: s for s in SVCS}
TAGS = json.load(open(os.path.join(HERE, "tag_lexicon.json")))["tags"]
ALIASES = json.load(open(os.path.join(HERE, "category_aliases.json")))["aliases"]

# 처방 규칙의 공식 저장처. 새 선호 규칙은 코드가 아니라 이 데이터에 추가한다.
PREFS = [
    {**p, "when_hint": tuple(p["when_hint"])} if "when_hint" in p else p
    for p in json.load(open(os.path.join(HERE, "preferences.json")))["preferences"]
]

ROLE_OK = {"action": {"action", "read_action"},
           "condition": {"read"},
           "read": {"read", "read_action"},
           "notify": {"action"}}

GENERIC_TOKENS = {"장치", "기기", "디바이스", "전부", "모두", "모든", "다"}
PARTICLES = ("으로", "이라고", "라고", "에게", "한테", "로", "을", "를", "이", "가",
             "은", "는", "에", "의", "와", "과", "도", "만", "들")
CHANNEL_CAT = {"스피커": "Speaker", "토스트": "ToastPublisher", "알림": "ToastPublisher"}
# 채널의 표준 전달 서비스 — notify 그룹은 어휘 매칭 없이 이걸 쓴다
CANON_NOTIFY = {"Speaker": "Speaker.Speak", "ToastPublisher": "ToastPublisher.Publish"}


def _strip_particle(tok):
    for p in PARTICLES:
        if tok.endswith(p) and len(tok) - len(p) >= 1:
            return tok[:-len(p)]
    return tok


def _tokens(hint):
    toks = [_strip_particle(t) for t in re.split(r"[\s,]+", hint) if t]
    return [t for t in toks if t and t not in GENERIC_TOKENS]


def _tag_hit(token, tag):
    """1글자 토큰은 트리거와 정확 일치만 인정 — '문'이 '창문'의 부분문자열로
    Window 태그를 잡는 오염을 막는다."""
    tn = norm(token)
    spec = TAGS.get(tag, {})
    if tn == norm(tag):
        return True
    for t in spec.get("triggers", []):
        t_n = norm(t)
        if tn == t_n or (len(tn) >= 2 and tn in t_n):
            return True
    return False
def _match_token_devices(token, devices, connected_cats):
    """한 토큰 → 그 토큰을 만족하는 디바이스 집합 + 매칭 근거."""
    tn = norm(token)
    ids, why = set(), []
    for did, d in devices.items():
        nick = norm(d.get("nickname", ""))
        if tn and ((len(tn) >= 2 and tn in nick)
                   or (len(tn) == 1 and any(tn == norm(w) for w in
                                            d.get("nickname", "").split()))):
            ids.add(did); why.append("nickname")
    tag_ids = set()
    for tag in TAGS:
        if _tag_hit(token, tag):
            hosts = {did for did, d in devices.items() if tag in d["tags"]}
            spec = TAGS[tag]
            if spec.get("host_category"):
                hosts = {did for did in hosts
                         if spec["host_category"] in devices[did]["category"]}
            if hosts:
                tag_ids |= hosts; why.append(f"tag:{tag}")
    ids |= tag_ids
    cat_ids = set()
    for cat in connected_cats:
        # 디바이스 식별은 ALIASES만 사용 — 효과 트리거는 타 디바이스 이름을
        # 문맥으로 포함할 수 있어 식별에 쓰면 오염됨 ('카메라 사진 메일로…')
        names = [cat] + ALIASES.get(cat, [])
        if any((len(tn) >= 2 and tn == norm(a)) or
               (len(tn) >= 2 and tn in norm(a) and len(norm(a)) - len(tn) <= 2) or
               (len(tn) == 1 and tn == norm(a))
               for a in names):
            cat_ids |= {did for did, d in devices.items() if cat in d["category"]}
            why.append(f"cat:{cat}")
    # 특이성 규칙: 태그가 카테고리의 부분집합이면 더 좁은 태그가 이긴다
    # ("문" → ContactSensor 4대 ⊃ Door 1대 → Door). 서로소면 합집합
    # ("불" → Light 10대 ⊍ LightSwitch 6대 → 16대, 외재적 affordance).
    if tag_ids and cat_ids and tag_ids < cat_ids:
        ids -= (cat_ids - tag_ids)
    else:
        ids |= cat_ids
    return ids, why


def _select_service(cluster_ids, devices, effect_hint, role):
    """클러스터의 카테고리 소유 서비스 중 effect에 맞는 것 선택 (+prefs)."""
    cats = {c for did in cluster_ids for c in devices[did]["category"]}
    en = norm(effect_hint or "")
    ok_roles = ROLE_OK.get(role, {"action", "read", "read_action"})

    # on/off/toggle intent: Switch-first, Light fallback (generalized live rule).
    # Switch도 Light도 없으면 None → 전원 의도 불충족 클러스터는 드롭됨
    # (baseline 오라클: 투야 버튼/화재센서/카메라는 '다 꺼줘'에서 제외)
    # 밝기/레벨 지정은 on/off 축약보다 우선 ("20 퍼센트만 켜줘")
    if role == "action" and en and "Light" in cats \
            and any(w in en for w in ("밝기", "퍼센트", "%")):
        return "Light.MoveToBrightness"
    if role == "action" and en:
        # '실행시켜줘/작동시키면'의 '켜'는 전원 의도가 아니다 — 사동 어미
        # '시켜/시키'를 지우고 본다 (2026-08-14, 388행 실측에서 발견).
        en_power = en.replace("시켜", "").replace("시키", "")
        for word, sw, lf in (("켜", "Switch.On", "Light.MoveToBrightness"),
                             ("꺼", "Switch.Off", "Light.MoveToBrightness"),
                             ("토글", "Switch.Toggle", None),
                             ("끄", "Switch.Off", "Light.MoveToBrightness")):
            if word in en_power:
                if "Switch" in cats:
                    return sw
                if "Light" in cats and lf:
                    return lf
                return None
    scored = {}
    stop_n = {norm(x) for x in STOP}
    for s in SVCS:
        cat = s["svc"].split(".")[0]
        if cat not in cats or s["role"] not in ok_roles:
            continue
        best = 0
        for trig in s.get("ko_triggers", []):
            tn = norm(trig)
            if not tn:
                continue
            if tn in en or (en and en in tn):
                best = max(best, min(len(tn), len(en)) * 2)
            else:
                sc = 0
                for t in re.split(r"\s+", trig):
                    t_n = norm(t)
                    if len(t_n) < 2 or t_n in stop_n:
                        continue
                    if t_n in en:
                        sc += len(t_n)
                    else:
                        # 어간 프리픽스 매칭: '촬영해줘' vs '촬영하고' → '촬영'
                        for plen in range(len(t_n), 1, -1):
                            if t_n[:plen] in en:
                                sc += plen if plen >= 2 else 0
                                break
                best = max(best, sc)
        if best > 0:
            scored[s["svc"]] = best
    if not scored:
        # 어휘 매칭 실패 폴백: 역할 적합 서비스가 클러스터에 단 하나뿐이면 그것
        # ("챗봇에게 삼행시 지어달라고" → ChatProvider의 유일 서비스 Chat)
        only = [s["svc"] for s in SVCS
                if s["svc"].split(".")[0] in cats and s["role"] in ok_roles]
        if len(only) == 1:
            return only[0]
        if role == "condition" and only:
            # 조건절 폴백: 그 카테고리의 대표(첫) read 값
            # ("미세먼지 좋음이면" → AirQualitySensor의 첫 값)
            return only[0]
        return None
    # preference rules: demote `over` when its `prefer` sibling is also viable
    for p in PREFS:
        if p["prefer"] in scored and p["over"] in scored:
            if "when_hint" in p and not any(w in (effect_hint or "")
                                            for w in p["when_hint"]):
                continue
            scored[p["over"]] = -1
    return max(scored, key=scored.get)


def _cat_vocab_hit_any(effect_hint, svc):
    en = norm(effect_hint)
    return any(norm(t) in en or en in norm(t)
               for t in svc.get("ko_triggers", []) if norm(t))
