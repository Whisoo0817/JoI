# Catalog 범위로 불가능한 시간 비교 판별 — 2026-09-08

사용자 승인: 서비스 명세에 Hour를 0~23 정수로 선언하고 Explorer가 그 선언을 사용한다.
정확한 구조화 필드는 기존 catalog 스키마의 `type: INTEGER`, `bound: [0, 23]`이다.
새로운 minimum/maximum 스키마를 병행하지 않는다.

## 변경과 범위

- `files/service_list_ver2.0.7.json`: Hour 0~24 → 0~23, Minute/Second 0~60 → 0~59.
  설명문도 양 끝 포함, 자정 Hour=0, leap-second 값 없음으로 명시했다.
  함수 인자인 Clock.Delay의 Hour/Minute/Second 범위는 바꾸지 않았다.
- `ServiceModel.clock_integer_range`: 준비된 catalog snapshot에서 INTEGER bound를 읽는다.
  실제 구현된 hour/minute 읽기의 비-null 정수 성질과 modulo 범위가 선언에 포함되는지도
  검사한다. 그 검사는 최적화의 전제 확인이며, 실제 비교에 사용하는 범위는 catalog에서 온다.
  예를 들어 사용자 catalog가 Hour 0~24이면 이 처리는 >=24를 거짓으로 증명하지 못한다.
- IR `clock.time`은 기존 의미대로 `hour*100+minute`이다. 선언된 두 범위에서
  `[hour_lo*100+minute_lo, hour_hi*100+minute_hi] = [0,2359]`를 도출한다.
  catalog의 **STRING Clock.Time 속성**을 INTEGER로 바꾸거나 같은 값으로 가정하지 않는다.
- `range_analysis.py`: 두 AST의 정수 비교에 같은 interval 판별식을 사용한다. `<, <=, >, >=`
  는 구간의 순서로, `==, !=`는 구간 분리 또는 동일 singleton일 때만 결론낸다.
  nullable 값, 실수/불리언 리터럴, 저장된 변수, 일반 산술식, 함수 호출에는 이 증명을
  적용하지 않는다. 일반 센서의 입력 분할/SMT 지원 범위를 이 작업으로 확대하지 않는다.
- `timed.reads_clock(..., catalog_ranges=True)`: 증명된 상수 비교 안의 읽기는 시간 의존성에서
  제외한다. **원래 IR/JoI AST와 실제 실행은 그대로**다. false 조건을 true로 바꾸거나
  delay/ACTION/변수/분기를 삭제하지 않는다. 결과 notes에 `catalog-range-v1` 적용을 남긴다.
  기본 reads_clock 호출 및 반례 replay는 보수적 분석을 유지한다.
- 정확히 알려진 TerminalRunner/DoneLatch/CatalogRunner와 IrRunner/OneShotRunner/PauseRunner에만
  이 새 분석을 적용한다. 알 수 없는 래퍼/하위 클래스는 추가 범위 증명을 얻지 못한다.

catalog 새 SHA256: `fe25ecbf5a9028b46232ce156072654217f23997e5b4f974368fa448fcffd1a4`.
이전 SHA256: `e69e5e442441197ff7d8eece70ad59fe966d82469fb07fc9dfc57c2446c4df9c`.
read-role review hash도 새 값으로 갱신한다. 모든 서비스 함수 명세와 그 설명문은 이전
동결 ZIP과 비교해 동일함을 확인한다. hash 검사를 제거하거나 임의 catalog를 승인하지 않는다.

## 충분조건과 수작업 증명 근거

1. `clock_state`는 hour를 `%24`, minute를 `%60`으로 만든다. 모든 정수 논리 시각에서
   각각 0~23, 0~59의 정수이고 null이 아니다. 외부 입력으로 derived clock을 덮어쓰는 것은
   `validate_domains`가 거절한다. 선언이 이 구현 범위를 포함하지 않으면 증명하지 않는다.
2. 읽기 구간이 `[l,u]`, 리터럴이 `c`이면 `u<c`일 때 모든 읽기에서 `<c`는 참이고,
   `l>=c`일 때는 거짓이다. 다른 부등식도 대칭이다. 같음 비교는 양 끝에서 같다는 이유로
   상수화하지 않는다. `hour==12`는 계속 시간 의존적이다.
3. 제거되는 의존성은 부작용 없는 직접 읽기로만 구성된 **비교식 전체의 결과**에 대한 것이다.
   비교식이 모든 허용 읽기에서 같은 bool이므로, 시각 이동으로 바뀌는 내부 피연산자가
   ACTION, 저장 값, 분기 결과에 노출되지 않는다. 원래 실행기가 비교를 계속 평가한다.
4. 프로그램의 모든 clock 읽기가 이러한 비교 안에 있고 나머지 AST에는 clock 읽기가 없을
   때만 기존 clock-free 시간 이동 관계를 적용한다. 실행 위치, 사용자 저장소, 입력 위상,
   정확한 내부 타이머 상대값과 각 전이를 보존한 그래프 폐쇄가 여전히 필요하다.
   카운터 관계/일반 clock 주기 추상화/샘플 반복 관찰로 무제한 인증하는 새 규칙은 없다.
5. H를 명시하면 bounded 결과를 유지한다. 자원 상한은 미완료이며 positive로 승격하지 않는다.

이는 구현에 대응시킨 수학적 논증이다. regression 통과나 corpus 결과 자체를 증명으로
대체하지 않으며 전체 Python 구현/실제 서버가 기계 검증됐다고 주장하지 않는다.

## 원문 오류와 검증 대상의 구별

C15_005/C18_003의 IR은 `clock.time>=2400`, 생성 코드는 `clock_hour>=24`를 종료 조건으로
쓴다. 둘 다 항상 거짓이다. 따라서 현재 쌍은 자정 이후에도 같은 주기로 계속 행동한다.
그 동등성을 인증할 수 있지만 “자정에 종료한다”는 자연어 의도가 맞게 구현됐다는 인증은
아니다. 이 reference 조건은 데이터 품질 이슈로 기록한다. 기존 dataset/IR/candidate bytes를
수정해서 결과를 맞추거나, 두 건을 평가 분모에서 제외하지 않는다.
의도 교정을 한다면 자정 경계를 실제로 검출하도록 reference를 별도로 고친 후 평가해야 한다.

## 검증과 평가 절차

기존 274개와 신규 15개 regression을 모두 실행한다. 신규 검사는 전수 작은 정수 구간으로
비교식 충분조건을 대조하고, 경계/자정 실제 ACTION 반례 재생, catalog 변경 시 proof 거절,
원래 프로그램 보존, saved time/unknown wrapper/H/cap 보존을 검사한다.

후속 전체 평가는 기존 v2와 같은 388개 후보, H=None, 입력 100ms/만료 1ms, 같은 자원 상한을
사용한다. 변경은 catalog 세 필드의 선언과 이 분석이며 LLM 호출은 없다. 모든 결과를 새
프로토콜/manifest/source ZIP에 남기고 이전 실행을 보존한다. 두 실패를 본 뒤 만든 개선과
익숙한 후보의 재평가이므로 exploratory follow-up이며 독립 held-out 증거가 아니다.
최종 결과는 별도 `catalog_ranges_corpus_2026-09-08_v1/report.md`에 기록한다.
