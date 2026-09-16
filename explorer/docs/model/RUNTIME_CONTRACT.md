# JoI 목표 런타임 계약과 E1

**최신 범위 정정:** 사용자는 확정한 의미론에서 IR와 JoI 코드의 ACTION trace
동치만을 검증 대상으로 확정했다. 이 파일은 그 **규범적 실행 의미론**이며 실제
배포 런타임 측정은 필수 완료 조건이 아니다. 내부 실행기의 의미 보존·입력
포괄성·탐색 보장이 필수다. 최신 내부 검사와 논증 연결은
[INTERNAL_SEMANTICS.md](../proof/INTERNAL_SEMANTICS.md)를 따른다. 아래 배포 로그 수집은
실제 플랫폼 동작까지 보장을 확장할 때의 선택적 후속 작업이다.

2026-09-07, `runtime-contract-v1`. 사용자는 실제 런타임의 모호한 정책을
검증에 유리하고 효율적인 방향으로 정하고, 필요하면 JoI 구현을 이 계약에
맞춰 수정할 수 있다고 지시했다. 아래는 그 권한에 따라 정한 **목표 명세**다.
현재 운영 서버에서 이미 확인한 사실이 아니다. 기존 시간·관찰·고정 binding
합의와 [서비스 모델](SERVICE_MODEL.md)을 유지한다.

## 1. 확정한 실행 규칙

| ID | 목표 규칙 | Explorer 및 구현 이유 |
| --- | --- | --- |
| R1 | 한 시나리오 인스턴스의 코드와 binding/inventory는 실행 중 고정한다. 단수 selector는 시작 전 정한 하나의 구체 ID를 계속 사용한다. | 실행 중 선택의 비결정성을 상태에 추가하지 않는다. 현재 검증은 주어진 binding 하나에 대한 것이며 다른 무작위 선택까지 검증했다는 뜻이 아니다. |
| R2 | 외부 입력은 100ms 경계마다 하나의 snapshot으로 반영한다. 같은 경계의 변경은 원자적으로 적용하고 경계 사이에는 유지한다. | 기존 입력 역사 전수조사 계약. 센서끼리 독립적인 모든 허용 조합을 포함하며 초기 센서 상태도 전수조사한다. |
| R3 | timer는 정수 1ms 논리 시각을 사용한다. delay는 도달한 시각부터 재고 만료 시각에 다음 문장으로 재개한다. 0ms는 즉시 계속한다. | 150ms를 200ms로 올림하지 않는다. 외부 입력 100ms와 별개의 정밀도다. |
| R4 | wait는 해당 실행 위치를 보존한다. 조건이 참이면 그 다음 줄부터 계속한다. 대기 중 앞의 ACTION이나 바깥 if 조건을 다시 실행하지 않는다. | 중첩 blocking에도 같은 규칙을 적용한다. |
| R5 | period는 **본문 회차가 완료된 시각부터** 센다. 대기·delay 중 다음 회차를 시작하거나 겹쳐 실행하지 않는다. | 150ms 본문 + 1000ms period이면 시작은 0, 1150, 2300ms다. 겹치는 인스턴스 상태가 필요 없다. |
| R6 | 동일 논리 시각에는 새 입력 snapshot을 먼저 반영하고 timer/wait를 처리한다. sustain 만료와 조건 해제가 겹치면 해제가 우선한다. | 새 입력을 이용해 같은 상태에서 유일한 전이를 계산한다. |
| R7 | rising edge의 첫 관찰이 true이면 한 번 발화한다. 래치는 회차 사이에 유지하고 wait/생성된 edge 코드가 실행되어 관찰할 때만 갱신한다. | delay나 period 휴지 중 잠깐 false였다 돌아온 값까지 별도 edge 이력으로 저장하지 않는다. |
| R8 | `:=`는 **초기 회차 전용 대입**이다. 첫 회차에서 그 문장에 도달하면 당시 값으로 RHS를 평가하고, 이후 회차에서는 건너뛴다. `=`는 도달할 때마다 평가한다. | 현재 실행기의 first-iteration 비트 하나로 표현한다. 선언마다 별도 초기화 상태를 추가하지 않는다. 자세한 경계는 아래 참조. |
| R9 | 검토된 읽기 함수는 `(device, member, typed arguments)`에 대응하는 현재 snapshot 값을 읽는다. 같은 key의 반복 호출은 같은 snapshot에서 같은 값이며, 다른 인자는 별도 key다. | 네트워크 요청·응답 대기·호출별 새 반환을 프로그램 전이로 추가하지 않는다. 반환값은 여전히 STRING/BOOL 등 기존 서비스 타입이다. |
| R10 | **BOOL/BOOLEAN 센서·조회 반환 입력은 항상 true/false다.** BOOL 결측은 허용 입력이 아니며 임의로 false로 바꾸지 않는다. 다른 타입은 읽기 값이 없으면 snapshot에 `None`을 허용한다. | 사용자 후속 확정 `strict-two-valued-v1`. adapter는 첫 입력부터 유효한 BOOL을 제공해야 한다. BOOL 누락/None/숫자0·1은 계약 밖으로 거절한다. 비BOOL 결측 및 API 인자 검사는 유지한다. |
| R11 | DOUBLE 외부 입력은 0.1 격자의 값만 adapter가 제공한다. 센서/property/조회 반환은 서비스 명세의 타입·범위를 따른다. | 임의의 연속 실수를 verifier가 조용히 반올림하는 것이 아니다. 장치가 더 정밀하면 adapter에서 격자 변환 정책을 별도 구현하고 기록해야 한다. ACTION 인자와 비교 임계값을 반올림하지 않는다. |
| R12 | ACTION은 기기 명령의 **논리적 발행**이다. 같은 호출의 독립 기기 fanout 순서는 무시하고 호출 경계·기기별 순서·인자·중복을 보존한다. 명시 순차 호출은 구분한다. | 기기의 물리 동작 완료나 네트워크 ACK까지 기다리는 시간이 아니다. 반환 대입이 있는 제어 함수는 ACTION+return 지원 전까지 REFUSED다. |
| R13 | one-shot 종료와 최상위 break는 해당 인스턴스를 영구 종료한다. 종료 자체는 ACTION이 아니다. | 이후 입력으로 되살아나지 않는다. cron 재시작/복수 시나리오의 상호작용은 이 테스트 묶음의 범위가 아니다. |
| R14 | **한 번도 대입된 적 없는 변수를 산술 연산(`+ - * / %`)의 피연산자로 쓰면 runtime error다.** 인스턴스는 그 지점에서 멈추고 다시 실행되지 않으며, 그 전에 낸 ACTION은 남는다. R13의 정상 종료와 달리 **오류 자체가 관찰 대상 사건**이다: 한쪽만 오류로 끝나면 두 실행의 관찰 결과는 다르다. | 값이 없는 칸을 조용히 0으로 때우면 생성된 코드의 초기화 누락이 동치 판정에서 사라진다. 범위는 변수뿐이다. `+`의 한쪽이 STRING이면 S8의 이어붙이기이지 산술이 아니고, R10이 허용하는 비BOOL 결측 입력 읽기(None)는 이 규칙과 무관하며 종전대로다. 사용자 확정 2026-09-16, `uninitialized-arith-v1`. |

### `:=` 경계의 명시적 결정

기존 설명의 “시작할 때 한 번”을 모든 위치의 선언을 시작 시점에 미리 평가하는
hoisting으로 해석하지 않는다. 첫 **논리 회차**는 delay/wait가 있어도 완료될 때까지
이어진다. 따라서 `delay(150 MSEC); x := sensor`는 150ms에 sensor를 읽는다.
첫 회차에서 false였던 가지의 `:=`는 실행되지 않았으므로 그 변수를 초기화하지
않으며, 다음 회차에 그 가지가 true여도 `:=`는 건너뛴다. 다른 대입이 없으면
읽기는 현 모델의 미정의 값(None)이다. 그 값을 산술에 쓰면 R14의 runtime error다.
초기 회차의 loop에서 같은 `:=`를 여러 번
지나면 매번 대입한다. 일반적인 최상위 flag 선언은 최초 한 번만 실행된다.

이는 `first encounter once per declaration`과 다른 정책이다. 기존 문서의
first-tick 설명 및 현 코드와 맞추고 초기화 이력에 따른 상태 조합 증가를 피하기
위해 이 정책을 선택했다. 새로운 flag 초기화는 첫 대기보다 앞의 최상위에
배치하면 가장 명료하다. 파서/생성기에 없는 문법을 새로 추가하는 결정은 아니다.

### 조회 함수 adapter의 구현 요구

서비스 함수 이름과 반환 타입은 바꾸지 않는다. `query`는 런타임의 새 서비스
종류가 아니라 검증 모델의 읽기 역할이다. 7개 검토 함수 목록은 SERVICE_MODEL.md에
있다. 구현은 필요한 고정 인자 key의 값을 비동기로 갱신할 수 있지만 **스크립트의
읽기는 현재 snapshot을 즉시 반환**해야 한다. 새 응답은 다음 허용 입력 경계에
반영한다. 아직 값이 없는 **비BOOL** key는 None으로 시작할 수 있다. BOOL 반환
key는 처음부터 true/false여야 한다. 호출할 때마다 외부
요청을 보내고 그 응답까지 스크립트를 정지시키는 구현은 R9와 다르므로 수정 대상이다.

adapter는 조회 결과의 타입/범위를 지키고 검토된 읽기가 관찰 대상 기기를
제어하지 않도록 해야 한다. 부작용을 갖는 함수의 반환을 단순 입력으로 숨기지 않는다.
이 캐시/snapshot 정책은 **목표 구현 요구**이며 현재 서버에서 관측한 성질이 아니다.

### R14 미초기화 변수 산술

가지 안에서만 초기화되는 변수를 바깥에서 쓰는 코드(`if (...) { n := 0 ... } ... n = n + 1`)는
LLM 생성물에서 실제로 나온다. 첫 회차에 그 가지를 지나지 않으면 `n`은 값이 없고, 그 상태의
`n + 1`을 어떻게 처리할지는 그동안 어느 문서에도 없었다. 0으로 때우는 쪽과 오류로 보는 쪽 중
**오류**를 택한다. 0으로 때우면 초기화 누락이 Timeline IR과 같은 ACTION 열을 내면서 사라지는데,
그건 검증이 잡아야 할 결함이기 때문이다. Timeline IR 실행 의미(`PerCom/3_Timeline_IR/HANDOFF.md`
"null 산술은 0 으로 강제")는 바꾸지 않는다. 두 쪽이 다르게 정한 것이 아니라, IR은 확정된 명세이고
JoI는 그 명세를 구현했다고 주장하는 코드다. 그래서 이런 코드는 두 실행의 차이(DIVERGE)로 나타난다.

범위를 변수로 좁힌 이유: 값이 없는 비BOOL 입력(R10)은 계약이 허용하는 정상 입력이므로 그 읽기까지
오류로 만들면 멀쩡한 시나리오가 오류가 된다.

구현: Explorer는 `explorer/runtime/interp.py`(`_uninitialized`, `error_action`), 독립 참조 실행기는
`PerCom/6_Evaluation/E2_fidelity/reference/joi_ref.py`(`JoiProgram.check_assigned`)에 있다. 양쪽 다
산술 노드에서만 검사하고, 한 번이라도 대입된 변수는(그 값이 None이어도) 검사하지 않는다.

## 2. 현재 확보한 근거

| 자료 | 확인한 것 | 확인하지 못하는 것 |
| --- | --- | --- |
| `docs/JOI_SPEC.md` 및 `files/joi_*.md` | period/delay/wait/first-tick 초기화의 로컬 설명과 생성 예제 | 실제 배포 scheduler 동작. period 기준·non-blocking의 의미가 충분히 구체적이지 않다. |
| `lowering/parser/JOILang.g4` 및 generated parser | 로컬 문법 검사. 이 묶음의 15개 script가 문법을 통과한다. | 시간 전이와 함수 반환 의미 |
| `files/service_list_ver2.0.7.json` | 서비스 타입, 인자 범위, Forecast의 STRING 반환 | 응답 지연·호출별 값 변경·오류 정책 |
| `sensys/simulators/joi_simulator.py` | periodic wait의 false가 `_AbortTick`으로 회차 나머지를 버리는 연구용 구현 | R4의 정답 oracle. 실제 서버라는 근거도 없다. |
| `../joi-agent/mcp_server/tools.py` | hub-controller의 scenario API 및 직접 서비스 호출 클라이언트 | 허브 안의 scheduler, DSL 반환 대입의 blocking 여부 |
| `../mysmax/execution/mock.py` | 명시적 simulated/mock 실행 | 실제 JoI 실행기 |

조사 범위는 현재 `joi` 및 인접 `joi-agent`, `joi-llm-lab`, `mysmax`, `mysmax_copy`
소스와 로컬 Documents/Downloads/Desktop의 파일 목록이다. 이 범위에서 실제 허브
스케줄러 구현/명령별 실행 trace를 찾지 못했다. 실제 장치 실행은 0회다.
이는 현재 E1 **명세 확정**을 막는 사유가 아니며, 배포 적합성 측정의 남은 의무다.

추가 문법 차이: Explorer는 `delay(1.5 SEC)`를 해석하지만 로컬 ANTLR 문법은
INTEGER duration만 허용한다. 같은 시간을 `delay(1500 MSEC)`로 표현하면 된다.
이번 probe는 모두 정수 MSEC/SEC 문법을 사용한다. 분수 단위를 배포 소스로 사용할
경우 생성 단계에서 정수 MSEC로 정규화하거나 runtime parser를 맞춰야 한다.
문법 파일을 scheduler 근거로 승격하거나 이 차이를 이미 수정했다고 기록하지 않는다.

## 3. E1 개발 검사와 완료 경계

재현 명령(결과 파일은 새 경로를 사용):

```bash
python -m explorer.tests.e1_runtime_probe --output /tmp/joi-e1-new.json
```

`tests/e1_runtime_probe.py`의 예상 trace는 위 규칙에서 손으로 계산했다.
catalog-backed JoI 실행기만 매 1ms 재생하고, 입력은 지정된 100ms 경계에 먼저
반영한다. BFS, deadline jump, IR와의 동치 비교를 예상 정답으로 쓰지 않는다.
단, 실제 실행기를 독립 구현한 것은 아니며 Explorer의 code runner 자체를 검사한다.

- 시간·분기·초기화·읽기 반환 **14개 예상 ACTION trace**.
- 반환값을 받는 Toggle의 **기대 REFUSED 1개**. 이것은 실행 trace 통과가 아니다.
- 지연 변경, wait를 if로 변경, `:=`를 `=`로 변경한 **프로그램 변이 대조군 3개**.
  문법 오류/예외만 생긴 변이는 검출 성공으로 세지 않는다.
- target ID, 서비스, 함수, 인자, 시각, 순서와 중복을 기록한다. 이 묶음은 단수
  selector만 쓰며 fanout 검증은 기존 contract 회귀에 별도로 있다.
- 결과에 script/입력 이력/예상·관측 trace, 검사 코드 hash, evaluator/catalog hash,
  읽은 근거 파일 hash를 남긴다. `actual_runtime_runs: 0`, `e1_complete: false`다.

최신 결과: `eval/results/e1_target_runtime_2026-09-07_v1.json`.

E1 전체 완료에는 이 고정된 명세에 대한 더 넓은 구성·경계 검사, 실행기 자체에
오류를 주입한 대조군 및 독립 의미론 oracle 근거가 필요하다. 이 15개 개발 사례가
일반 정리나 실제 서버 전체 적합성을 증명하지 않는다. 검색/입력의 조건부 정리는
각각 SEARCH_CORRECTNESS.md와 INPUT_COVERAGE.md의 별도 근거다.

## 4. 선택적 배포 보장 확장 — 실제 런타임 수정·대조

1. R1–R13을 실행기/adapter의 acceptance contract로 전달하고 소스 버전을 고정한다.
2. probe의 가상 입력 기기·출력 기록 기기를 연결해 동일 입력 이력을 주입한다.
   real device의 물리 상태 변화 시각 대신 **명령 발행**을 관찰한다.
3. 로그에 인스턴스 ID, 코드/binding hash, 논리 시각, 입력 snapshot revision,
   회차 시작/종료, pause/resume, ACTION target/method/typed args, 읽기 key/value,
   요청/응답과 캐시 반영 시각을 기록한다. 조용한 구간도 horizon까지 수집했는지 남긴다.
4. 지연된 응답·같은 key의 연속 다른 응답·결측을 주입해 R9/R10을 확인한다.
   cache 내부 갱신은 프로그램 읽기 시각/값과 구분한다. 100ms 입력 경계와 timer가
   겹치는 검사는 같은 snapshot revision 및 scheduler 순서를 확인한다.
5. OS/통신 지연으로 측정한 wall-clock 시각을 논리 시각과 혼동하지 않는다.
   물리적 시간 오차까지 주장하려면 별도의 오차 계약과 측정이 필요하다. 허용 오차를
   결과를 본 뒤 임의로 늘려 통과시키지 않는다.

현재 논문 보장의 연결은 **정의한 의미론 → 내부 실행기의 의미 보존 → 입력·탐색
정리**다. 배포 플랫폼의 측정/구현 적합성은 이 명제와 별개다. 기존 결과의
`e1_complete=false`는 당시 전체 E1 계획의 미완료 기록이며, 배포 측정이 현재
모델 검증의 선행 조건이라는 뜻으로 읽지 않는다. 초록은 변경하지 않는다.
