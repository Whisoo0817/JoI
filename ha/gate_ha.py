"""HA 게이트 — 확인된 (IR + 기기 바인딩 표) × HA 문서 나란히 비교 (W4).

explorer/gate.py의 HA판. IR 쪽 접지는 동일(바인딩 표, reground_ir),
HA 쪽은 ha_step.HaRunner(제한 조각 번역 → 같은 한-걸음 실행기).
cron 앵커는 표기 차이를 무시하는 정규화 비교(cron_norm) 후 공통 소거.

판정: EQUIV / DIVERGE(반례 재생 확인) / REFUSED(조각 밖 fail-closed).

Run:  python -m ha.gate_ha          # 388행 × ha/gt/*.yaml 판정 분포
"""

from __future__ import annotations

import json

from explorer.gate import GateResult, load_rows, reground_ir
from explorer.interp import Unsupported
from explorer.ir_step import IrRunner
from explorer.product import product_runners, replay_divergence

from .ha_step import HaRunner, cron_norm


def gate_pair_ha(ir: dict, binding: dict, devices: dict,
                 doc: dict) -> GateResult:
    notes: list[str] = []
    try:
        ha_r = HaRunner(doc, devices)

        tl = [dict(t) for t in (ir.get("timeline") or [])]
        ir_cron = (tl[0].get("cron") or "").strip() \
            if tl and tl[0].get("anchor") == "cron" else ""
        if ir_cron or ha_r.cron:
            if not (ir_cron and ha_r.cron
                    and cron_norm(ir_cron) == cron_norm(ha_r.cron)):
                raise Unsupported(
                    f"cron 앵커 불일치: ir={ir_cron!r} ha={ha_r.cron!r}")
            tl[0] = {"op": "start_at", "anchor": "now"}
            ir = {**ir, "timeline": tl}

        new_ir, name_map, bind, rw_notes = reground_ir(ir, binding)
        notes += rw_notes
        ir_r = IrRunner(new_ir, name_map=name_map, bind=bind)

        if ha_r.period_hint > 0:
            grid = max(1000, int(round(ha_r.period_hint * 1000)))
            pr = product_runners(ir_r, ha_r, grid)
        else:
            # 그리드 바닥 1초 — HA 조각의 시간 해상도(1초) 기준. IR의
            # 밀리초 주기는 "매 tick"으로 양자화되어 양쪽이 일치한다.
            ts = [t for t in (set(ir_r.axes.ts_thresholds)
                              | set(ha_r.axes.ts_thresholds)) if t > 0]
            grid = 1000 if ts and min(ts) < 60 else 60000
            pr = product_runners(ir_r, ha_r, grid)
    except Unsupported as e:
        return GateResult("REFUSED", notes=notes + [str(e)])

    replays = [replay_divergence(ir_r, ha_r, dv) for dv in pr.divergences]
    return GateResult(pr.verdict, pr, replays, notes)


def main() -> None:
    import glob
    from collections import Counter

    import yaml

    rows = load_rows()
    res, refused = Counter(), Counter()
    diverged, unconfirmed = [], []
    for f in sorted(glob.glob("ha/gt/*.yaml")):
        key = f.rsplit("/", 1)[-1][:-5]
        r = rows.get(key)
        if r is None:
            continue
        doc = yaml.safe_load(open(f, encoding="utf-8"))
        g = gate_pair_ha(json.loads(r["ir_gt"]),
                         json.loads(r.get("binding_gt") or "{}"),
                         json.loads(r["connected_devices"]), doc)
        res[g.verdict] += 1
        if g.verdict == "DIVERGE":
            diverged.append(key)
            if not g.confirmed:
                unconfirmed.append(key)
        if g.verdict == "REFUSED":
            refused[f"{key}: {g.notes[-1][:70]}"] += 1
    print("HA 게이트 × 참조 lowering:", dict(res))
    if diverged:
        print(f"DIVERGE {len(diverged)}: {diverged[:20]}")
        print(f"  그중 재생 미확인: {unconfirmed[:10] or '없음'}")
    for k, v in refused.most_common(15):
        print(f"  [{v}] {k}")


if __name__ == "__main__":
    main()
