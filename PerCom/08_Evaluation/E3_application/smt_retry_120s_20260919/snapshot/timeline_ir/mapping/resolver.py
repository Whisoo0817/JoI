"""Device mapping resolver — judgment by LLM, representation and validation by Python.

역할 분담 (v2와의 차이가 여기에 있다):
  A. 제약 추출  (LLM #1, 환경 무지)  : 발화를 그룹으로 쪼개고 스팬을 분류
  B. 후보 생성  (Python, recall 지향) : 어휘로 "그럴듯한 후보"를 넓게 모음 (교집합 아님)
  C. 지시 해소  (LLM #2, 환경 접지)   : 후보 중 사용자가 가리킨 집합을 선택
                                       — 대조적 의도("KT 말고 삼성")는 여기서만 풀린다
  D. 검증·표현  (Python)              : 선택 검증 → 능력 검사 → 서비스 → selector → 수량

LLM은 절대 태그 문자열·서비스명·수량을 생성하지 않는다. C의 출력은 후보 dN의
부분집합뿐이고 guided decoding으로 enum이 강제되므로, 존재하지 않는 디바이스를
지목하는 실패는 구조적으로 불가능하다. 나머지 실패(능력 없음/채널 없음)는 D가
귀속된 에러로 바꾼다.

"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(HERE))

from . import engine as JE
from .ontology import minimal_tags_for, quantifier_for
from . import extractor as ER
from .extractor import extract, match_hint

SELECT_PROMPT = open(os.path.join(PROJECT_ROOT, "files", "mapping",
                                  "select_devices.md"), encoding="utf-8").read()
CANON_NOTIFY = JE.CANON_NOTIFY
ROLE_OK = JE.ROLE_OK

# 정책: "지금 몇 시야/시간 알려줘"류 현재 시각 안내는 단일 Datetime이 아니라
# Hour+Minute 두 값을 읽는다 (베이스라인/naming 단계 규약)
CLOCK_TIME_EXPAND = {"Clock.Datetime": ["Clock.Hour", "Clock.Minute"],
                     "Clock.Time": ["Clock.Hour", "Clock.Minute"]}


# ── B. 후보 생성 (recall 지향: 어느 토큰이든 걸리면 후보) ────────────────
def candidates_for(group, devices, connected_cats):
    role = group["role"]
    dh, eh = group.get("device_hint"), group.get("effect_hint")

    if role == "notify":
        cats = [JE.CHANNEL_CAT[k] for k in JE.CHANNEL_CAT if dh and k in dh] \
            or ["Speaker", "ToastPublisher"]
        ids = {d for d, v in devices.items() if set(v["category"]) & set(cats)}
        return ids, cats

    ids = set()
    if dh:
        for t in JE._tokens(dh):
            got, _ = JE._match_token_devices(t, devices, connected_cats)
            ids |= got            # ← 합집합. 좁히는 일은 LLM이 한다
    if not ids and eh:
        for cat in match_hint(eh, connected_cats, top_n=3):
            ids |= {d for d, v in devices.items() if cat in v["category"]}
    return ids, None


# ── C. 지시 해소 (LLM #2, 후보 안에서만) ────────────────────────────────
def select_devices(command, group, cand_ids, devices):
    """후보가 0~1개면 LLM을 부르지 않는다 (선택의 여지가 없음)."""
    if len(cand_ids) <= 1:
        return set(cand_ids), "후보 단일 — LLM 생략"
    # 무표지(지칭 구절 없음) 그룹은 좁힐 근거 자체가 없다 — 확정 정책
    # (§9.11/9.12: 무표지 액션·센서류 조건은 후보 전체)대로 전체 선택.
    # LLM에게 물으면 임의로 제외하는 결함이 있었다 (2026-08-14, C07_013).
    if not group.get("device_hint"):
        return set(cand_ids), "무표지 — 후보 전체(정책)"

    alias = {f"d{i+1}": did for i, did in enumerate(sorted(cand_ids))}
    lines = []
    for a, did in alias.items():
        d = devices[did]
        tags = [t for t in d["tags"] if not t.startswith("tc0_")]
        lines.append(f"{a} | {d.get('nickname','')} | {','.join(d['category'])} "
                     f"| {','.join(tags)}")
    user = (f"[Command]\n{command}\n\n"
            f"[Group]\nrole={group['role']} | 지칭={group.get('device_hint')!r} "
            f"| 효과={group.get('effect_hint')!r}\n\n"
            f"[Candidates]\n" + "\n".join(lines))

    schema = {
        "type": "object",
        "properties": {
            "selected": {"type": "array",
                         "items": {"enum": list(alias)}},   # ← 후보로 제한
        },
        "required": ["selected"],
        "additionalProperties": False,
    }
    ER.ensure_client()
    resp = ER.client.chat.completions.create(
        model=ER.MODEL, temperature=0, max_tokens=768,
        messages=[{"role": "system", "content": SELECT_PROMPT},
                  {"role": "user", "content": user}],
        extra_body={"guided_json": schema,
                    "chat_template_kwargs": {"enable_thinking": False}},
    )
    raw = resp.choices[0].message.content or ""
    try:
        out = json.loads(raw)
    except json.JSONDecodeError:
        # 잘린 출력에서 selected 배열만 건져낸다 (reason은 로그용이라 버려도 됨)
        import re as _re
        ids = _re.findall(r'"(d\d+)"', raw)
        out = {"selected": ids, "reason": "(응답 잘림 — id만 복구)"}
    picked = {alias[a] for a in out.get("selected", []) if a in alias}  # D의 재검증
    dropped = sorted(set(alias) - set(out.get("selected", [])))
    reason = (f"제외 {[devices[alias[a]].get('nickname','') for a in dropped]}"
              if dropped else "후보 전체 선택")
    return picked, reason


# ── D. 검증 + 표현 ──────────────────────────────────────────────────────
def resolve(command, devices, log=None):
    log = log if log is not None else []
    connected_cats = {c for d in devices.values() for c in d["category"]}
    parsed = extract(command)
    groups_out, errors = [], []
    has_sink = any(g["role"] == "notify" for g in parsed["groups"])

    for g in parsed["groups"]:
        role, dh, eh = g["role"], g.get("device_hint"), g.get("effect_hint")

        # ── notify 전담 경로: 채널별로 독립 클러스터를 만든다.
        # (하나로 합치면 대표 서비스 하나만 남아 Toast가 유실됨 — 2026-07-20 결함)
        if role == "notify":
            # 정책 (2026-07-20 사용자 확정): 채널을 문자 그대로 지칭했을 때만
            # 제한하고, 무지칭 notify는 무조건 Speaker+Toast 둘 다.
            # hard=false인 device_hint는 추출기의 유추일 수 있으므로 무시.
            text = f"{dh if g.get('device_hard') else ''} {eh or ''}"
            chans = list(dict.fromkeys(
                cat for k, cat in JE.CHANNEL_CAT.items() if k in text)) \
                or ["Speaker", "ToastPublisher"]     # 무지칭 → 둘 다 (무조건)
            n_clusters, absent = [], []
            for cat in chans:
                ids = {d for d, v in devices.items() if cat in v["category"]}
                if not ids:
                    absent.append(cat)
                    continue
                st, _ = minimal_tags_for(ids, devices)
                n_clusters.append({"ids": ids, "svc": CANON_NOTIFY[cat],
                                   "sel": st or sorted(ids),
                                   "quant": quantifier_for("auto", "notify",
                                                           len(ids))})
            if not n_clusters:
                errors.append(f"'{dh or '알림'}': 알릴 수단이 없음 — "
                              f"필요 채널 {chans} 중 연결된 디바이스 0대")
                continue
            if absent:
                log.append(f"[notify] 채널 {absent} 미연결 — 나머지로 전달")
            log.append(f"[notify] {dh or eh!r}: 채널 {chans}")
            groups_out.append({"role": "notify", "hint": dh or eh,
                               "reason": "채널 정책", "clusters": n_clusters})
            continue

        cands, _channels = candidates_for(g, devices, connected_cats)
        if not cands:
            errors.append(f"'{dh or eh}': 해당하는 연결 디바이스 없음")
            continue

        picked, reason = select_devices(command, g, cands, devices)
        log.append(f"[{role}] {dh or eh!r}: 후보 {len(cands)} → 선택 "
                   f"{len(picked)}  ({reason})")

        # 실현 가능성 ②: LLM이 "해당 없음"으로 판단
        if not picked:
            errors.append(f"'{dh or eh}': 지칭에 맞는 디바이스 없음 — {reason}")
            continue

        # OR 클러스터 분해 (Light vs LightSwitch: 서비스가 갈리므로 분리)
        light = {d for d in picked if "Light" in devices[d]["category"]}
        lsw = {d for d in picked - light if "LightSwitch" in devices[d]["tags"]}
        rest = picked - light - lsw
        # 밝기/퍼센트 명령은 Light 클러스터만 남긴다 — 단, 조명이 실제로
        # 골라졌을 때만. 조명 없는 퍼센트 명령(블라인드 50%, 볼륨 30% 등)까지
        # 전부 드롭하던 결함 수정 (2026-08-14, 388행 첫 실측에서 발견).
        level = bool(eh) and bool(light) \
            and any(w in eh for w in ("밝기", "퍼센트", "%"))

        clusters = []
        for part in (light, lsw, rest):
            if not part or (level and part is not light):
                continue
            svc0 = JE._select_service(part, devices, eh, role)
            if not svc0:
                continue          # 능력 없는 클러스터는 드롭 (부분 실현 금지)
            # 정책: 현재 시각 안내는 Hour+Minute 2회 읽기로 확장
            # (베이스라인 패리티 — naming 단계가 HH:MM으로 조립)
            svc_list = CLOCK_TIME_EXPAND.get(svc0, [svc0]) \
                if role == "read" else [svc0]
            for svc in svc_list:
                # 디바이스별 능력 검사: 선택된 서비스의 카테고리를 실제로 가진
                # 디바이스만 남긴다 ("삼성 기기들 전부 꺼줘"에서 Switch 없는
                # 로봇청소기에 Switch.Off가 붙는 것을 방지)
                svc_cat = svc.split(".")[0]
                p = {d for d in part if svc_cat in devices[d]["category"]}
                if not p:
                    continue
                tags, exact = minimal_tags_for(p, devices)
                quant = quantifier_for(g.get("quantifier") or "auto", role, len(p))
                # ⚠️ 임시 하드코딩 (2026-07-20 사용자 지시, 범용 정책化 금지):
                # PresenceSensor 부재 조건("사람이 없으면")은 모든 센서가 부재를
                # 지속해야 하므로 무표지라도 all. 다른 센서로 일반화하지 말 것.
                if role == "condition" and not g.get("quantifier") \
                        and any("PresenceSensor" in devices[d]["category"] for d in p) \
                        and eh and any(w in eh for w in ("없으면", "없음", "부재")):
                    quant = "all"
                if tags and exact:
                    clusters.append({"ids": p, "svc": svc, "sel": tags,
                                     "quant": quant})
                else:
                    # 태그로 이 집합만 못 고름 → 디바이스별 id로 분해
                    for did in sorted(p):
                        clusters.append({"ids": {did}, "svc": svc, "sel": [did],
                                         "quant": ""})

        # 실현 가능성 ③: 고른 디바이스가 요구된 일을 못 함
        if not clusters:
            owners = sorted({s["svc"].split(".")[0] for s in JE.SVCS
                             if s["role"] in ROLE_OK.get(role, set())
                             and JE._cat_vocab_hit_any(eh or "", s)})[:3]
            errors.append(f"'{dh or eh}' 는 '{eh}' 를 수행할 수 없음"
                          + (f" — 가능한 카테고리: {owners}" if owners else ""))
            continue

        groups_out.append({"role": role, "hint": dh or eh, "reason": reason,
                           "clusters": clusters})

        # 체이닝: STRING 반환 read_action + 명령에 sink 없음 → Speaker
        for cl in list(clusters):
            info = JE.SVC_BY_ID.get(cl["svc"], {})
            if info.get("role") == "read_action" and info.get("returns") == "STRING" \
                    and not has_sink:
                spk = {d for d, v in devices.items() if "Speaker" in v["category"]}
                if not spk:
                    errors.append(f"{cl['svc']} 의 답을 전달할 스피커가 없음")
                    continue
                st, _ = minimal_tags_for(spk, devices)
                groups_out.append({
                    "role": "notify(chained)", "hint": f"${cl['svc'].split('.')[1]}",
                    "reason": "STRING 반환값 전달", "clusters": [
                        {"ids": spk, "svc": "Speaker.Speak",
                         "sel": st or sorted(spk),
                         "quant": quantifier_for("auto", "notify", len(spk))}]})

    # BINARY 상류 → 하류 메일을 첨부 변형으로 승격
    bvar = None
    for grp in groups_out:
        for cl in grp["clusters"]:
            info = JE.SVC_BY_ID.get(cl["svc"], {})
            if info.get("role") == "read_action" and info.get("returns") == "BINARY":
                bvar = cl["svc"].split(".")[1]
            elif cl["svc"] == "EmailProvider.SendMail" and bvar:
                cl["svc"] = "EmailProvider.SendMailWithBinaryFile"
    return {"groups": groups_out, "errors": errors, "log": log,
            "extracted": parsed["groups"]}
