# 인계: Explorer 타이머 이산화 (2026-09-14)

받는 쪽: 타이머 이산화를 맡을 AI. 작성: E2 담당 세션(Claude). 결정권자: whisoo.

## 0. 한 줄 요약

Explorer의 새 timed 검색은 **경과 시간을 값 그대로 상태에 담는다.** 그래서 "2시간 안에 사건이 오나 /
2시간을 넘기나"만 가르면 되는 요구도 0.1초마다 다른 상태가 생겨 한도에 걸린다. 틱 카운터·timestamp
기록·IR timeout 을 **"상수보다 작음 / 같음 / 큼" 구간으로 묶어서** 한도 안에 닫히게 만드는 것이 목표다.
**틀린 EQUIV 를 하나라도 만들면 실패다.**

## 1. 논문과 실험에서의 위치

- 논문: PerCom 2027 VETS (제출 2026-09-18 AoE). 브랜치 `paper`, 저장소 `~/joi`.
- Explorer = IR(Timeline) 과 LLM 이 만든 JoI 코드의 동작 동등성 검증기. 판정 EQUIV / DIVERGE(반례) / REFUSED.
- E2 = 독립 정답기로 Explorer 판정을 검사한 실험. 142쌍, 동결 `649cb9c`. 결과 `RESULTS.md`, `INSPECTION_2026-09-14.md`.
  - 판정을 낸 104쌍 중 정답기와 어긋난 판정 0.
  - **판정 못 함 38쌍(27%)** 중 **19쌍이 시간·상태 수 한도 초과** ← 이 인계의 대상.
- 실행 인터프리터: `~/temp/bin/python` (시스템 python3 아님).

## 2. 대상 19쌍 (본 실행: 쌍당 120 초, max_states 400,000, max_transitions 2,000,000)

| 쌍 | 본 실행 결과 | 쌍의 특징 |
|---|---|---|
| C20-O/correct, C20-O/fault1 | TIMEOUT | 2 HOUR timeout 창. JoI 는 0.1초 틱을 72,000 까지 셈. IR on_timeout 에 `_noop` 시계 읽기 |
| C07/correct, fault1–4 | TIMEOUT | 22시 이후 10분 지속 + 5분 주기 회차 ×7 + 0.5초 점멸 ×10. JoI 틱 카운터 여러 개, `(#Clock).Hour`, IR `_noop` |
| E1-034/correct, fault1–4 | TIMEOUT | 오븐 4 HOUR 지속(JoI 틱 144,000) + 1 MIN 확인 timeout |
| C01/fault2 | TIMEOUT | 2 MIN 부재 timeout, JoI 틱 1,200 |
| C05/fault2, C05/fault3 | REFUSED (탐색 미완, state cap) | |
| C15/correct, C15/fault1 | REFUSED (탐색 미완, state cap) | IR·JoI 둘 다 clock 읽음 |
| C18/correct | REFUSED (탐색 미완, state cap) | clock 읽음 |
| C19/correct | REFUSED (탐색 미완, state cap) | clock 읽음 |

쌍 원문: `pairs/e1_pairs.json` (`pair_id` 로 찾기; `ir`, `binding`, `devices`, `joi`, `catalog`, `t_start_ms`).
정답기 이력: `histories/e1_histories.json` (`histories[<base_case>]`).
**정답기는 이 19쌍 중 올바른 쌍 전부에서 차이를 못 찾았고, 오류 쌍 전부(C05 f2·f3, C07 f1–4, C20-O f1, E1-034 f1–4, C01 f2)에서 차이를 찾았다** (`runs/e2_run.ref-current-supp.jsonl.gz`).
즉 올바른 쌍은 EQUIV, 오류 쌍은 DIVERGE 가 나와야 기대와 맞는다. C15/fault1(`h < 6` → `h <= 6`)만 예외: 정답기도 차이를 못 찾았다.
정답기 이력이 06시대를 지나지 않았을 가능성이 크다(확인 안 함). 관찰 불가 오류로 단정하지 말고, Explorer 가 DIVERGE 를 내면 재생 확인 결과로 판단할 것.

## 3. 원인 증거 — C20-O/correct 로 직접 바꿔 본 결과 (각 300 초 한도)

요구(CHI'19): "Sally 가 침실에 들어오고, 그 뒤 2시간 안에 해가 지면 불을 켜라."

| 변형 | 정답기 (C20-O 이력 324개) | Explorer |
|---|---|---|
| 원본 | 모두 같음 | 판정 불가 (본 실행 TIMEOUT) |
| 창 2 MIN / 10 MIN / 1 SEC (JoI 틱도 맞춤) | — | 판정 불가 (transition cap, 상태 ~33만) |
| 밝기 입력을 {20, 500} 두 값으로 제한 | — | 판정 불가 (state cap) |
| IR `_noop` 시계 읽기만 제거 (2 HOUR 유지) | — | 판정 불가 (transition cap) |
| **`_noop` 제거 + 창 2 MIN** | — | **EQUIV-FIXPOINT, 상태 15,616, 13.6 초** |
| JoI 를 timestamp 방식으로 (`t_in = ts`, `ts - t_in >= 7200`) | 모두 같음 | 판정 불가 (transition cap) |
| timestamp 방식 + `_noop` 제거 | 모두 같음 | 판정 불가 (transition cap) |
| IR·JoI 둘 다 1 MIN 주기(JoI 틱 120) + 입력 격자 60 초 | 모두 같음 | 판정 불가 (state cap, 28 초) |
| IR 만 1 MIN 주기 | 3개 다름 | DIVERGE (진짜 차이 — 회차 사이 1분 동안 재입장 놓침) |
| IR·JoI 1 MIN, 입력 격자 100 ms | 107개 다름 | DIVERGE (진짜 차이 — JoI 가 최대 1분 늦음) |

재현: `probe_c20.py` (이 폴더). `~/temp/bin/python probe_c20.py <variant>`; 변형 이름은 `--list`.

해석:
1. **시간 길이를 줄이는 것만으로는 안 닫힌다.** 2분짜리도 `_noop`(시계 읽기)이 있으면 안 닫혔다.
2. **시계 읽기가 있으면 절대 시각이 상태 키에 들어간다.** `timed.py` 의 `absolute_time = horizon_ms is not None or clock_sensitive`
   → `store_key` 가 값을 그대로, `node_key` 가 `node.now` 를 그대로 담는다. `_noop` 은 E1 IR 작성 때
   "timeout 이면 아무것도 안 함" 을 적을 수단이 없어 넣은 `read _noop = Clock.Hour` (`E1_adequacy/irs.py:23`) 다.
3. **시계를 안 읽어도 프로그램 변수(틱 카운터, timestamp 기록)는 값 그대로다.** `store_key` 가 나이(age-ms)로 바꾸는 것은
   실행기 내부 타이머(`internal_timers`)뿐이다. JoI 의 `ticks` 는 틱마다 다른 값 → 틱마다 다른 상태.
4. timestamp 방식도 같은 이유로 안 닫힌다: `(#Clock).Timestamp` 읽기 → `clock_sensitive` → 절대 시각 유지.

## 4. 현재 코드 구조 (읽을 곳)

- `explorer/verification/gate.py` `gate_pair` → `prepare_pair` → `timed.timed_product(..., verification_mode='auto')`.
  E2 는 `run_e2.py:explorer_side` 에서 `prepare_pair` + `timed_product(horizon_ms=None, t0_ms=T0_EXPLORER+t_start_ms)` + `fold_verdict`.
- `explorer/verification/timed.py` `timed_product` (auto):
  1. `relational_analysis.analyze` 통과 시 `relational_product` (정수 카운터 관계 경로, `docs/proof/RELATIONAL_FIXPOINT.md`).
  2. 입력 자동이면 `smt.smt_product` 시도.
  3. 아니면 구체 BFS. 상태 키 = `node_key` (양쪽 저장소·GV·시각 위상·유지 입력). `reads_clock` → `absolute_time`.
  4. 한도: `max_states`, `max_transitions`, `max_input_combinations` → `UNKNOWN` → `fold_verdict` 에서 REFUSED.
- `explorer/verification/time_events.py` `silent_deadline`, `crossed_input_grid`: 양쪽이 입력을 안 읽는 대기면 다음 만료로 건너뜀
  (`docs/proof/UNBOUNDED_TIME.md`). **JoI 가 틱마다 입력을 읽으면 건너뛸 수 없다.**
- 옛 경로 `explorer/analysis/explore.py`, `explorer/verification/product.py` 에는 **쌍별 마감 차이 구간(deadline region)과 counter 포화**가 있었다
  (`explore.py:695` 부근, `_tod_flips`, `_regs_frozen`, walk_time). 새 timed 경로는 이것을 쓰지 않는다
  (`docs/model/SUPPORTED_FRAGMENT.md` "타이머 여러 개", "알려진 잔여 갭").
  `UNBOUNDED_TIME.md` 도 "여러 타이머의 region/zone 일반 추상화는 구현하지 않았다" 고 적어 두었다.
- 증명 문서: `docs/proof/PROOF_OBLIGATIONS.md` (L4 시간 생략과 상태 키의 미래 보존), `SEARCH_CORRECTNESS.md` §3–4.
- 거절 무늬: `explorer/analysis/features.py` (joint-guard 등), `SUPPORTED_FRAGMENT.md` "거절하는 것".

## 5. 해야 할 것

아이디어(whisoo): 타이머는 결국 "기한 안에 조건 만족 vs 기한 넘김" 둘 중 하나다. 들어온 시각을 timestamp 로 재든 틱을 세든,
판정에 필요한 것은 비교 상수에 대한 위치와 사건의 순서뿐이니 이산화하자.

구체 목표:
1. **시간처럼 움직이는 값을 알아보기.**
   - JoI 틱 카운터: 매 틱 `v = v + 1`, 상수로만 리셋, 상수와의 비교에만 쓰임, 관찰값(ACTION 인자)으로 안 흘러감.
   - timestamp 기록: `t = Clock.Timestamp` 스냅샷, `Clock.Timestamp - t (op) 상수` 비교에만 쓰임.
   - IR `wait` 의 `for` / `timeout`, `delay`, cycle `period` (이미 내부 타이머).
2. **구간으로 묶기.** 각 시간 값을 "비교 상수들로 나눈 구간" 으로 바꾼다. 서로 다른 시계(IR 타이머 ↔ JoI 카운터) 사이의
   차이가 판정에 영향을 주면 그 차이도 구간으로 보존한다(timed automata region / DBM zone 이 표준). 쌍별 차이 구간은 옛 경로에 선례가 있다.
3. **판정에 쓰지 않는 시계 읽기 처리.** `_noop` 처럼 읽기만 하고 어디에도 안 쓰는 `Clock.Hour` 때문에 절대 시각을 유지하지 않도록 한다
   (죽은 읽기 판별). 실제 시각 비교(`Clock.Hour >= 22`)는 기존 `tod_ops`/catalog-range 방식과 맞물려야 한다.
4. **DIVERGE 는 지금처럼 구체 재생 확인**(`replay_divergence`, `fold_verdict`) 을 통과해야만 낸다. 구간 상태에서 찾은 반례를 구체 입력 경로로 풀어낼 것.
5. **못 묶는 모양은 지금처럼 UNKNOWN/REFUSED.** 넓게 받아들이지 말 것.

## 6. 수용 기준

- **틀린 EQUIV 0.** 올바른 쌍에서 EQUIV, 오류 쌍에서 재생 확인된 DIVERGE. 이미 판정이 난 104쌍에서 EQUIV↔DIVERGE 뒤집힘 0.
- C20-O/correct 원본 → EQUIV, C20-O/fault1 → DIVERGE(재생 확인), 둘 다 쌍당 120 초 안.
- 19쌍 전부 다시 돌린 표(쌍, 전 판정, 새 판정, 상태 수, 초). 판정 못 한 쌍은 이유와 함께 남긴다.
- 기존 회귀 전부 통과: `test_contract`, `test_input_coverage`, `test_service_model`, `test_soundness`, `test_exact_tick`,
  `test_time_elision`, `test_relational_fixpoint`, `test_search_correctness`, `explorer.analysis.features`, `explorer.runtime.ir_step`
  (`python -m explorer.tests.<name>`, 인터프리터 `~/temp/bin/python`, 작업 디렉터리 `~/joi`).
- 새 추상화마다 **반례 테스트**를 추가: 마감 직전/직후(±1 틱) 사건, 두 타이머 마감 동시, 리셋 직후 재시작, 틱 카운터가 관찰값으로 새는 경우(거절돼야 함).
- 증명 문서 갱신: 새 구간 묶음이 L4(상태 키의 미래 보존)를 왜 만족하는지 `docs/proof/` 에 적는다. 적용 조건과 거절 조건을 `SUPPORTED_FRAGMENT.md` 에 적는다.

## 7. 지켜야 할 것

- **정답기(`E2_fidelity/reference/`)는 읽지도 고치지도 말 것.** 정답기는 Explorer 코드를 본 적 없는 별도 작성자가 명세만으로 만든 독립 기준이다.
  쌍(`pairs/`), 이력(`histories/`), 동결 실행 결과(`runs/`)도 고치지 않는다.
- 결과는 **새 Explorer 판** 으로 기록한다. 동결판 결과를 덮어쓰지 않는다. E2 다시 돌리기는 `run_e2.py` 를 새 출력 이름으로 (E2 담당과 조율).
- **동시 작업 충돌 주의:** E2 담당(Claude)이 같은 시기에 바인딩 규칙을 고친다
  — `explorer/runtime/ground.py`, `explorer/verification/observation.py`, `explorer/verification/gate.py`(기기 변환부) 와 `E2_fidelity/run_e2.py`.
  이 파일들은 건드리지 말고, 별도 브랜치나 git worktree 에서 작업한 뒤 합칠 것.
- `files/timeline_ir/extractor.md` 수정 금지.
- git remote URL 에 토큰이 들어 있다. `git remote -v` 출력이나 push 로그를 그대로 보여주지 말 것.
- 파일 삭제는 whisoo 승인 없이 하지 말 것.
- 쉬운 말로 기록할 것(whisoo 요청). 논문 원고(`PerCom/*/PerCom_version.md` 등)는 쓰지 않는다.

## 8. 범위 밖 (이번에 안 해도 됨)

- 끝없이 커지는 카운터·누적합 12쌍(E1-099, E1-095, C13_006, C14_003 — `unbounded carried vars`),
  실행 중 값끼리 비교 5쌍(E1-028 — `joint-guard`). 다만 E1-099 의 `Clock.Timestamp >= $t_on + 300 + 120 * $k` 는 타이머 문제와 이어져 있으니 참고.
- 바인딩·셀렉터·any/all 차이: whisoo 결정으로 E2 에서 무시한다(E2 담당이 처리).
