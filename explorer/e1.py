"""E1 harness: the paper's exhaustive result table, machine-generated.

One run produces every per-scenario verdict with its evidence — no
percentages, no sampling language. Table 1: per scenario — fragment
membership of its predicates, exploration size, closure, self-equivalence,
and every obligation finding (or "clean"). Table 2: injected faults — each
of the six fault classes exercised at least once, which layer detects it,
and the counterexample gist. Out-of-scope items appear BY NAME, never as a
percentage remainder.

Output: stdout + runs/e1.md (markdown, commit-ready).

Run:  python -m explorer.e1
"""

from __future__ import annotations

import os
import time as _time

from .interp import Unsupported, parse
from .predicates import analyze
from .obligations import check, _fmt
from .product import product_explore
from .ground import Dev, from_adapt, ground
from .cron import prepare


def scenario_rows(data, devs) -> list[dict]:
    rows = []
    for s in data:
        name = s["name"]
        frag = analyze(name, s["code"])
        dist: dict[str, int] = {}
        for p in frag["preds"]:
            dist[p.klass] = dist.get(p.klass, 0) + 1
        n_ground = dist.get("GROUND", 0)
        n_review = dist.get("REVIEW", 0)
        row = {"name": name, "preds": frag["total"],
               "in_frag": frag["in_frag"], "ground": n_ground,
               "review": n_review, "notes": []}
        try:
            gstmts, rep = ground(parse(s["code"]), devs)
            cron = s.get("cron", "")
            if cron not in ("", "x", None):
                gstmts, period = prepare(gstmts, cron)
                row["notes"].append(f"cron {cron}")
            else:
                period = int(s["period"])
            if rep.floating:
                row["notes"].append("부유 " + ",".join(rep.floating))
            t0 = _time.time()
            r = check(gstmts, period)
            row["t_explore"] = _time.time() - t0
            g = r.graph
            row.update(states=g.n_states, edges=g.n_edges,
                       closed=g.closed)
            finds = [f"VACUOUS {_fmt(k)}" for k in sorted(r.dead)]
            finds += [f"SEED-DEP {_fmt(k)}" for k in sorted(r.seed_dependent)]
            finds += [f"OVERLAP {_fmt(k)}" for k, _, _ in r.overlaps]
            finds += [f"COUNTER-CARRY {nm}" for nm, _ in r.counter_carry]
            row["findings"] = finds
            t0 = _time.time()
            pr = product_explore(gstmts, gstmts, period)
            row["self_equiv"] = pr.verdict
            row["t_product"] = _time.time() - t0
        except Unsupported as e:
            row["error"] = str(e)
        rows.append(row)
    return rows


def fault_rows(data, devs) -> list[dict]:
    by = {s["name"]: s for s in data}

    def mut(name: str, old: str, new: str) -> tuple[str, str, int]:
        src = by[name]["code"]
        out = src.replace(old, new)
        assert out != src, f"no-op mutation: {old!r}"
        return src, out, int(by[name]["period"])

    cases = [
        ("경계 이동", "침입 grace `>` → `>=`",
         *mut("보안모드 침입 감지", "now - grace_start > grace_sec",
              "now - grace_start >= grace_sec")),
        ("시간 상수", "화재 cooldown 30분→3분",
         *mut("화재 감지 알림", "30 * 60", "3 * 60")),
        ("엣지→레벨", "보안모드 was_pushed 조건 삭제",
         *mut("보안모드 자동제어", "if (pushed == true and was_pushed == false)",
              "if (pushed == true)")),
        ("재알림 폭주", "침입 cooldown 600→60",
         *mut("보안모드 침입 감지", "alert_cooldown := 600",
              "alert_cooldown := 60")),
        ("배선(재배포)", "침입 카메라 Office→Lobby",
         *mut("보안모드 침입 감지", "(#Camera #Office)", "(#Camera #Lobby)")),
    ]
    rows = []
    for klass, desc, base_src, mut_src, period in cases:
        env = devs
        if "Lobby" in mut_src:
            env = devs + [Dev("cam2", "Camera", ("Lobby",))]
        ga, _ = ground(parse(base_src), env)
        gb, _ = ground(parse(mut_src), env)
        r = product_explore(ga, gb, period)
        gist = ""
        if r.divergences:
            dv = r.divergences[0]
            gist = f"깊이 {dv.depth}, dwell {dv.dwell_ms // 1000}s"
        rows.append({"class": klass, "desc": desc, "verdict": r.verdict,
                     "layer": "곱(동치)", "gist": gist,
                     "states": r.n_states, "sec": r.seconds})

    # obligation-layer detections (single-code, no base needed)
    intr = by["보안모드 침입 감지"]
    m = intr["code"].replace("alert_cooldown := 600", "alert_cooldown := 5")
    gm, _ = ground(parse(m), devs)
    ro = check(gm, int(intr["period"]))
    ov = ro.overlaps[0] if ro.overlaps else None
    rows.append({"class": "점유 겹침", "desc": "침입 cooldown 600→5",
                 "verdict": "OVERLAP" if ov else "미검출",
                 "layer": "의무(겹침)",
                 "gist": f"{ov[2]}s 점유 중 {ov[1]}s 재발화" if ov else "",
                 "states": ro.graph.n_states, "sec": 0.0})

    # quantifier ∃→1대: binding-dependent (k=1 EQUIV / k=2 DIVERGE)
    fire = by["화재 감지 알림"]
    fmut = fire["code"].replace(
        "(#PresenceSensor #Office).presenceSensor_presence ==| true",
        "(#PresenceSensor #Office #Desk1).presenceSensor_presence == true")
    assert fmut != fire["code"]
    verdicts = []
    for k in (1, 2):
        env = [Dev("sd1", "SmokeDetector", ("Office",)),
               Dev("sp1", "Speaker", ("Office",)),
               Dev("em1", "EmailProvider"), Dev("tp1", "ToastPublisher"),
               Dev("ps1", "PresenceSensor", ("Office",), ("Desk1",))]
        env += [Dev(f"ps{i + 2}", "PresenceSensor", ("Office",))
                for i in range(k - 1)]
        ga, _ = ground(parse(fire["code"]), env)
        gb, _ = ground(parse(fmut), env)
        verdicts.append(product_explore(ga, gb, int(fire["period"])).verdict)
    rows.append({"class": "quantifier", "desc": "화재 ∃재실 → 특정 1대",
                 "verdict": f"k=1 {verdicts[0]} / k=2 {verdicts[1]}",
                 "layer": "곱(동치)×바인딩",
                 "gist": "동치는 바인딩의 성질", "states": "-", "sec": 0.0})
    return rows


def main() -> None:
    import json
    from adapt.inventory import base_office

    devs = from_adapt(base_office())
    data = json.load(open("explorer/corpus/joi_automation_codes.json"))
    t0 = _time.time()
    srows = scenario_rows(data, devs)
    frows = fault_rows(data, devs)
    total = _time.time() - t0

    lines = ["# E1: 전수 판정 표 (기계 생성)", "",
             f"인벤토리 base_office 14대 · 총 소요 {total:.0f}s", "",
             "## 표 1 — 시나리오별 전수 탐색·판정",
             "",
             "| 시나리오 | 술어(단편/GROUND/미해명) | 상태 | 에지 | 닫힘 |"
             " 자기동치 | 의무 판정 | 비고 |",
             "|---|---|---|---|---|---|---|---|"]
    for r in srows:
        if "error" in r:
            lines.append(f"| {r['name']} | {r['in_frag']}/{r['ground']}"
                         f"/{r['review']} of {r['preds']} | — | — | — | — |"
                         f" Unsupported: {r['error']} |"
                         f" {'; '.join(r['notes'])} |")
            continue
        f = "; ".join(r["findings"]) or "무결"
        lines.append(
            f"| {r['name']} | {r['in_frag']}/{r['ground']}/{r['review']}"
            f" of {r['preds']} | {r['states']} | {r['edges']} |"
            f" {'예' if r['closed'] else 'NO'} | {r['self_equiv']} |"
            f" {f} | {'; '.join(r['notes'])} |")
    lines += ["", "## 표 2 — 고장 주입 검출 (클래스별 ≥1)", "",
              "| 고장 클래스 | 주입 | 판정 | 검출 층 | 반례 요지 |",
              "|---|---|---|---|---|"]
    for r in frows:
        lines.append(f"| {r['class']} | {r['desc']} | {r['verdict']} |"
                     f" {r['layer']} | {r['gist']} |")
    lines += ["", "스코프 밖(호명): 미사용 캡처의 물리 점유 비가시 /"
              " k≥2 결합 칸은 실물 인벤토리 대기 / 복합 시나리오 곱 보류(TODO)"]

    out = "\n".join(lines)
    os.makedirs("simulator/runs", exist_ok=True)
    with open("simulator/runs/e1.md", "w") as fp:
        fp.write(out + "\n")
    print(out)
    print("\n→ simulator/runs/e1.md 저장")


if __name__ == "__main__":
    main()
