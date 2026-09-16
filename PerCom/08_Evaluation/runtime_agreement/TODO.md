# 실기기 실험 TODO — 모델–런타임 일치 (2026-09-15, whisoo 방향 결정)

상태: **계획만. 실행·원고 반영 없음.** E1–E4 번호 밖의 보조 실험이다. 위치는 Evaluation 끝 또는 Implementation 끝의 작은 소절(표 1개 + 반 단 그림 1개 이하).

## 1. 무엇을 보여 주나

한 문장: **Explorer 가 믿는 실행 모델(JoI 의미 실행기)이 실제 JoI 런타임과 같은 시각에 같은 동작을 낸다.**

| 방향 | 실기기에서 보는 것 | 막는 반론 |
| --- | --- | --- |
| **DIVERGE → 실제 오차 재현 (중심)** | Explorer 반례 입력을 실기기에 주면 코드가 **실제로** 예측한 틀린 시각·틀린 동작을 내는가 | "DIVERGE 68 은 실행기가 만든 가짜 차이" (E3 의 반례 재생은 실행기 안의 재생이다) |
| **EQUIV → 예측 trace 일치 (짝)** | 같은 입력에서 실기기 동작이 Timeline 예측 trace 와 같은 시각에 나오는가 | "인증이 기대는 실행 모델이 현실과 다르다" (E3 원고의 *not independent evidence of real-device behavior* 를 좁힘) |

쓰지 않을 것:
- "배포한 자동화가 실제로 정확하다", deployment safety. 실기기 1회 실행은 입력 이력 하나라서 H 없는 인증의 증거가 아니다.
- SenSys 의 live-authored end-to-end / existence proof framing, NL→IR·사용자 확인 결과.
- 옛 게이트 판정(pass/repaired)과 옛 repair 루프 결과.

원고 문장 수준(초안, whisoo 확정 전): *On a commercial hub with physical devices, the observed action times of n programs matched the traces predicted by the Timeline reference at the logging resolution, and the counterexamples of m divergent programs reproduced the predicted mismatch.* 기록 방식(사람/플랫폼 로그), 해상도, 1회 실행임을 함께 적는다.

## 2. 사례 선정

### 공통 조건
1. **테스트베드에서 실현 가능한 서비스만.** SenSys 테스트베드(`sensys/evaluation/results/deployment/registration_package_live.json` devices): PresenceSensor, ContactSensor(문), AirQualitySensor(CO2·온도), Plug/Switch(TV·선풍기), Light(회의실·연구실), Speaker, Clock. MotionSensor 는 `deployment_pool.json` physical_set 에 있으나 등록 기기 목록에는 없다 — 실물 확인 필요.
2. **관찰 해상도로 보이는 차이만.** SenSys 는 사람이 초 단위로 기록했고 센서 그래프는 1분 해상도였다. 1초 이하 차이는 플랫폼 로그 타임스탬프가 있어야 한다.
3. **실험 시간이 현실적인 것.** 반례 시각이 수십 분 이상이면 제외하거나 "그 시각까지 동작 없음"만 본다.
4. 반례 입력을 사람이 재현할 수 있어야 한다(문 열고 닫기, 자리 비우기 등). null·음수 입력 반례는 실기기에서 못 만든다.
5. 선정 규칙을 먼저 적고 고른다. 결과를 보고 사례를 바꾸지 않는다.

### A. DIVERGE 후보 (E3 68건 중 테스트베드 서비스만 쓰는 것)
근거: `E3_application/divergence_audit_20260915/results-audit.md`, `cases.json`(witness_input, ir_actions, joi_actions). 현재 timer 워크트리에만 있음 — codex 의 paper 병합 후 경로 확인.

| 우선 | 사례 | 유형 | 서비스 | 예측 차이 | 메모 |
| --- | --- | --- | --- | --- | --- |
| 1 | C24_001 | 지속·주기 혼동 | ContactSensor, Speaker | IR 60 s 에 안내, JoI 는 약 1770 s | 60 s 에 **안내 없음**을 보면 충분. 가장 크고 뚜렷한 차이 |
| 1 | C24_004 | 지속·주기 혼동 | PresenceSensor, Speaker | IR 60 s, JoI 는 15 s tick × 60 | 위와 같은 유형, 다른 센서 |
| 1 | C24_002 | 호출 범위 오류 | PresenceSensor, Speaker | 지속 조건 전 t=0 에 JoI 만 안내 | 즉시 보임 |
| 2 | C08_032 / C08_041 | 이벤트 대기→1초 polling | ContactSensor, Switch/Light | IR 은 100 ms 조건 변화에 반응, JoI 는 1 s tick 에서만 검사 | 1 초 미만으로 문을 열었다 닫으면 JoI 는 **동작을 놓침**. 단, 센서 보고 지연·디바운스가 펄스를 먼저 없앨 수 있어 사전 확인 필요 |
| 2 | C14_004 / C14_007 / C08_036 | 이벤트 대기→polling | MotionSensor, Light | 위와 같음 | MotionSensor 실물 확인 후 |
| 3 | C20_002 | 지속 1 틱 조기 | ContactSensor, Switch | IR 5 s, JoI 4 s | 1 s 차이. 플랫폼 로그 타임스탬프가 있을 때만 |
| 3 | C20_003 / C20_009 / C20_014 | 지속 1 틱 조기 | PresenceSensor, Switch | 30 s/120 s/600 s 에서 1 s 조기 | 위와 같음. SenSys hero 와 같은 기기 |
| 제외 | C24_003 | 지속·주기 혼동 | Plug, Speaker | JoI 71880 s | 너무 김 |
| 제외 | C17_003 | 없는 break | Speaker | 1 시간 뒤 두 번째 호출 누락 | 너무 김 |
| 확인 | C07_024 | 이벤트 대기→polling | PresenceSensor, ColorControl | | 테스트베드 조명이 ColorControl 을 지원하는지 모름 |

목표: 유형이 겹치지 않게 **4–6건**(우선 1 세 건 + 우선 2 한두 건 + 로그 해상도가 되면 우선 3 한 건).
feedback 결과가 나오면 같은 사례의 **repair 전(DIVERGE)–후(EQUIV)** 짝을 1순위로 바꾼다(B1 에서 EQUIV 가 된 사례 중 위 표에 있는 것).

### B. EQUIV 후보
1. **SenSys 실기기 6건 재사용**(새 실행 없이 관찰 기록 사용): hero(지속 5분), count(30 s × 3), edge(문→조명), delay(3분), CO2 rising, 온도 rising. 원자료 `sensys/evaluation/results/deployment/{registration_package_live.json, observations.json, live_raw/}`.
   재사용 전 필수 확인:
   - [ ] 6건 IR 을 현재 Timeline 형식·binding 으로 옮김(`edge: none, for`, cycle `period 100 MSEC` 등 옛 형식).
   - [ ] **실제로 등록한 JoI**(hero 는 등록 때 `==|` → `==` 로 바꿈)와 게이트 없는 hero 샘플 4개, 총 10개를 현재 Explorer 로 검사.
   - [ ] hero 수정 코드(`period 100`, `hold_ticks >= 3000`)가 지속 1 틱 조기 유형으로 DIVERGE 가 나오는지 확인. 나오면 hero 는 EQUIV 예시에서 빼고 "초 단위 관찰로 안 보이는 차이" 사례로 재분류.
   - [ ] rising 2건: 현재 계약은 초기에 이미 참이면 edge 발화 — 관찰 당시 시작 상태가 거짓이었는지 기록으로 확인.
   - [ ] 관찰은 사람 기록·초 단위·1회 실행임을 표에 명시.
2. 필요하면 A 와 같은 유형·같은 기기의 E3 EQUIV 후보 1–2건을 추가해 DIVERGE 와 짝을 맞춘다.

## 3. 실행 전 whisoo 가 정할 것
- [ ] 테스트베드가 지금도 살아 있는지, 기기 목록(MotionSensor, ColorControl 조명 여부).
- [ ] 동작 시각 기록 방법: 사람 기록(초) / 플랫폼 로그 타임스탬프(해상도?). 우선 3 포함 여부가 여기서 정해진다.
- [ ] 입력 주는 방법: 사람이 직접 / 가상 기기 주입. 가상 주입이면 "실기기" 범위를 문장에서 좁힌다.
- [ ] 허용 오차 규칙(예: 로그 해상도 + 기기 반응 지연 상한)을 결과 보기 전에 고정.
- [ ] 건수(DIVERGE 4–6, EQUIV 6 + α)와 원고 위치(Evaluation 끝 / Implementation 끝).

## 4. 기록할 것 (실행 시)
사례 ID, 후보 SHA256, 등록한 코드 원문(바꾼 곳이 있으면 diff), 반례 입력과 사람이 실제로 준 입력의 시각, 예측 trace(IR·JoI 양쪽), 관찰 trace, 기록 해상도, 판정(일치/불일치/관찰 불가), 실패·재시도 전부.

## 5. 분량 제약 (2026-09-15 논의)
표 1개 + 반 단 그림 1개 이하. SenSys 처럼 테스트베드 사진 + 표 + trace 그림 세 개는 넣지 않는다. 분량이 모자라면 trace 그림부터 뺀다.
