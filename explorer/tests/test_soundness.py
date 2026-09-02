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


# ── P1 Day 1: 미지원 무늬 fail-closed (2026-09-02 개정 계획) ─────────────────

from ..interp import Unsupported

TEMP = "(#TemperatureSensor).temperatureSensor_temperature"
HUMID = "(#HumiditySensor).humiditySensor_humidity"


def _refused(src: str) -> bool:
    try:
        product_explore(src, src, PERIOD)
        return False
    except Unsupported:
        return True


def test_joint_arithmetic_guard_is_refused():
    src = (f"t = {TEMP}\nh = {HUMID}\n"
           f"if (t + h > 100) {{ {SPEAK} }}\n")
    assert _refused(src), "두 입력을 섞은 산술 guard가 통과 (per-axis 분할로는 미보장)"


def test_read_vs_read_guard_is_refused():
    src = (f"t = {TEMP}\nh = {HUMID}\n"
           f"if (t > h) {{ {SPEAK} }}\n")
    assert _refused(src), "읽기 vs 읽기 비교가 통과 (대표값 쌍이 실경계를 놓침)"


def test_derived_single_key_guard_is_refused():
    # k=1이어도 항등이 아니면 경계가 이동한다: x/2>10의 실경계는 20
    src = f"t = {TEMP}\nif (t / 2 > 10) {{ {SPEAK} }}\n"
    assert _refused(src), "변형된 단일 키 guard가 통과 (술어 상수 10 ≠ 실경계 20)"


def test_independent_multikey_and_or_is_not_flagged():
    # 원자별 '맨 읽기 vs 상수'는 키가 여러 개라도 정확 — 오탐 금지
    src = (f"t = {TEMP}\nh = {HUMID}\n"
           f"if (t > 10 and h < 5) {{ {SPEAK} }}\n")
    assert product_explore(src, src, PERIOD).verdict == "EQUIV"


def test_bool_vs_bool_compare_is_not_flagged():
    # bool 도메인은 전량 열거되므로 bool끼리 비교는 정확 (보안모드 자동제어 무늬)
    src = ("prev := false\ncur = false\n"
           "if ((#Door).door_contact == true) { cur = true }\n"
           f"if (cur != prev) {{ {SPEAK} }}\nprev = cur\n")
    assert product_explore(src, src, PERIOD).verdict == "EQUIV"


def test_observable_counter_is_refused():
    src = ("n := 0\nif ((#Door).door_contact == true) { n = n + 1 }\n"
           "if (n >= 3) { (#Speaker).speaker_speak(n) }\n")
    assert _refused(src), "포화 counter 값이 액션 인자로 나가는데 통과 (cap 위가 뭉개짐)"


def test_comparison_only_counter_is_allowed():
    src = ("n := 0\nif ((#Door).door_contact == true) { n = n + 1 }\n"
           f"if (n >= 3) {{ {SPEAK} }}\n")
    assert product_explore(src, src, PERIOD).verdict == "EQUIV"


def test_arith_transformed_arg_is_refused():
    src = f"t = {TEMP}\n(#Speaker).speaker_speak(t * 2)\n"
    assert _refused(src), "산술을 거친 값의 인자 유출이 통과 (대표값 우연 일치 가능)"


def test_identity_arg_flow_is_allowed():
    src = f"t = {TEMP}\nif (t > 10) {{ (#Speaker).speaker_speak(t) }}\n"
    assert product_explore(src, src, PERIOD).verdict == "EQUIV"


_TWO_TIMERS = (
    "a := 0\nb := 0\nnow = (#Clock).clock_timestamp\n"
    "if ((#Door).door_contact == true) { a = now }\n"
    "if ((#Window).window_contact == true) { b = now }\n"
    "if (now - a > %s) { (#Speaker).speaker_speak(\"x\") }\n"
    "if (now - b > %s) { (#Speaker).speaker_speak(\"y\") }\n"
)


def test_two_timers_same_threshold_allowed():
    # 같은 단일 임계값이면 선후 부호(order_sig)로 교차 순서가 보존된다
    assert product_explore(_TWO_TIMERS % (30, 30),
                           _TWO_TIMERS % (30, 30), PERIOD).verdict == "EQUIV"


# ── ② 마감 차이 구간 (2026-09-02, deadline region) ───────────────────────────

def test_two_timers_distinct_thresholds_now_supported():
    # Day 1의 fail-closed를 ②가 대체 — 자기쌍은 EQUIV·닫힘이어야 한다
    r = product_explore(_TWO_TIMERS % (30, 60), _TWO_TIMERS % (30, 60), PERIOD)
    assert r.verdict == "EQUIV" and r.closed, (r.verdict, r.notes)


def test_two_timers_threshold_mutation_diverges():
    r = product_explore(_TWO_TIMERS % (30, 60), _TWO_TIMERS % (30, 45), PERIOD)
    assert r.verdict == "DIVERGE", r.verdict


def test_deadline_region_separates_states():
    # 같은 zone·같은 선후 부호라도 차이가 임계차(30)를 넘느냐로 미래
    # 교차 순서가 갈린다 — 상태 키가 갈라야 한다 (구 부호 방식은 병합)
    from ..interp import parse
    from ..predicates import classify_vars
    from ..explore import derive_axes, normalize
    stmts = parse(_TWO_TIMERS % (30, 60))
    vinfo = classify_vars(stmts)
    axes = derive_axes(stmts, vinfo)
    T = 1_000_000
    k1 = normalize({"a": T - 5, "b": T - 40}, {}, T * 1000, vinfo, axes)
    k2 = normalize({"a": T - 15, "b": T - 40}, {}, T * 1000, vinfo, axes)
    assert k1 != k2, "차이 35s와 25s(임계차 30 양쪽)가 같은 키로 병합"
    k3 = normalize({"a": T - 5, "b": T - 40}, {}, T * 1000, vinfo, axes)
    assert k1 == k3


# ── 점프 억제 시 실걸음 fast-forward (2026-09-02, E3 C18_007 회귀) ──────────

TRACKER_HOUR = (
    "last := 0\n"
    "now = (#Clock).clock_timestamp\n"
    "last = now\n"
    'if ((#Clock).clock_hour >= %d) { (#Speaker).speaker_speak("late") }\n'
)


def test_suppressed_jump_still_reaches_calendar_boundary():
    # now-추적 레지스터가 점프를 억제해도 달력 경계(22시 vs 23시) 뒤의
    # 행동 차이는 실걸음으로 도달해 잡아야 한다 — 이전엔 tick 후속이
    # 같은 키로 접혀 상태 1개로 '닫힘·EQUIV'를 선언했다 (허위 EQUIV)
    r = product_explore(TRACKER_HOUR % 22, TRACKER_HOUR % 23, PERIOD)
    assert r.verdict == "DIVERGE", (r.verdict, r.n_states, r.notes)


def test_suppressed_jump_selfpair_still_equiv():
    r = product_explore(TRACKER_HOUR % 22, TRACKER_HOUR % 22, PERIOD)
    assert r.verdict == "EQUIV" and r.closed, (r.verdict, r.notes)


# ── ① clock.time(HHMM) 달력 모델링 (2026-09-02) ──────────────────────────────

TOD = 'if (clock.time >= %d) { (#Speaker).speaker_speak("night") }\n'


def test_clock_time_axes_and_selfpair():
    from ..interp import parse
    from ..predicates import classify_vars
    from ..explore import derive_axes
    stmts = parse(TOD % 2300)
    axes = derive_axes(stmts, classify_vars(stmts))
    assert (">=", 2300) in axes.tod_ops, axes.tod_ops
    r = product_explore(TOD % 2300, TOD % 2300, PERIOD)
    assert r.verdict == "EQUIV" and r.closed, (r.verdict, r.notes)


def test_clock_time_threshold_mutation_diverges():
    # 22:00~23:00 사이에서만 행동이 갈린다 — 경계 점프가 있어야 잡힌다
    r = product_explore(TOD % 2300, TOD % 2200, PERIOD)
    assert r.verdict == "DIVERGE", r.verdict


def test_clock_time_2400_is_never_true():
    # HHMM 최대는 2359 — `>= 2400` 분기는 죽은 코드와 동치
    dead = TOD % 2400
    empty = "x = (#Clock).clock_hour\n"
    assert product_explore(dead, empty, PERIOD).verdict == "EQUIV"


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
