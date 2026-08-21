# -*- coding: utf-8 -*-
"""slm 파이프라인 ↔ 게이트 잇기.

게이트는 binding 표(서비스 → 기기 자리)를 요구한다. 여기서는 정답표 대신
**파이프라인이 고른 기기**(build_selectors 의 resolved)를 쓴다 — IR 쪽과
JoI 쪽을 같은 기기 묶음으로 접지해야, 갈라짐(DIVERGE)의 원인이 기기 고르기가
아니라 lowering 으로 좁혀지기 때문. 기기 고르기가 맞는지는 딴 데서 잰다.
"""
from __future__ import annotations

from .gate import GateResult, gate_pair


def _pick_one(ids: list[str], devices: dict) -> list[str]:
    """단수 자리인데 후보가 여럿일 때 — JoI 쪽 접지 규칙(ground.pick_by_rule)과
    똑같이 고른다: Main 태그가 정확히 1대면 그것, 아니면 인벤토리 순서 첫 후보.
    양쪽이 다른 기기를 고르면 가짜 DIVERGE 가 나므로 규칙을 맞춰야 한다."""
    ids = list(ids)
    if len(ids) <= 1:
        return ids
    mains = [d for d in ids
             if "Main" in ((devices.get(d) or {}).get("tags") or ())]
    if len(mains) == 1:
        return mains
    order = {k: i for i, k in enumerate(devices)}
    return [min(ids, key=lambda d: order.get(d, len(order)))]


def make_binding(selection: dict, devices: dict) -> dict:
    """build_selectors 결과 → 게이트 binding 표.

    서비스당 자리 하나만 적는다(게이트의 '병합 자리' 규약: 자리가 하나면
    그 서비스의 전 등장이 같은 집합을 쓴다). 값 모양은 binding_gt 와 동일:
      - 수량 any/all 읽기·조건 → {"any"/"all": [기기들]}
      - 전부 부르기(action all) → [기기들]
      - 단수 → [기기 하나]
    """
    binding: dict = {}
    seen: dict[str, int] = {}                 # 카테고리별 자리 수
    roles = selection.get("roles") or {}
    for svc, info in (selection.get("resolved") or {}).items():
        cat = svc.split(".", 1)[0]            # 게이트 binding 키는 카테고리 이름
        q = info.get("q") or "one"
        ids = sorted(info.get("devices") or [])
        role = roles.get(svc, "action")
        if q == "any":
            val = {"any": ids} if len(ids) > 1 else _pick_one(ids, devices)
        elif q == "all":
            val = {"all": ids} if role in ("condition", "read") else ids
        else:
            val = _pick_one(ids, devices)
        n = seen.get(cat, 0) + 1
        seen[cat] = n                          # 같은 카테고리 두 번째부터 #2, #3 …
        binding[cat if n == 1 else f"{cat}#{n}"] = val
    return binding


def gate_row(ir: dict, jb: dict, devices: dict,
             selection: dict | None = None) -> GateResult:
    """정답 IR × 후보 코드 한 행 판정.

    jb: {"script": JoI 코드, "period": ms(0=원샷), "cron": ""|"x"|크론}.
    selection 을 안 주면 여기서 build_selectors 로 만든다(파이프라인과 동일)."""
    if selection is None:
        from joi.devices import build_selectors
        selection = build_selectors(ir, devices, None)
    binding = make_binding(selection, devices)
    try:
        return gate_pair(selection.get("ir") or ir, binding, devices, jb)
    except ValueError as e:
        # JoI 파서가 코드를 못 읽음(형식 깨짐) — 판정 불가이므로 REFUSED.
        return GateResult("REFUSED", notes=[f"코드를 읽지 못함: {e}"])
