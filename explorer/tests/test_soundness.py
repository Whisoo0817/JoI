"""Soundness 회귀 테스트 — 2026-09-02 P0 수정의 반례들을 고정한다.

명세: explorer_soundness_fix_spec (타 에이전트 분석) + whisoo 결정 3건
  ① tick 내 액션 순서도 관찰값이다 (정렬 금지)
  ② 바인딩 애매성은 없다고 가정 (규약 유지 — 여기선 테스트 없음)
  ③ 내부 UNKNOWN은 밖으로 REFUSED로 접는다 (3-way 유지)

Run:  python3 -m explorer.tests.test_soundness
"""

from __future__ import annotations

import traceback

from .. import product as product_mod
from ..explore import explore, reps_from_preds
from ..gate import GateResult, fold_verdict
from ..product import (Divergence, ProductResult, ReplayResult, merge_axes,
                       product_explore)
from ..runner import JoiRunner

PERIOD = 60_000

SPEAK = '(#Speaker).speaker_speak("a")'
MAIL = '(#EmailProvider).emailProvider_sendMail("x", "s", "b")'


# ── 이슈 1: tick 내 액션 순서·중복 ───────────────────────────────────────────

def test_same_tick_action_order_is_observable():
    a = f"{SPEAK}\n{MAIL}\n"
    b = f"{MAIL}\n{SPEAK}\n"
    assert product_explore(a, b, PERIOD).verdict == "DIVERGE", \
        "순서만 다른 두 프로그램이 EQUIV로 통과 (사진→이메일 뒤집힘 미검출)"


def test_identical_order_remains_equivalent():
    a = f"{SPEAK}\n{MAIL}\n"
    assert product_explore(a, a, PERIOD).verdict == "EQUIV"


def test_duplicate_actions_are_not_deduplicated():
    once, twice = f"{SPEAK}\n", f"{SPEAK}\n{SPEAK}\n"
    assert product_explore(once, twice, PERIOD).verdict == "DIVERGE", \
        "같은 tick의 같은 액션 2회가 1회와 동일 취급됨"


def test_action_arguments_are_observable():
    a = '(#Speaker).speaker_speak("a")\n'
    b = '(#Speaker).speaker_speak("b")\n'
    assert product_explore(a, b, PERIOD).verdict == "DIVERGE"


# ── 이슈 2: 미완 그래프는 EQUIV가 아니다 ─────────────────────────────────────

LATCH = (
    "seen := false\n"
    "if ((#Door).door_contact == true) { seen = true }\n"
)


def test_state_cap_yields_unknown():
    saved = product_mod.STATE_CAP
    product_mod.STATE_CAP = -1
    try:
        r = product_explore(LATCH, LATCH, PERIOD)
    finally:
        product_mod.STATE_CAP = saved
    assert r.verdict == "UNKNOWN" and not r.closed, \
        f"cap에 걸린 미완 탐색이 {r.verdict} (EQUIV 금지)"


def test_equiv_requires_closed_graph():
    r = product_explore(LATCH, LATCH, PERIOD)
    assert r.verdict == "EQUIV" and r.closed


# ── 이슈 3: 인접 임계 사이 열린 구간 ─────────────────────────────────────────

def test_close_real_thresholds_create_middle_cell():
    # (10, 10.5) 구간에서만 발화 vs 무발화 — 구 c±1 대표값으로는 미검출
    a = ("t = (#TemperatureSensor).temperatureSensor_temperature\n"
         'if (t > 10 and t < 10.5) { (#Speaker).speaker_speak("hot") }\n')
    b = "t = (#TemperatureSensor).temperatureSensor_temperature\n"
    assert product_explore(a, b, PERIOD).verdict == "DIVERGE", \
        "임계 10과 10.5 사이 열린 구간이 입력 분할에서 누락"


def test_gap_one_integer_thresholds_create_middle_cell():
    # 간격 1인 임계쌍(10, 11)도 실수 도메인이면 중간 구간이 있다
    a = ("t = (#TemperatureSensor).temperatureSensor_temperature\n"
         'if (t > 10 and t < 11) { (#Speaker).speaker_speak("mid") }\n')
    b = "t = (#TemperatureSensor).temperatureSensor_temperature\n"
    assert product_explore(a, b, PERIOD).verdict == "DIVERGE"


def test_reps_cover_every_region():
    # 대표값 집합이 모든 진리벡터 구간을 하나씩 덮는다
    pairs = [(">", 10.0), ("<", 10.5), (">=", 20.0)]
    reps = reps_from_preds(pairs)
    assert any(10.0 < r < 10.5 for r in reps), reps
    assert any(r <= 10.0 for r in reps) and any(r >= 20.0 for r in reps)


def test_merge_axes_builds_joint_partition():
    # 임계가 양쪽에 갈라져 있으면 합집합 술어로 대표값을 다시 만들어야 한다
    a = ("t = (#TemperatureSensor).temperatureSensor_temperature\n"
         'if (t > 10) { (#Speaker).speaker_speak("x") }\n')
    b = ("t = (#TemperatureSensor).temperatureSensor_temperature\n"
         'if (t > 10.4) { (#Speaker).speaker_speak("x") }\n')
    assert product_explore(a, b, PERIOD).verdict == "DIVERGE", \
        "(10, 10.4] 구간이 병합 축에서 누락 → 허위 EQUIV"


def test_merge_axes_keeps_cell_preds():
    a = JoiRunner.from_src(
        "t = (#TemperatureSensor).temperatureSensor_temperature\n"
        'if (t > 10) { (#Speaker).speaker_speak("x") }\n')
    m = merge_axes(a.axes, a.axes)
    assert m.cell_preds, "merge_axes가 cell_preds를 버림 (replay cell_of 불능)"


# ── 이슈 4: product의 시간 점프 안전 조건 ────────────────────────────────────

NOW_TRACKER = (
    "last := 0\n"
    "now = (#Clock).clock_timestamp\n"
    'if (now - last > 600) { (#Speaker).speaker_speak("tick") }\n'
    "last = now\n"
)


def test_now_tracking_register_blocks_jump_in_product():
    r = product_explore(NOW_TRACKER, NOW_TRACKER, PERIOD)
    assert r.verdict == "EQUIV", r.verdict
    assert "jump suppressed: now-tracking register" in r.notes, \
        "explore에만 있던 레지스터 동결 가드가 product에 없음"


def test_explore_and_product_share_jump_guard():
    g = explore(NOW_TRACKER, PERIOD)
    assert any("jump suppressed" in n for n in g.notes)


# ── 이슈 5 + 결정 ③: 게이트 판정 접기 ────────────────────────────────────────

def _pr(verdict: str, closed: bool = True) -> ProductResult:
    pr = ProductResult(verdict, closed=closed)
    if verdict == "DIVERGE":
        pr.divergences = [Divergence(1, {}, 0, ("a",), ("b",), [])]
    if verdict == "UNKNOWN":
        pr.notes = ["CAP HIT"]
        pr.closed = False
    return pr


def test_diverge_requires_confirmed_replay():
    g = fold_verdict(_pr("DIVERGE"), [ReplayResult(False, note="허위?")], [])
    assert g.verdict == "REFUSED" and any("재생 미확인" in n for n in g.notes)


def test_confirmed_replay_keeps_diverge():
    g = fold_verdict(_pr("DIVERGE"), [ReplayResult(True, at_step=0)], [])
    assert g.verdict == "DIVERGE"


def test_gate_folds_unknown_into_refused():
    g = fold_verdict(_pr("UNKNOWN"), [], [])
    assert g.verdict == "REFUSED" and any("탐색 미완" in n for n in g.notes)


def test_gate_passes_equiv():
    assert fold_verdict(_pr("EQUIV"), [], []).verdict == "EQUIV"


# ── runner ───────────────────────────────────────────────────────────────────

def main() -> int:
    tests = [(k, v) for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except Exception:
            failed += 1
            print(f"FAIL {name}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
