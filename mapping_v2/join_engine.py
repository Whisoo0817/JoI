"""Phase 3: deterministic join engine.

command → [extract_runner: constraint groups (LLM, environment-blind)]
        → THIS ENGINE (no LLM):
            device-side: nickname / tag / category token resolution, AND-join,
                         hard-constraint coverage check with attributed errors
            effect-side: service selection over the matched cluster's services,
                         preference rules, on/off Switch-first + Light fallback
            output:      OR-clusters with minimal_tags selectors, quantifier
                         (device_ontology.quantifier_for), chained sinks

Reuses production helpers verbatim: device_ontology.minimal_tags_for /
quantifier_for. Never touches production code.

Usage: /home/ikess/joi-llm/venv/bin/python join_engine.py        # demo cases
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
sys.path.insert(0, HERE)

from device_ontology import minimal_tags_for, quantifier_for  # noqa: E402
from gate_check import STOP, norm  # noqa: E402

SVCS = json.load(open(os.path.join(HERE, "effects.json")))["services"]
SVC_BY_ID = {s["svc"]: s for s in SVCS}
TAGS = json.load(open(os.path.join(HERE, "tag_lexicon.json")))["tags"]
ALIASES = json.load(open(os.path.join(HERE, "category_aliases.json")))["aliases"]

# 처방 규칙 — preferences.json이 공식 저장처 (구 device_rules 기본 섹션 후계).
# 새 선호 규칙은 코드가 아니라 그 파일에 추가한다.
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


def _token_in_trigger(tn, trig):
    """토큰-정밀 매칭: 1글자 토큰('불','문')은 트리거의 토큰과 정확 일치만 인정
    (부분문자열이면 불필요/문자열 따위에 오염됨). 2글자 이상은 substring 허용."""
    if len(tn) >= 2:
        return tn in norm(trig)
    return any(tn == norm(t) for t in re.split(r"\s+", trig))


def _cat_vocab_hit(token, cat):
    """token이 카테고리의 서비스 트리거 어휘에 등장하는가."""
    tn = norm(token)
    if not tn:
        return False
    if tn == norm(cat):
        return True
    for s in SVCS:
        if s["svc"].split(".")[0] != cat:
            continue
        for trig in s.get("ko_triggers", []):
            if _token_in_trigger(tn, trig):
                return True
    return False


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


class Resolution:
    def __init__(self):
        self.groups = []   # {role, clusters:[{ids, sel_tags, quant, service}], ...}
        self.errors = []


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


def resolve(command, devices, extract_fn):
    from extract_runner import match_hint  # effect-only 카테고리 후보용
    res = Resolution()
    connected_cats = {c for d in devices.values() for c in d["category"]}
    parsed = extract_fn(command)
    has_sink = any(g["role"] == "notify" for g in parsed["groups"])

    for g in parsed["groups"]:
        role, dh, eh = g["role"], g.get("device_hint"), g.get("effect_hint")
        clusters = []

        if role == "notify":
            cats = [CHANNEL_CAT[k] for k in CHANNEL_CAT if dh and k in dh] \
                or ["Speaker", "ToastPublisher"]  # 채널 미지정 기본 정책
            for cat in cats:
                ids = {d for d, v in devices.items() if cat in v["category"]}
                if ids:
                    clusters.append({"ids": ids, "svc": None,
                                     "canonical": CANON_NOTIFY[cat],
                                     "via": f"channel:{cat}"})
        elif dh:  # 디바이스 지칭 (hard)
            toks = _tokens(dh)
            per_token, missing = [], []
            for t in toks:
                ids, why = _match_token_devices(t, devices, connected_cats)
                (per_token.append((t, ids, why)) if ids else missing.append(t))
            # 수식어 관용: 일부 토큰만 해석되면 그것으로 진행 ("환기 알림" →
            # '환기'는 목적어 수식, '알림'이 디바이스). 전부 미해석일 때만 에러.
            if missing and per_token:
                missing = []
            if missing:
                res.errors.append(
                    f"'{dh}': 토큰 {missing} 에 해당하는 연결 디바이스 없음")
                continue
            joined = set.intersection(*(ids for _, ids, _ in per_token)) \
                if per_token else set()
            if not joined:
                detail = "; ".join(
                    f"'{t}'→{sorted({devices[i]['nickname'] for i in ids})[:3]}"
                    for t, ids, _ in per_token)
                res.errors.append(
                    f"'{dh}': 토큰 조합을 동시에 만족하는 디바이스 없음 ({detail})")
                continue
            # OR-cluster split: 외재적 affordance (Light-cat vs LightSwitch-tag)
            light = {d for d in joined if "Light" in devices[d]["category"]}
            lsw = {d for d in joined - light if "LightSwitch" in devices[d]["tags"]}
            rest = joined - light - lsw
            # 밝기/레벨 지정 효과는 Light 카테고리만 실현 가능 — 벽스위치
            # 클러스터는 On/Off밖에 못 하므로 여기서 드롭 (부분 실현 금지)
            level_effect = bool(eh) and any(w in eh for w in ("밝기", "퍼센트", "%"))
            for part in (light, lsw, rest):
                if part and not (level_effect and part is not light):
                    clusters.append({"ids": part, "svc": None, "via": "device-join"})
        elif eh:  # 서비스/효과 단위 (device free) — 효과가 집합을 결정
            # 효과 문구 안의 디바이스 명사가 우선 ("경제 뉴스" → NewsProvider);
            # 없을 때만 트리거 어휘 랭킹으로 폴백
            alias_cats = [c for c in connected_cats
                          for t in _tokens(eh)
                          if any(norm(t) == norm(a) for a in ALIASES.get(c, []))]
            for cat in alias_cats or match_hint(eh, connected_cats, top_n=3):
                ok = ROLE_OK.get(role, set())
                owns = any(s["role"] in ok for s in SVCS
                           if s["svc"].split(".")[0] == cat)
                ids = {d for d, v in devices.items() if cat in v["category"]}
                if owns and ids:
                    clusters.append({"ids": ids, "svc": None, "via": f"effect:{cat}"})
                    break
        if not clusters:
            if dh or eh:
                res.errors.append(f"그룹 해석 실패: role={role} dev={dh!r} eff={eh!r}")
            continue

        out_clusters, dropped = [], []
        for cl in clusters:
            svc = cl.get("canonical") \
                or (_select_service(cl["ids"], devices, eh, role) if eh else None)
            if dh and eh and svc is None and role in ("action", "read"):
                dropped.append(cl)  # 능력 없는 클러스터: 일단 보류
                continue
            if svc:  # 디바이스별 능력 검사 (Switch 없는 기기에 Switch.Off 방지)
                _cat = svc.split(".")[0]
                cl["ids"] = {d for d in cl["ids"] if _cat in devices[d]["category"]}
                if not cl["ids"]:
                    dropped.append(cl)
                    continue
            tags, exact = minimal_tags_for(cl["ids"], devices)
            quant = quantifier_for(g.get("quantifier") or "auto", role, len(cl["ids"]))
            if tags and exact:
                out_clusters.append({**cl, "svc": svc, "sel": tags,
                                     "quant": quant, "exact": True})
            else:
                # 어떤 태그 조합으로도 이 집합만 골라낼 수 없다 (형제 디바이스가
                # 의미 태그를 공유 — 예: 삼성/KT 공기청정기가 태그 동일).
                # 공통 태그를 쓰면 남을 과선택하므로 디바이스별 id로 쪼갠다.
                for did in sorted(cl["ids"]):
                    out_clusters.append({**cl, "ids": {did}, "svc": svc,
                                         "sel": [did], "quant": "",
                                         "exact": True,
                                         "via": cl.get("via", "") + " +id-split"})
            # chaining: read_action STRING + sink 없음 → Speaker
            if svc and SVC_BY_ID[svc]["role"] == "read_action" \
                    and SVC_BY_ID[svc]["returns"] == "STRING" and not has_sink:
                spk = {d for d, v in devices.items() if "Speaker" in v["category"]}
                if spk:
                    st, _ = minimal_tags_for(spk, devices)
                    res.groups.append({"role": "notify(chained)",
                                       "clusters": [{"ids": spk, "svc": "Speaker.Speak",
                                                     "sel": st or sorted(spk),
                                                     "quant": quantifier_for("auto", "notify", len(spk)),
                                                     "via": "chain:$" + svc.split(".")[1]}]})
        if out_clusters:
            res.groups.append({"role": role, "hint": dh or eh,
                               "clusters": out_clusters})
            # 일부 클러스터만 능력 없음 → 현행 skill filter처럼 조용히 드롭
        elif dropped:
            owners = sorted({s["svc"].split(".")[0] for s in SVCS
                             if s["role"] in ROLE_OK.get(role, set())
                             and _cat_vocab_hit_any(eh, s)})[:3]
            res.errors.append(
                f"'{dh}' 는 '{eh}' 를 수행할 수 없음"
                + (f" — 가능한 카테고리: {owners}" if owners else ""))

    # ── BINARY 체이닝 후처리: 업스트림 read_action이 BINARY를 반환하면
    # 다운스트림 메일 전송을 첨부 변형으로 승격 ($CaptureImage → attach)
    binary_var = None
    for grp in res.groups:
        for cl in grp["clusters"]:
            svc = cl.get("svc")
            if svc and SVC_BY_ID.get(svc, {}).get("returns") == "BINARY" \
                    and SVC_BY_ID[svc]["role"] == "read_action":
                binary_var = svc.split(".")[1]
            elif svc == "EmailProvider.SendMail" and binary_var:
                cl["svc"] = "EmailProvider.SendMailWithBinaryFile"
                cl["via"] = f"{cl.get('via','')} +chain:${binary_var}"
    return res


def _cat_vocab_hit_any(effect_hint, svc):
    en = norm(effect_hint)
    return any(norm(t) in en or en in norm(t)
               for t in svc.get("ko_triggers", []) if norm(t))


DEMO = [
    "삼성 공기청정기 큰거를 토글해줘",
    "투야 장치들 다 꺼줘",
    "헤이홈 IR 에어컨 꺼줘",
    "불 켜줘",
    "조명 밝기 20 퍼센트로 설정해줘",
    "챗봇에게 대한민국의 수도가 어디인지 물어봐줘",
    "삼성 에어컨으로 습도를 측정해줘",
    "커튼 닫아줘",
    "문이 열리면 카메라로 촬영하고 이메일로 보내줘",
]

if __name__ == "__main__":
    import run as R  # 데모용 디바이스 페이로드 (하네스에서만 읽는다)
    from extract_runner import extract
    for cmd in DEMO:
        print(f"\n══════ {cmd}")
        r = resolve(cmd, R.CONNECTED_DEVICES, extract)
        for grp in r.groups:
            print(f"  [{grp['role']}]")
            for cl in grp["clusters"]:
                sel = " ".join("#" + t for t in cl["sel"])
                print(f"    {cl.get('quant','')}({sel}) → {cl['svc']}"
                      f"  [{len(cl['ids'])}대, via {cl.get('via','?')}]")
        for e in r.errors:
            print(f"  🚫 {e}")
