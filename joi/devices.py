"""IR 서비스 → 연결 기기 조인 → 셀렉터 (LLM 없음, 순수 파이썬).

joi_slm 이 만든 Timeline IR 은 서비스 수준(`Category.Method`)이고 기기를 고르지 않는다.
lowering 프롬프트는 서비스마다 `[Precision Selectors]` 한 줄이 필요하므로, 여기서
IR 에 나오는 서비스마다 연결 기기 목록을 카테고리로 조인해 셀렉터를 만든다.

  셀렉터  : `(#Category)` — 그 카테고리를 가진 연결 기기 전부
  수량사  : 기기 1대 → 없음 / 조건·읽기 자리 → `any` / 실행 자리 → `all`
            (수량 정책은 나중에 정한다 — 지금은 이 기본값 하나)
  Clock·GlobalVariable 은 기기가 아니므로 셀렉터를 만들지 않는다.

기기 없는 서비스가 하나라도 있으면 `MissingDevices` 를 던진다(부분 실현 금지).

TODO(기기 선택): 같은 카테고리 안에서 어느 기기인지(방·별명·"삼성" 등)는 아직 고르지 않는다.
"""

from __future__ import annotations

import re
from typing import Any

# 서비스 이름 `Category.Method` — 조건식(cond/until) 안에서도 이 모양으로 나온다.
_SVC_RE = re.compile(r"\b([A-Z][A-Za-z0-9]*)\.([A-Za-z][A-Za-z0-9]*)\b")
# 기기가 아닌 카테고리 (셀렉터 불필요)
NON_DEVICE = {"Clock", "GlobalVariable"}


class MissingDevices(ValueError):
    """IR 이 쓰는 서비스의 카테고리를 가진 연결 기기가 없다."""
    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__("연결된 기기 없음: " + ", ".join(missing))


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
            if not isinstance(s, dict):
                continue
            op = s.get("op")
            if op == "call":
                t = s.get("target", "")
                if isinstance(t, str) and "." in t:
                    put(t, "action")
                for v in (s.get("args") or {}).values():
                    scan_expr(v, "read")
            elif op == "read":
                if isinstance(s.get("src"), str):
                    put(s["src"], "read")
            elif op == "if":
                scan_expr(s.get("cond"), "condition")
                walk(s.get("then") or [])
                walk(s.get("else") or [])
            elif op == "wait":
                scan_expr(s.get("cond"), "condition")
            elif op == "cycle":
                scan_expr(s.get("until"), "condition")
                walk(s.get("body") or [])

    walk((ir or {}).get("timeline") or [])
    return roles


def _categories_of(dev: dict) -> set[str]:
    cats = dev.get("category", [])
    if isinstance(cats, str):
        cats = [cats]
    return {c for c in cats if isinstance(c, str)}


def build_selectors(ir: dict, connected_devices: dict) -> dict:
    """→ {"selectors": {svc: ["<quant>(#Cat)"]}, "resolved": {svc: {"q", "devices"}},
          "selected_services": [svc, ...], "roles": {svc: role}}"""
    roles = services_in_ir(ir)
    selectors, resolved, missing = {}, {}, []
    for svc, role in roles.items():
        cat = svc.split(".", 1)[0]
        if cat in NON_DEVICE:
            continue
        ids = [k for k, d in (connected_devices or {}).items()
               if isinstance(d, dict) and cat in _categories_of(d)]
        if not ids:
            missing.append(svc)
            continue
        if len(ids) <= 1:
            q = ""
        elif role in ("condition", "read"):
            q = "any"
        else:
            q = "all"
        selectors[svc] = [f"{q}(#{cat})"]
        resolved[svc] = {"q": q or "one", "devices": ids}
    if missing:
        raise MissingDevices(missing)
    return {"selectors": selectors, "resolved": resolved,
            "selected_services": list(roles.keys()), "roles": roles}


def render_selectors(selectors: dict) -> str:
    """lowering 프롬프트의 `[Precision Selectors]` 블록 — 서비스마다 한 줄."""
    lines = [f"{svc}: " + " / ".join(sel) for svc, sel in (selectors or {}).items() if sel]
    return "\n".join(lines) if lines else "(none)"
