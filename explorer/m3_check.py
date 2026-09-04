"""M3 검사 — 정답 (IR, JoI) 307쌍에서 IR×JoI 나란히 비교 (ir_step_design.md).

바인딩 접착(§9.4 지름길): 정답 JoI의 AST에서 읽기 키와 액션 셀렉터를
뽑아 IR 쪽 name_map(조건 키)·bind(액션 태그)로 넘긴다. 정답이 확인된
쌍의 자기 검증이므로 허용 — 실제 게이트에서는 확인된 바인딩 표가 출처.

Run:  python -m explorer.m3_check
"""

from __future__ import annotations

import glob
import json
from collections import Counter

from . import joi_parser as jp
from .expr import canonical_key
from .interp import Unsupported, world_key
from .ir_step import IrRunner
from .explore import _read_key
from .predicates import stmt_exprs, walk_stmts
from .pause import PauseRunner, has_blocking
from .product import product_runners
from .runner import DoneLatch, JoiRunner


def _walk_expr(n):
    yield n
    if hasattr(n, "__dict__"):
        for v in vars(n).values():
            if isinstance(v, (list, tuple)):
                for x in v:
                    if hasattr(x, "__dict__"):
                        yield from _walk_expr(x)
            elif hasattr(v, "__dict__"):
                yield from _walk_expr(v)


def build_maps(stmts) -> tuple[dict, dict]:
    """JoI AST → (name_map: 'svc.attr'→월드키, bind: (svc,method)→태그)."""
    name_map, bind = {}, {}
    for s in walk_stmts(stmts):
        if isinstance(s, jp.CallStmt):
            c = s.call
            svc, m = canonical_key(c.service, c.method)
            g = tuple(c.tags)
            lst = bind.setdefault((svc, m), [])
            if g not in lst:       # 문장 순서대로의 서로 다른 셀렉터 그룹
                lst.append(g)
        for e in stmt_exprs(s):
            for n in _walk_expr(e):
                wk = _read_key(n)
                if wk and "." in wk:
                    tags, attr = wk.rsplit(".", 1)
                    for tag in tags.split("+"):
                        name_map.setdefault(f"{tag}.{attr}", wk)
    return name_map, bind


def check_pair(d: dict):
    from .interp import parse as _parse
    from .oneshot import OneShotRunner
    jb = d["joi_block"]
    period = int(jb.get("period") or 0)
    cron = (jb.get("cron") or "").strip()
    ir = d["ir"]
    if cron and cron != "x":
        # cron 쌍: 양쪽이 같은 cron 문자열을 공유(47/47 사전 확인) →
        # 시작 시점이 공통이므로 앵커를 소거하고, 한 번의 발화(창) 안
        # 행동만 나란히 비교한다. 문자열이 다르면 진짜 결함이므로 중단.
        tl = [dict(t) for t in (ir.get("timeline") or [])]
        if not (tl and tl[0].get("op") == "start_at"
                and tl[0].get("anchor") == "cron"
                and (tl[0].get("cron") or "").strip() == cron):
            raise Unsupported(f"cron 앵커 불일치: joi={cron!r}")
        tl[0] = {"op": "start_at", "anchor": "now"}
        ir = {**ir, "timeline": tl}
    stmts = _parse(jb["script"])
    name_map, bind = build_maps(stmts)
    ir_r = IrRunner(ir, name_map=name_map, bind=bind)
    if period > 0:
        # 주기형 JoI의 최상위 break = 블록 영구 종료 → DoneLatch로 고정.
        # blocking 문이 있으면 멈춤 이어가기 실행기(pause.py)로.
        if has_blocking(stmts):
            joi_r = DoneLatch(PauseRunner(stmts, repeat=True))
        else:
            joi_r = DoneLatch(JoiRunner.from_src(stmts))
        return product_runners(ir_r, joi_r, period)
    try:
        joi_r = OneShotRunner(stmts)
    except Unsupported:      # 중첩 blocking → 멈춤 이어가기 실행기
        joi_r = PauseRunner(stmts, repeat=False)
    # one-shot의 tick 격자: 등장하는 최소 시간 상수보다 촘촘하게
    ts = [t for t in (set(ir_r.axes.ts_thresholds)
                      | set(joi_r.axes.ts_thresholds)) if t > 0]
    grid = 60000
    if ts and min(ts) < 60:
        grid = 1000 if min(ts) >= 1 else 100
    return product_runners(ir_r, joi_r, grid)


def main() -> None:
    res, errs = Counter(), Counter()
    diverged = []
    for f in sorted(glob.glob("sensys/simulators/cache/*.json")):
        d = json.load(open(f))
        jb = d.get("joi_block")
        if not jb:
            res["(joi_block 없음)"] += 1
            continue
        name = f.split("/")[-1]
        try:
            pr = check_pair(d)
            res[pr.verdict] += 1
            if pr.verdict == "DIVERGE":
                diverged.append(name)
        except Unsupported as e:
            errs[f"U: {str(e)[:50]}"] += 1
        except Exception as e:
            errs[f"{type(e).__name__}: {str(e)[:50]}"] += 1
    print("주기형(비 blocking) IR×정답 JoI:", dict(res))
    if diverged:
        print("DIVERGE:", diverged)
    for k, v in errs.most_common(12):
        print(f"  [{v}] {k}")


if __name__ == "__main__":
    main()
