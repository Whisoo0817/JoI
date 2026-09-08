# 관계 기반 무제한 ACTION 검증

2026-09-08. 구현: `relational-state-v1`. 기존 concrete / symbolic / SMT 경로는 유지한다.
새 경로는 `verification_mode='relational', horizon_ms=None`으로 명시적으로 선택한다.
`None`은 요청 범위이며 성공의 근거는 초기 관계·전이 의무·그래프 폐쇄다.

## 1. 실제 지원 범위

- IR: 첫 실행 명령이 ENTER_CYCLE인 단일 최상위 이름 카운터 cycle, 양의 고정
  period, cycle 전체가 프로그램. 중첩 cycle, count 숫자 상한, cycle until은 v1에서 거절.
- JoI: 같은 completion-relative period의 PauseRunner. 첫 문장은 하나의 INTEGER
  `:=` 초기화. IR/JoI 변수 이름은 달라도 된다. 이름으로 동등성을 가정하지 않는다.
- 출력 및 지역 변수: INTEGER 리터럴·복사·덧셈·뺄셈, 명시적 정수→문자열 변환.
  구조적으로 같은 표현은 인증할 수 있다. 임의 대수적 동치 변형을 시도하지 않는다.
- 조건: 정수 식 비교와 bool 조합, 직접 외부 읽기와 리터럴 비교. 외부 값은 guard에만
  사용한다. 실제 catalog의 양쪽 공동 분할 전체 곱집합을 검사한다.
- 시간: 고정 delay, period, wait. 기존 IR wait의 edge·지속·timeout 레지스터를 모두
  유지한다. 이것이 임의 wait 조합에서 closure를 보장한다는 뜻은 아니다.
- 미지원: clock 읽기, GV, query/read 대입, 관계 변수 float 연산, modulo, 동적 시간,
  관계 문자열 조건, 복잡한 살아 있는 과거 snapshot 관계, 임의 loop.
- 서비스의 ACTION 인자 type/domain은 계속 검사한다. 무제한 정수의 문자열 출력은
  제한 없는 STRING에만 허용한다. raw INTEGER를 STRING 인자로 자동 인정하지 않는다.

구조 조건이 실패하면 REFUSED, 탐색 중 관계 의무·미지원 기호 연산·자원 상한은
UNKNOWN/INCONCLUSIVE다. gate는 이를 REFUSED로 접는다. 이 결과를 ACTION 불일치로
해석하면 안 된다. 새 경로는 자동 bounded fallback을 실행하지 않는다.
최초 구체 반응에서 실제 ACTION이 다르면 구체 반례를 만들고, gate에서 재생한다.
추상 반응의 실패에는 DIVERGE를 붙이지 않는다.

## 2. 핵심 예와 상태 의미

```text
IR: cycle(count=n, period=1초) { Speaker("count: " + n) }
    END_ITER에서 n += 1
JoI: k := 0; Speaker("count: " + k); k = k + 1
     완료 후 1초 대기
```

초기화와 첫 반응은 실제 0에서 실행한다. 이후 노드는 `n=k=N`이라는 관계를 가지며
N은 임의의 수학적 정수다. 두 출력은 `Text("count: ", IntToText(N))`, 두 갱신은
`N+1`이다. 양쪽 출력·갱신 순서·갱신 후 값의 일치를 확인한 뒤 다음 노드의 카운터를
새 임의 정수로 일반화한다. N+1을 비교하기 전에 N으로 바꾸지 않는다.

단순 예는 시간 H 없이 10개 상태로 닫힌다. 이는 입력 격자 100ms와 period 1000ms의
타이머 상태를 포함한 수치다. 150ms delay를 붙인 기대 출력은 150, 1300, 2450ms다.

`N>=3` 등의 조건은 반응 안에서 같은 typed 식에 같은 진리값을 주고, 참/거짓을 모두
전개한다. 반응이 끝나면 조건 제약은 잊는다. 도달 불가능한 값이나 분기를 더 포함하는
과대 근사이므로 인증이 더 어려워질 수 있지만, 실제 실행을 빠뜨리는 근거로 쓰지 않는다.
1,000회 이후에만 틀리는 코드는 3.2초 동안 출력이 같아도 무제한 인증을 받지 못한다.

## 3. 보장 명제

아래 명제는 정의한 실행 모델과 해당 구현의 적합성을 전제로 한 수작업 정확성 논증이다.
Python 구현 전체의 기계 검증이나 실제 플랫폼 전반에 대한 인증을 뜻하지 않는다.

> 구조·입력·서비스 적합성 검사를 통과한 IR/JoI 쌍에 대해 relational-state-v1이
> 모든 초기/전이 의무를 완료하고 닫힌 유한 관계 그래프로 EQUIV-FIXPOINT를 반환하면,
> 선언한 고정 바인딩·서비스 입력 도메인·100ms 입력 이력·정확한 1ms deadline·
> completion-relative period 모델에서 모든 허용 입력 이력에 대한 두 ACTION trace는
> 시간 상한 없이 같다. 각 입력 이력에서 실제 프로그램 초기화를 따른다.

이는 모든 임의 지역 변수 초기값을 넣는다는 뜻이 아니다. 초기 환경은 허용 도메인
전체이며 지역 변수는 각 프로그램의 실제 초기화로 정해진다. 지원하지 않는 프로그램은
명제의 인증 대상에 포함하지 않는다. H가 있는 기존 결과는 이 명제로 승격하지 않는다.

## 4. 증명 의무와 구현 연결

| 의무 | 근거와 실제 처리 |
| --- | --- |
| 초기 포함 | 각 입력 조합에서 빈 지역 저장소로 두 실행기를 실행한다. 선택 카운터의 초기화·갱신 관찰, ACTION, 갱신 후 정수 값이 같아야 관계를 도입한다. `relational.py:expand/normalize` |
| 기호 연산 적합성 | `PairInt`의 +/−는 INTEGER AST, `RelText`는 리터럴과 IntToText다. AST 구조 일치는 모든 정수 대입에 대해 같은 연산 결과를 뜻한다. Python 기본 객체 equality는 증명 비교에 쓰지 않는다. `relational_values.py`, `state_key.py` |
| 전이 보존 | 같은 관계/환경에서 기존 IrRunner/PauseRunner를 실행한다. 선택 카운터의 초기화·갱신과 ACTION 사이 순서를 비교하고 post 값도 비교한다. 내부 증명 관찰은 제품 ACTION에 추가되지 않는다. `interp.py`, `ir_step.py`, `relational.py` |
| 분기 포괄 | NeedBranch가 발생한 정수 조건의 양쪽 진리값을 재실행한다. 한 반응에서 같은 식의 선택을 공유한다. 모든 완료 분기 의무를 검사한다. 조건 간 상관을 잊는 것은 과대 근사다. |
| 입력 포괄 | 사용 위치 검사로 외부 값의 용도를 직접 guard로 한정한다. 기존 catalog-backed 공동 분할에서 guard 진리값이 일정하다는 논증을 재사용하고 전 곱집합을 실행한다. 원값 ACTION 전달을 대표값으로 인증하지 않는다. `relational_analysis.py`, `input_coverage.py`, `service_model.py` |
| 일반화 포함 | 동일한 post 정수 쌍을 임의 정수로 바꾸면 후속 구체 쌍을 포함한다. 다른 값은 보존한다. 현재 값과 같은 기호 복사는 같이 바꿀 수 있지만 과거 snapshot을 현재 기호로 바꾸지 않는다. 지원 밖 live 관계는 거절한다. |
| 죽은 값 제거 | period 완료 경계에서만 다음 회차의 모든 경로에서 읽히기 전 덮어쓰는 지역 값을 지운다. may-read-before-overwrite의 유한 집합 고정점을 계산하며 :=는 다음 회차의 overwrite로 간주하지 않는다. 멈춘 continuation에서는 이 제거를 적용하지 않는다. `entry_live` |
| 시간 포괄 | `next_time`이 다음 입력 격자와 양쪽 정확한 만료 중 최솟값을 선택한다. 동률에는 새 입력을 먼저 적용한다. clock 비사용 시 내부 타이머의 정확한 age와 입력 격자 위상을 키에 보존한다. 외부 입력은 만료만 있는 사건에서 유지한다. |
| ACTION 관찰 | 기존 D1의 호출 순서, 대상, 인자, 중복을 보존한다. 동일 fanout의 독립 대상만 교환 가능하다. 갱신 관찰 비교도 이 정규화를 따른다. `observation.py` |
| 폐쇄 | 상태마다 모든 입력/분기를 전개하고 후속 키를 큐에 넣는다. 모든 의무 완료 후 큐가 비어야 EQUIV/closed/complete를 함께 설정한다. cap은 UNKNOWN. `ProductResult.claim`도 미폐쇄 성공을 FIXPOINT로 표시하지 않는다. |

초기 포함과 전이 보존을 유한 길이 입력 prefix에 귀납 적용하면 모든 prefix의 timed
ACTION trace가 같다. 각 유한 시간 prefix가 같으므로 무한 실행의 trace도 같다.
이 결론의 핵심은 대표 카운터 숫자를 몇 개 시험하는 것이 아니라, 임의 정수 관계에서
각 전이가 보존됨을 확인하는 것이다. 종료 표시 자체는 ACTION이 아니며 미래 ACTION은
흡수적 종료 실행기에 의해 처리한다.

## 5. 공용 실행기 수정

`compile_ir`은 ACTION/query 인자에서 읽히는 카운터의 증가를 제거하거나 modulo로
접지 않는다. 템플릿·식 내부·뒤따르는 사용도 전체 명령에서 확인한다. 출력만 쓰던
카운터가 0,0,0이 되던 오류는 0,1,2로 수정했다. 기존 D7 거절은 유지한다.

수학적 INTEGER의 문자열 변환에 Python의 기본 4,300자리 제한을 숨은 전제로 쓰지
않도록 `integer_text.value_text`를 추가했다. 9자리 이하 조각으로 변환하여 유한한
모든 정수에 대해 같은 십진 문자열을 정의한다. 전역 Python 설정은 바꾸지 않는다.
실제 메모리/시간 고갈을 인증으로 처리하지 않으며 JoI 구현이 이 INTEGER 모델을
따르는 것은 실행 모델 적합성의 전제다.

## 6. 검증 및 평가 근거

- [251개 회귀](../../eval/results/relational_validation_2026-09-08_v1.json): 기존223+신규28.
- [개발20사례](../../eval/results/relational_development_2026-09-08_v1.json): 무제한 인증6,
  구체 반례 재생3, 보수적 미완료8, 구조 거절3. 사전 지정 기대 판정과 모두 일치.
- [손으로 계산한 trace](../../eval/fixtures/relational_expected_traces.json): 0,1,2 출력,
  150ms delay와 완료 상대 period, modulo 조건 아래 원값 출력. 신규 회귀는 재진입,
  두 센서 전 조합, snapshot, 초기화/갱신/문자열/순서/1,000회 오류도 확인한다.
- [기존 E1](../../eval/results/e1_internal_semantics_relational_2026-09-08_v1.json): 11프로그램,
  563입력 이력, IR 별도1이력, 실행기 변이2검출, 실패0. E1 기준 실행기는 관계
  INTEGER 자체의 독립 증명 oracle이 아니며 검사 범위를 과장하지 않는다.
- [전체 후보 무제한 시도](../../eval/results/relational_corpus_2026-09-08_v1/summary.json):
  같은388건 전부 포함. 구조/준비 거절327, 기존 생성 실패59, 준비 오류2.
  새 경로의 진입 구조를 만족하는 쌍은0이며 신규 corpus 무제한 인증은0이다.
  이는 IR/code가 모두 다르다는 결과가 아니라 새 경로의 좁은 적용 범위다.
- 기존 3.2초 평가 재검증은 별도 결과 `contract_recheck_v4_2026-09-08_v4`에 기록한다.
  후보를 새로 생성하거나 과거 bounded 인증을 무제한 수치에 포함하지 않는다.

동결 protocol/manifest/source archive와 결과 SHA를 남긴다. 소스 연속성은 물리적
격리나 독립 증명 감사가 아니다. 개발 fixture와 익숙한 corpus의 재평가를 held-out
평가로 부르지 않는다. 다음 논문 작업은 이 명제·증명 의무·실제 적용 범위를 기존
bounded/SMT 근거와 분리해 연결하는 것이다.
