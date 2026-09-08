# fresh-v4 준비 거절 46건 분류 (2026-09-07)

이 문서는 기존 평가의 **준비 REFUSED 46건만** 사후 진단한다. 생성 실패59,
파싱 오류2, BFS 미완료1, 반례77은 이 분모에 포함하지 않는다. 원시 평가·후보·
정답 데이터·서비스 명세·production Explorer는 변경하지 않았다.

| 주된 원인 | 건수 | 의미와 조치 |
|---|---:|---|
| 생성 코드 측 계약/대상 불일치 | 23 | 서비스·인자·selector 사용 문제. Explorer를 느슨하게 해서 받을 대상이 아님 |
| 정답 IR와 현재 카탈로그 불일치 | 6 | 정답/명세 출처를 점검할 평가 데이터 문제 |
| 합의된 미지원 기능 | 14 | 현 거절 정책 유지. formal 보장을 위해 전부 지원할 필요 없음 |
| 입력 도메인 모델 한계 | 2 | 큰 유한 값 영역 또는 일반 문자열을 ACTION으로 전달하는 사례 |
| frontend 확장 후보 | 1 | BOOL `any` 맨 조건 읽기 정규화 후보. 원본은 여전히 REFUSED |
| 합계 | 46 | 각 사례는 주된 원인에 한 번만 집계 |

거절 사유는 첫 차단 지점이므로 한 행에 추가 문제가 있을 수 있다. 예를 들어
VOID 반환 대입을 정리해도 산술 ACTION 인자가 남으면 D7에 의해 계속 거절된다.
23건도 실제 장치 실행으로 얻은 오류 정답 label이 아니라 **현재 선언한 계약과
gold binding에 대한 정적 불일치**다. 모든 JoI 집합 문법이 불법이라는 뜻은 아니다.

## 1. 생성 코드 측 23건

| 유형 | ID | 근거 |
|---|---|---|
| 선언되지 않은 서비스 사용, 9 | C06_001, C06_003, C06_005, C06_006, C12_010, C17_008, C20_004, C20_011, C20_016 | Temperature/HumiditySensor 기기에 AirQualitySensor 읽기, Plug 기기에 Charger.Power 등. 이름 태그와 service capability는 다름 |
| 잘못된 함수/enum, 2 | C01_023, C02_018 | IR CleaningMode(stop)를 코드 RunMode(stop)로 바꿈. stop은 전자에만 있음 |
| 한 값 위치의 다중 기기 읽기, 10 | C01_008, C01_010, C01_013, C01_016, C03_003, C03_007, C15_008, C17_002, C17_006, C21_005 | IR은 특정 한 기기의 scalar 값. 코드 all/any는 실제 두 기기를 선택해 대입/인자로 사용. 임의로 첫 값을 택할 수 없음 |
| 존재 양화사 any로 ACTION 호출, 2 | C03_008, C03_012 | `any(#Speaker).speaker_stop()`가 두 기기에 매칭. 현 계약에서 any는 조건용이며 ACTION 선택 실행 규칙이 없음 |

예: C06_001의 Bedroom_TempSensor는 `TemperatureSensor` capability만 선언되어
있는데 코드가 `AirQualitySensor.Temperature`를 읽는다. 카탈로그 검사를 끄는
것은 수리가 아니다. C21_005는 서로 다른 두 방의 IR 읽기를 같은 all 집합으로
두 번 읽어 binding까지 잃었으며 후속 ACTION 대상도 점검해야 한다.

## 2. 정답 IR·카탈로그 6건

| ID | 확인된 불일치 | 추가 주의 |
|---|---|---|
| C01_006 | VOID Television.SetChannel에 `var: Television.Channel` | 산술 인자도 D7 대상 |
| C01_017 | VOID Speaker.Speak에 `var: TodayMenu` | 반환 없는 호출에 대입 지정 |
| C14_001 | VOID Light.MoveToBrightness에 `var: Light` | 산술 인자·IR/code period 차이도 존재 |
| C14_005 | VOID Light.MoveToBrightness에 `var: Light` | 산술 인자·selector/service도 추가 점검 |
| C14_006 | VOID LevelControl.MoveToLevel에 `var: LevelControl.CurrentLevel` | 산술 인자도 D7 대상 |
| C03_002 | IsAvailable에 필수 ServiceName 인자 누락 | 코드도 누락; 두 기기 query 반환도 scalar 집계가 없음 |

이는 이번 새 Gemma가 생성한 `ir_gt`가 아니다. 기존 정답 IR을 주입했다.
따라서 생성 모델 오류로만 분류하면 안 된다. 현재 카탈로그의 IsAvailable은
설명상 service name인데 인자 타입은 BOOL로 되어 있어 **카탈로그 자체의 설계
정합성도 확인**해야 한다. 임의 인자 추가·VOID var 삭제·과거 gold 수정은 하지 않았다.

## 3. 의도적으로 유지할 미지원 14건

| 유형 | ID | 유지 이유 |
|---|---|---|
| 증가 counter의 modulo 조건, 8 | C13_001–C13_007, C14_003 | 현 유한성 인증 밖. modulo 전용 상태 추상화는 별도 증명 필요 |
| 미검토/효과 있는 함수의 반환 대입, 3 | C01_015, C01_019, C17_003 | GenerateImage/ChatWithAI/SetVolume. 단순 입력 읽기로 치환하면 ACTION/반환 의미를 잃을 수 있음 |
| 산술 관찰 인자, 1 | C14_002 | 기존 합의 D7 arith-arg/derived-guard |
| 여러 기기의 query 반환, 2 | C15_009, C15_010 | IR binding부터 MenuProvider 두 대. 한 scalar에 어떤 결과를 받을지 규칙이 없음 |

이 14건의 현재 거절은 Explorer의 잘못된 동등 판정이 아니다. C13의 modulo는
확장할 수 있는 연구 방향이지만 이번 분류가 지원 재개나 자동 수정 결정은 아니다.

## 4. 입력 모델 2건

- **C01_009**: TemperatureWeather DOUBLE 범위는 [-470,10000]. 0.1 격자만
  104,701개이고 결측/표현 구분도 추가된다. **유한하지만 크다.** 자동 exact
  domain 생성 한도를 넘어 거절됐다. 이후 조합 한도도 따로 고려해야 하므로
  작은 입력 subset을 만들어 통과시킨다고 전체 catalog 범위 검증이 되지는 않는다.
- **C01_018**: GetMenu의 일반 STRING 반환을 Speak로 그대로 전달한다.
  유한 문자열 목록이 명세에 없어 전체 열거가 불가능하다. 명시적 유한 모델은
  그 모델 범위만 보장하며, 일반 문자열 전체 보장은 symbolic 값/동일성 추론 등
  별도 설계와 증명을 요구한다. 선언 몇 개만 추가하면 일반 문제가 해결되는 것은 아니다.

둘 다 파서 버그나 잘못된 동등성 판정으로 분류하지 않는다. 기존 입력 정책을
유지하면서 비용/보장 범위를 설계할 TODO다. BFS 미완료 C01_014는 별도 사례다.

## 5. frontend 후보 1건

C18_006은 `not (any(#MotionSensor).motionSensor_motion)`을 사용한다.
Motion은 catalog BOOL이고, 현재 grounding은 `any(...).Motion == true`처럼
명시 비교가 있을 때만 여러 장치를 펼친다. 조건 문맥의 BOOL any를 정규화하는
확장은 검토 가치가 있다. BOOL 아닌 scalar 집합 읽기에 확대하면 안 된다.

진단용 **메모리 복사본**에만 `== true`를 넣어 준비/0ms 탐색을 수행했다.
준비는 통과했고 재생 확인 DIVERGE가 나왔다. 현재 IR의 `not Motion`에 all
binding을 적용하면 `not (A and B)`, 코드의 not-any는 `not (A or B)`다.
A=true/B=None이면 IR은 Lock을 내고 코드는 내지 않는다. 따라서 구문 지원이
생겨도 이 후보가 동등해진다는 뜻은 아니다. 원본 REFUSED와 과거 집계는 유지했다.

## 실제 후속 TODO

1. **정답/명세 6건의 불일치 출처 검토.** 평가 reference부터 신뢰할 수 있게
   정리할 변경안을 만들되, VOID var를 지워도 남는 D7 문제를 구분한다.
2. **BOOL any 조건 정규화 설계·검사.** 보완 후보는 1개 문법 유형이며
   nullable, not/and/or 문맥 및 명시 비교와의 대응을 확인해야 한다.
3. **입력 모델 2건의 지원 비용 판단.** 큰 유한 값은 열거 비용, 일반 STRING은
   보장 범위/상징적 처리 문제로 분리한다. 지금 근거 없이 입력 범위를 좁히지 않는다.
4. 생성 코드 측 23건은 생성 파이프라인 개선 항목으로 남기고, 미지원14건은
   합의한 경계를 유지한다. 이를 전부 Explorer 구현 작업으로 옮기지 않는다.

## 재현 근거

- [행별 JSON](results/contract_fresh_v4_refusal_triage_2026-09-07_v1.json):
  46개 원본 payload/hash/거절 단계, 주·부 원인, 카탈로그 facts, 복사본 probe.
- `python explorer/eval/triage_refusals.py --output <새 파일>`은 46개 first refusal
  문자열을 모두 재현하고, frozen 후보·manifest 및 참조 소스 hash를 검사한다.
  최초 실행은 relative `__file__` 처리로 산출물 전에 실패했고, 경로 수정 후 완료했다.
- 독립 실행기 증명이 아닌 사후 self-review다. 원시 실험을 재분류하거나
  unsupported를 false-positive/false-negative 수치로 바꾸지 않았다.
