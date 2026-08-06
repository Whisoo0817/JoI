"""Phase 4 섀도 비교 — 엄격판 (2026-07-20 재작성).

이전 판의 계측 결함 두 개를 고쳤다:
  ① 서비스를 카테고리로 뭉갰음 → Switch.On과 Switch.Off가 같이 채점됨.
     이제 전체 서비스 id로 비교한다.
  ② selector 문자열만 비교하고 tc0_ id는 '<id>'로 뭉갰음 → 다른 기기를
     골라도 일치로 집계됨. 이제 selector를 CONNECTED_DEVICES에 대해
     **실제 디바이스 집합으로 해석**해 집합끼리 비교한다. 표현이 달라도
     같은 기기면 동일, 같은 표현이라도 다른 기기면 불일치.

비교 단위: (role, quant, service_id) 별로 디바이스 집합을 합쳐 비교.
  - role: 베이스라인은 `wait until(...)` 안의 호출을 condition으로 분류.
  - condition의 quant는 'cond'로 정규화 (any/all 의미는 ==| 연산자가 담당
    하는 렌더 관례라 selector 접두사로는 비교 불가).
  - 집합 크기 1이면 quant 접두사를 ''로 정규화 (all(#X) ≡ (#X) when |X|=1).
  - 같은 (role, quant, svc)의 클러스터 분할은 집합 합집합으로 동치 처리
    (base의 all(#Tuya #Switch) ≡ v3의 SharedLight+LightSwitch 분할).

인자/메시지/cron은 여전히 비교하지 않는다 (v3의 소관 밖).

사용: /home/ikess/joi-llm/venv/bin/python shadow_compare.py --v3
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
sys.path.insert(0, HERE)

import run as R  # noqa: E402

DEV = R.CONNECTED_DEVICES
USE_V3 = "--v3" in sys.argv

# 끝의 '(' 는 선택 — 조건절 값 읽기(contactSensor_contact == false)는
# 함수 호출이 아니라 괄호가 없다 (필수로 하면 조건절 전부 누락됨)
CALL = re.compile(r'(all|any)?\(\s*(#[^)]*?)\s*\)\s*\.\s*(\w+)')


def _labels(did):
    d = DEV[did]
    return set(d.get("category", [])) | set(d.get("tags", [])) | {did}


def resolve_selector(sel_text):
    """'#Light #Section3' / '#tc0_...' → 실제 디바이스 id 집합 (교집합 의미)."""
    toks = [t.lstrip("#") for t in sel_text.split() if t.strip()]
    if not toks:
        return frozenset()
    return frozenset(d for d in DEV if all(t in _labels(d) for t in toks))


def _method_svc(meth):
    """'emailProvider_sendMailWithBinaryFile' → 'EmailProvider.SendMailWithBinaryFile'"""
    head, _, tail = meth.partition("_")
    up = lambda s: s[0].upper() + s[1:] if s else s  # noqa: E731
    return f"{up(head)}.{up(tail)}"


_SVC_ROLE = {s["svc"]: s["role"] for s in json.load(
    open(os.path.join(HERE, "effects.json")))["services"]}


def _merge(triples):
    """(role, quant, svc) 별 디바이스 집합 합집합 → 비교 가능한 frozenset.

    role은 렌더링(wait until/if 루프)에서 추측하지 않고 **서비스의 read/action
    속성**에서 유도한다 — 지속 조건이 if-폴링으로 렌더되는 등 표현이 달라도
    양쪽에 동일한 규칙이 적용되므로 비대칭이 생기지 않는다.
    read의 any/all 의미는 비교 연산자(==|) 관례라 접두사로는 비교 불가 → 'r'.
    """
    acc = {}
    for _ignored_role, quant, ids, svc in triples:
        role = "read" if _SVC_ROLE.get(svc) == "read" else "action"
        if role == "read":
            quant = "r"
        elif len(ids) <= 1:
            quant = ""            # all(#X) ≡ (#X) when |X|=1
        key = (role, quant, svc)
        acc[key] = acc.get(key, frozenset()) | ids
    return frozenset((k[0], k[1], ids, k[2]) for k, ids in acc.items())


def baseline_triples(rec):
    code = rec["code"] if isinstance(rec["code"], str) \
        else json.dumps(rec["code"], ensure_ascii=False)
    m = re.search(r'"script"\s*:\s*"(.*)"\s*}', code, re.DOTALL)
    script = (m.group(1) if m else code).replace("\\n", "\n").replace('\\"', '"')
    out = []
    depth = 0   # wait until(...) 괄호 깊이 — 지속 조건은 여러 줄로 렌더됨
    for line in script.split("\n"):
        if depth <= 0 and "wait until" in line:
            depth = 0
            tail = line.split("wait until", 1)[1]
            depth += tail.count("(") - tail.count(")")
            in_cond = True
        elif depth > 0:
            depth += line.count("(") - line.count(")")
            in_cond = True
        else:
            in_cond = "wait until" in line
        role = "condition" if in_cond else "action"
        for quant, sel, meth in CALL.findall(line):
            out.append((role, quant or "", resolve_selector(sel),
                        _method_svc(meth)))
    return _merge(out)


def engine_triples(command):
    if USE_V3:
        from resolver_v3 import resolve_v3
        r = resolve_v3(command, DEV)
        groups, errors = r["groups"], r["errors"]
    else:
        from extract_runner import extract
        from join_engine import resolve
        r = resolve(command, DEV, extract)
        groups, errors = r.groups, r.errors
    out = []
    for grp in groups:
        role = "condition" if grp["role"] == "condition" else "action"
        for cl in grp["clusters"]:
            if not cl.get("svc"):
                continue
            out.append((role, cl.get("quant", ""), frozenset(cl["ids"]),
                        cl["svc"]))
    return _merge(out), errors


def show(triples):
    def fmt(t):
        role, quant, ids, svc = t
        names = sorted(DEV[i]["nickname"] for i in ids)
        disp = f"{len(ids)}대" if len(ids) > 3 else "/".join(names)
        return f"{role[:4]}·{quant or '-'}[{disp}]→{svc}"
    return "{" + ";  ".join(fmt(t) for t in
                            sorted(triples, key=lambda x: x[3])) + "}"


if __name__ == "__main__":
    recs = [json.loads(l) for l in
            open(os.path.join(HERE, "baseline_2026-07-20.jsonl"))]
    same = diff = refuse_ok = refuse_diff = 0
    for rec in recs:
        cmd = rec["command"]
        try:
            new, errs = engine_triples(cmd)
        except Exception as e:  # noqa: BLE001
            print(f"💥 {cmd}: {e}")
            diff += 1
            continue
        if not rec.get("ok"):
            ok = bool(errs) and not new
            refuse_ok += ok
            refuse_diff += (not ok)
            if not ok:
                print(f"\n[REFUSE-DIFF] {cmd}\n   new : {show(new)}")
                for e in errs:
                    print(f"   🚫 {e}")
            continue
        base = baseline_triples(rec)
        if base == new:
            same += 1
        else:
            diff += 1
            print(f"\n[DIFF] {cmd}")
            print(f"   base: {show(base)}")
            print(f"   new : {show(new)}")
            only_b, only_n = base - new, new - base
            if only_b:
                print(f"   ⊖ 베이스만: {show(only_b)}")
            if only_n:
                print(f"   ⊕ 신규만  : {show(only_n)}")
            for e in errs:
                print(f"   🚫 {e}")
    n = len(recs)
    print(f"\n═══ [엄격판] 일치 {same}/{n - refuse_ok - refuse_diff} "
          f"(거부일치 {refuse_ok}, 거부불일치 {refuse_diff}) | 불일치 {diff}")
