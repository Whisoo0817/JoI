"""E3 DIVERGE 분류 — 서비스 / 디바이스 매핑 / 로직·인자 / 집합·수량 정책(보류).

whisoo 결정(2026-08-14): 수량 정책(단수 규약 vs 라이브 any/all·후보 전체)은
시스템 구현이 어느 정도 끝난 뒤 정하기로 하고 그때까지는 "맞은 것"으로
친다. 지금 보는 것은 로직·서비스·디바이스 매핑뿐이다.

분류 순서(앞이 우선):
  서비스     — 호출 메서드/읽기 속성의 (스킬, 이름) 집합이 다름
  디바이스   — 어떤 스킬의 후보 기기 집합이 정답 집합을 포함하지 않음
               (엉뚱한 기기·누락·부유 셀렉터)
  집합/수량  — 서비스·기기 포함 관계는 맞고 집합 크기(상위집합)나
               any/all만 다름 → 정답 바인딩을 후보 쪽 집합·수량사로 바꿔
               다시 게이트: EQUIV면 "정책 차이만"(보류=통과 취급),
               읽기/인자 자리라 못 넓히면 "정책(재검증 불가)"
  로직/인자  — 위가 다 같은데도 갈림(제어 흐름·인자·시간·수량사 잔여)
"""

from __future__ import annotations

import json
import re

from . import expr as ex
from . import joi_parser as jp
from .expr import canonical_key
from .gate import _REF, devs_of, gate_pair, parse_binding, pick_by_rule
from .ground import match
from .interp import parse


# ── IR 쪽 발자국 ────────────────────────────────────────────────────────────

def ir_footprint(ir: dict, binding: dict) -> dict:
    calls, reads = set(), set()

    def walk(steps):
        for s in steps or []:
            if not isinstance(s, dict):
                continue
            if s.get("op") == "call" and "." in (s.get("target") or ""):
                sk, _, m = s["target"].partition(".")
                calls.add(canonical_key(sk, m))
            if s.get("op") == "read" and "." in (s.get("src") or ""):
                sk, _, a = s["src"].partition(".")
                reads.add(canonical_key(sk, a))
            for f in ("cond", "until"):
                for sk, a in _REF.findall(s.get(f) or ""):
                    if sk not in ("Clock", "GlobalVariable"):
                        reads.add(canonical_key(sk, a))
            for v in (s.get("args") or {}).values():
                if isinstance(v, str):
                    for sk, a in _REF.findall(v):
                        if sk not in ("Clock", "GlobalVariable"):
                            reads.add(canonical_key(sk, a))
            for v in s.values():
                if isinstance(v, list):
                    walk(v)
    walk(ir.get("timeline"))
    devs = {}   # skill(lower) → {"ids": set, "quants": set}
    for svc, slots in parse_binding(binding).items():
        e = devs.setdefault(svc.lower(), {"ids": set(), "quants": set()})
        for ids, q in slots:
            e["ids"] |= set(ids)
            e["quants"].add(q or ("single" if len(ids) == 1 else "list"))
    return {"calls": calls, "reads": reads, "devs": devs}


# ── JoI 후보 쪽 발자국 (셀렉터를 인벤토리로 직접 풀어 본다) ──────────────────

def joi_footprint(script: str, devices: dict) -> dict:
    """셀렉터를 인벤토리로 직접 풀어 스킬별 기기 집합·수량 형태를 모은다.
    접지(ground.py)와 같은 규칙: 비교 문맥의 all(...) 은 전체(∀), ==| 는
    존재(∃), 그 밖(스칼라 위치·단수 셀렉터·any 호출)은 규약 1대 선택."""
    stmts = parse(script)
    dl = devs_of(devices)
    calls, reads = set(), set()
    devs: dict = {}
    floating = set()

    def sel_matches(tags):
        if not tags or any(t in ("Clock", "GlobalVariable") for t in tags):
            return None
        m = match(dl, tuple(tags))
        if not m:
            floating.add("#" + "#".join(tags))
        return m

    def note(skill, m, quant):
        e = devs.setdefault(skill, {"ids": set(), "quants": set()})
        if m:
            if quant in ("any", "all", "list"):
                e["ids"] |= {d.id for d in m}
            else:
                e["ids"].add(pick_by_rule(m).id)
        e["quants"].add(quant)

    _CMPS = {"==", "!=", ">", ">=", "<", "<="}

    def walk(n, ctx="scalar"):
        if isinstance(n, (list, tuple)):
            for x in n:
                walk(x, ctx)
            return
        if isinstance(n, ex.BinaryOp):
            base = n.op[:-1] if n.op.endswith("|") else n.op
            if base in _CMPS:
                sub = "cmp_any" if n.op.endswith("|") else "cmp"
            else:
                sub = "scalar"
            walk(n.left, sub)
            walk(n.right, sub)
            return
        if isinstance(n, ex.QuantRef):
            sk, _, a = n.key.partition(".")
            if sk in ("clock", "globalvariable"):     # 주변 환경 — IR 쪽과 같이 제외
                return
            reads.add((sk, a))
            m = sel_matches(n.tags)
            if ctx == "cmp_any":
                q = "any"
            elif ctx == "cmp" and n.quant == "all":
                q = "all"
            else:
                q = "single"
            note(sk, m, q)
            return
        if isinstance(n, jp.CallExpr):
            sk, mth = canonical_key(n.service, n.method)
            m = sel_matches(n.tags)
            if n.args is None:
                if sk in ("clock", "globalvariable"):
                    return
                reads.add((sk, mth))
                note(sk, m, "single")
            else:
                calls.add((sk, mth))
                note(sk, m, "list" if n.quant == "all" else "single")
                walk(n.args, "scalar")
            return
        for f in getattr(n, "__dataclass_fields__", {}):
            v = getattr(n, f)
            if isinstance(v, (list, tuple)) or hasattr(v, "__dataclass_fields__"):
                walk(v, "scalar")
    walk(stmts)
    return {"calls": calls, "reads": reads, "devs": devs,
            "floating": floating}


# ── 단수 규약 자리 (binding_review.md §1) ────────────────────────────────────

def convention_slots(path: str = "explorer/runs/binding_review.md") -> dict:
    """행 → {스킬(lower)}: 정답이 규약(Main/첫 후보) 단수로 남은 읽기 자리.
    이 자리에서만 후보의 상위집합을 '수량 정책 차이'로 본다 — 그 밖의
    상위집합은 지칭(장소·태그) 무시 = 디바이스 매핑 오류."""
    out: dict = {}
    cur, in_sec1 = None, False
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except OSError:
        return out
    for ln in lines:
        if ln.startswith("## "):
            in_sec1 = ln.startswith("## 1.")
            continue
        if not in_sec1:
            continue
        m = re.match(r"- \*\*(C\d+_\d+)\*\*", ln)
        if m:
            cur = m.group(1)
            continue
        m = re.match(r"\s+- ([A-Za-z]+)\[", ln)
        if m and cur:
            out.setdefault(cur, set()).add(m.group(1).lower())
    return out


_CONV = None


# ── 분류 ─────────────────────────────────────────────────────────────────────

def _expanded_binding(binding: dict, jf: dict) -> dict | None:
    """정답 바인딩의 각 스킬 자리를 후보의 기기 집합·수량사로 바꾼다.
    바꿀 게 없으면 None."""
    out, changed = {}, False
    for name, v in binding.items():
        sk = name.split("#")[0].lower()
        gt_ids = set(next(iter(v.values())) if isinstance(v, dict) else v)
        gt_q = next(iter(v)) if isinstance(v, dict) else None
        c = jf["devs"].get(sk)
        if not c or not c["ids"] or not (c["ids"] >= gt_ids):
            out[name] = v
            continue
        cq = None
        if "any" in c["quants"]:
            cq = "any"
        elif "all" in c["quants"]:
            cq = "all"
        ids = sorted(c["ids"])
        if isinstance(v, dict) or cq:
            nv = {cq or gt_q: ids} if (cq or gt_q) else ids
        else:
            nv = ids
        if json.dumps(nv, sort_keys=True) != json.dumps(v, sort_keys=True):
            changed = True
        out[name] = nv
    return out if changed else None


def classify(ir: dict, binding: dict, devices: dict, jb: dict,
             key: str = "") -> tuple[str, str]:
    """(분류, 요지). 게이트 DIVERGE 행에만 부른다."""
    global _CONV
    if _CONV is None:
        _CONV = convention_slots()
    conv = _CONV.get(key, set())
    try:
        jf = joi_footprint(jb.get("script", ""), devices)
    except Exception as e:
        return "서비스", f"후보 해석 불가: {type(e).__name__}: {str(e)[:60]}"
    f = ir_footprint(ir, binding)

    if f["calls"] != jf["calls"] or f["reads"] != jf["reads"]:
        parts = []
        mc, xc = f["calls"] - jf["calls"], jf["calls"] - f["calls"]
        mr, xr = f["reads"] - jf["reads"], jf["reads"] - f["reads"]
        if mc:
            parts.append("호출 누락 " + ",".join(".".join(x) for x in sorted(mc)))
        if xc:
            parts.append("호출 과잉 " + ",".join(".".join(x) for x in sorted(xc)))
        if mr:
            parts.append("읽기 누락 " + ",".join(".".join(x) for x in sorted(mr)))
        if xr:
            parts.append("읽기 과잉 " + ",".join(".".join(x) for x in sorted(xr)))
        return "서비스", "; ".join(parts)

    if jf["floating"]:
        return "디바이스", "부유 셀렉터 " + ",".join(sorted(jf["floating"]))
    bad = []
    superset, quant_diff = [], []
    for sk, e in f["devs"].items():
        c = jf["devs"].get(sk)
        if c is None:
            continue
        if not (c["ids"] >= e["ids"]):
            bad.append(f"{sk}: 정답 {sorted(e['ids'])} vs 후보 {sorted(c['ids'])}")
        elif c["ids"] > e["ids"]:
            if sk in conv:
                superset.append(f"{sk} +{sorted(c['ids'] - e['ids'])}")
            else:   # 지칭된 부분집합을 넘어섬 = 태그/장소 무시
                bad.append(f"{sk}: 지칭 밖 기기 포함 +{sorted(c['ids'] - e['ids'])}")
        cq = {q for q in c["quants"] if q in ("any", "all")}
        gq = {q for q in e["quants"] if q in ("any", "all")}
        if cq != gq and (cq or gq):
            quant_diff.append(f"{sk} 정답 {sorted(gq) or '단수'} vs 후보 {sorted(cq) or '단수'}")
    if bad:
        return "디바이스", "; ".join(bad)

    if superset or quant_diff:
        nb = _expanded_binding(binding, jf)
        detail = "; ".join(superset + quant_diff)
        if nb is None:
            return "로직/인자", "집합 표기만 다름 — " + detail
        g2 = gate_pair(ir, nb, devices, jb)
        if g2.verdict == "EQUIV":
            return "집합/수량(정책)", detail
        if g2.verdict == "REFUSED":
            return "집합/수량(재검증 불가)", detail + " | " + (g2.notes[-1][:50] if g2.notes else "")
        return "로직/인자", "집합 차이 제외 후에도 갈림 — " + detail
    return "로직/인자", ""
