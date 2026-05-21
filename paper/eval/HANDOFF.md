# Handoff — Group P 종료, Phase 2 진입 직전

날짜: 2026-05-20
브랜치: paper (commit 172c6bd 위에 미커밋 변경 다수)

## 1. 현재 baseline

| Run | Pass | % | 비고 |
|---|---:|---:|---|
| Phase 0 (5/19 14:42) | 271/307 | 88.3 | 5/19 lowering overhaul 직후 첫 측정 |
| Phase 1 (5/19 18:44) | 270/307 | 87.9 | sim quantifier/comparator/period-aware fixes |
| **Group P (5/20 01:11)** | **262/307** | **85.3** | catalog conformance + cron iteration + D-3/D-5 prompt |

**감소(-2.6pp)는 sim 의미가 정확해진 대가**. IR sim이 user 정의대로 cron-매발화 의미를 반영하면서 lowering이 못 따라가는 케이스(예: break 의미 mismatch) 가 표면화. 이 mismatch들은 paper §6.4 verification system이 의도적으로 잡아야 할 obligation 위반.

## 2. 코드 변경 (미커밋, paper 브랜치)

### Group P — 이번 세션
1. **`paper/timeline_ir.py`** — `validate_ir_against_devices(ir, connected_devices)` 신규 함수. IR의 모든 `Service.Attr` 참조가 `connected_devices`의 어느 category에 있어야 함. `clock.*`, `$var`, `True/False/None/Null`은 제외. 미존재 시 `IRValidationError`.
2. **`paper/run_local_ir.py`** — `extract_ir` 후처리에서 위 함수 호출. import 라인 갱신. 실패 시 `JoiGenerationError(error_code="ir_catalog_mismatch")`.
3. **`paper/timeline_ir_extractor.md`** — D7b D-5 alternation 규칙에 "두 call 슬롯의 값은 서로 다른 NL 값"이라는 강제 문구 추가. D7b 표 + Lexical Cues 표 두 군데 명시.
4. **`files/joi_cycle.md`** — D-4 phase lifecycle template를 `if(phase==0){...} if(phase==1){...}` (두 if) → `if(phase==0){...} else {...}` (단일 if/else)로 변경. Ex4 예시도 동일.
5. **`paper/simulators/ir_simulator.py`** — `run_ir_simulation`에서 top-level `start_at(cron)`이면 모든 cron 발화 시각마다 body 재실행. 이전: 첫 fire 한 번만.
6. **`paper/simulators/joi_simulator.py`** — cron이 있으면 cron 발화 시각마다 script 실행 (period=0이면 sub-tick 없이 cron만, period>0이면 cron 윈도우 내 sub-tick 추가). 이전: cron + period=0은 one-shot 처리.
7. **`paper/simulators/test_e2e.py`** — D-7 test를 "one-shot" 해석에서 user 정의 "cron recurring + matching period" 인코딩으로 갱신.

### Phase 1 (5/19 18:44) 변경 — 이미 적용됨
- **`paper/simulators/expr.py`** — `_BUILTIN_FUNCS`에 `all/any/avg` 추가 + single-device collapse evaluator.
- **`paper/simulators/event_synth.py`** — `_unwrap_quantifier` + `_gather_assignments` FuncCall 재귀. 추가로 `_synth_wait(period_ms=...)` + `_walk(period_stack=[...])` (period-aware prelude/fire).
- **`paper/simulators/comparator.py`** — `compare_traces(prefix_mode=...)`. MAX_TRACE 포화 시 마지막 group trim 후 비교.
- **`paper/simulators/eval_harness.py`** — saturation 감지 시 `prefix_mode=True`로 호출.

### Phase 0 (5/19 14:42) — 이미 적용됨
- `paper/eval/run_baseline.sh` — 카테고리별 segmented 실행 + /tmp 로그 + 누적 summary.
- `paper/eval/baseline.md`, `paper/eval/failing_rows.md` — 초기 측정 문서.

## 3. user 합의된 컨벤션 정리

### cron 의미론 (5/20 명시화)
- `cron` 설정되면 **항상 모든 발화 시각에 fire**. one-shot이라는 개념 없음.
- `period=0`: cron 발화만 (sub-tick 없음). 예: cron `0 18 * * *` + period=0 → 매일 18시 1번.
- `period>0`: 각 cron 발화 윈도우 안에서 period 간격으로 추가 sub-tick.
- IR 측: top-level `start_at(cron)` + cycle 없이 body가 있으면 동일 의미 (매 cron 발화마다 body 실행).
- IR 측: cycle wrapping은 period-driven 반복용 (no cron 또는 cron + 더 짧은 period).

### catalog conformance (5/20)
- IR의 `Service.Attr` 참조는 `connected_devices`의 어떤 device category에 존재해야 함. 미존재 = extractor 환각, IRValidationError로 reject.
- JoI 측 catalog 검사는 Phase 2 L1 정적 분석기가 담당.

### lowering 컨벤션 (5/20 강제)
- D-4 phase lifecycle: `if(phase==0){body; phase=1} else {body}` 단일 if/else. 두 개의 if는 첫 tick에 body 중복 실행.
- D-5 alternation: body에 inter-call delay 유지, period는 inter-call delay 값. 두 call slot은 NL의 두 distinct 값을 가짐.

## 4. 남은 실패 클러스터 (Group P 사후 ~45 실패)

전부 pipeline 영역 (lowering / IR extractor) — sim 결함 아님. Phase 2-3 verification system이 자동 진단 + Phase 4 retry harness가 self-correction signal로 변환.

### Cluster A — Lowering이 2-call 시퀀스 중 둘째 call 누락 (~8건)
- C01 #15/#18/#19 (generate+save, read+speak)
- C02 #10
- C04 #1
- C15 #9/#10 (cron + read+speak)

### Cluster B — IR/JoI cond key namespace drift (~6건)
- 거의 모두 catalog에 없는 attribute 환각 (IR `Light.IsOn`, JoI `(#Light).isOn` 같은). canonical_key가 prefix-strip으로 통일을 시도하지만 환각 케이스에서 갈라짐.
- 예: C10 #6, C05 #19/#20/#30 (compound cond)

### Cluster C — D-3 phase double-emit (~3건, timeout)
- C12 #5/#13 (smoke detected siren cycle). joi_cycle.md prompt 갱신했지만 LLM이 옛 두-if 패턴 여전히 emit하는 경우 있음.

### Cluster D — Cron + cycle composition mismatch (~6건)
- C18 #4/#10 등. IR은 `start_at(cron); cycle{...} until ...`. JoI는 `cron + period + break` 패턴. break가 전체 프로그램을 terminate하지만 IR cycle은 cron 발화마다 재진입.

### Cluster E — D-5 alternation NL 값 미스 (~3건)
- C13 #2/#4/#7. NL은 두 distinct 값 ("sleep mode and auto mode")인데 extractor가 같은 값 두 번 emit. extractor prompt 5/20 강화했지만 LLM이 여전히 종종 환각.

### Cluster F — Misc (C14 counter, multi-cron, args mismatch ~15건)
- C14 4건 — counter/increment idiom 미구현 (paper §7 future work `cycle(n=N)` 확장)
- C15 #15, C16 #5 — multi-cron reject 정책 (paper §7 limitation)
- 나머지 args 정규화 / parse error 등

## 5. Task 진행 (모두 완료)

```
[completed] #11 P1 — IR catalog conformance check
[completed] #12 P2 — lowering D-3 single if/else template
[completed] #13 P3 — extractor D-5 alternation convention
[completed] #14 P4 — sim cron iteration for start_at(cron)
[completed] #15 P5 — re-baseline after P1-P4
```

이전 Phase 0/1 task들도 모두 completed.

## 6. 다음 단계 — Phase 2 (IR-FSM + L1 정적 분석기)

paper §6.4 verification system의 본체. Group V로 명명.

### V1. IR-FSM 유도 — `paper/verifier/ir_fsm.py` (NEW)
- IR 객체 → IR-FSM (transition-obligation list).
- 각 IR op마다 의무 발행:
  - `wait(cond, edge)`: cond 전환 시점 의무
  - `call(target, args)`: 정확히 1회 emit 의무 (위치 + 시간)
  - `cycle(period, until)`: re-arming 의무, until 종료 의무
  - `if`: 활성 분기만의 의무
  - `delay(N)`: 직전-다음 의무 간 간격 의무
  - `read`: register 갱신 + 후속 dependency
  - `start_at(cron)`: 각 cron 발화에서 후속 body 재시작
- composition: sequencing / re-arming / register-dep / reachability 4종.
- 비용 2주.

### V2. L1 정적 분석기 — `paper/verifier/l1_static.py` (NEW)
- AST-only 검사 (실행 없이):
  - JoI script의 모든 `(#X).method(...)` 및 `(#X).attr`이 connected_devices 또는 catalog에 존재 (Cluster B의 JoI-side 검출).
  - flag 초기화 누락 (`triggered := false` 없이 사용)
  - 단위 누락 delay
  - selector 형식 오류
  - cron 슬롯 범위 (`hhmm >= 2400`, minute=55 for 11PM 등)
  - 괄호/중괄호 균형 (C07 #10 같은 parse_fail 사전 차단)
- 비용 4-5일.

### V3. L2 obligation trace checker — `paper/verifier/l2_runtime.py` (NEW)
- scenario 합성 → JoI sim → trace → IR-FSM stream → 의무별 satisfaction.
- 출력: coverage rate + 위반 의무 리스트 (IR feature path, op kind, expected vs observed).
- L3 (full diff-sim)는 기존 comparator 재활용.
- 비용 3-4일 (V1 끝난 직후).

### R1. retry harness — `paper/verifier/diagnose.py` + `retry_harness.py` (NEW)
- V2/V3 위반 → IR-feature granular retry message → lowering 재호출.
- P1 reject (catalog mismatch)도 같은 형식으로 extractor retry.
- 비용 1.5주 (V 끝난 뒤).

## 7. 핵심 결정 사항 / 결론

1. **Group P 종료**. 잔존 실패는 모두 pipeline 영역. sim 더 만지면 verification 시스템의 진단 효력 떨어짐.
2. **pass rate -2.6pp는 의미적으로 정확해진 대가**. paper 흐름과 정합 (verification system이 잡아야 할 obligation 위반들).
3. **Phase 2 (Group V)** 진입 권장. IR-FSM 유도부터 시작.

## 8. 재현 가능성

```bash
cd /home/gnltnwjstk/joi
./paper/eval/run_baseline.sh           # 17 cats 전체
./paper/eval/run_baseline.sh C18       # 단일 카테고리
rm -rf paper/simulators/cache/*.json   # 재캐싱
```

E2E 회귀 체크: `python3 -m paper.simulators.test_e2e` (11/11 pass).

## 9. 파일 색인

- `paper/eval/baseline.md` — Phase 0/1 history (Group P 미반영, 아직 5/19 기준)
- `paper/eval/failing_rows.md` — Phase 1 시점 클러스터 분류 (Group P 미반영)
- `paper/eval/run_baseline.sh` — segmented runner
- `paper/eval/HANDOFF.md` — 이 문서 (최신)
- `/tmp/joi_eval_*_20260520_011057.log` — Group P 최종 baseline raw logs
- `/tmp/joi_eval_summary_20260520_011057.txt` — Group P 최종 summary

## 10. 메모리 갱신 권장

이 핸드오프를 토대로 `~/.claude/projects/-home-gnltnwjstk/memory/`에 신규 메모리 작성 권장:
- `project_pipeline_state_2026_05_20.md` (전체 상태 스냅샷)
- `MEMORY.md` 인덱스에 추가, 이전 `2026_05_19` 항목은 superseded 표시.
