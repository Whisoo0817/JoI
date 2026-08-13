# M3 발견 — 정답 307쌍 중 신 검사기가 잡은 결함 (2026-08-14)

주기형·비 blocking 48쌍 판정: **EQUIV 40 / DIVERGE 8**. 8건 전수 해부 결과
접착 잔여가 아니라 **쌍 자체의 결함 6건 + 집합 바인딩 미지원 2건**.
전부 v1 게이트(경계 이벤트 합성 + tolerance)를 통과해 "정답"으로
캐시된 것들이다 → E2(TCB 충실성)의 실물 사례.

## 레퍼런스 IR 결함 (4건) → 382 재감사(§5.2) 수정 대상

- **C13_002/004/006** — "30분마다 sleep↔auto 토글" 명령인데 IR은
  `call auto; delay 30; call auto; delay 30` — **양쪽 다 auto**, sleep이
  없음. JoI(상태 토글)가 맞고 IR이 틀림.
- **C17_006** — "미세먼지 ≥200이면 high, ≤100이면 low"인데 IR의 else
  분기가 **low가 아니라 high**. JoI가 맞음.

## 생성 JoI 결함 = v1 생존자 (1건+의심 1건)

- **C14_002** — 밝기 -10, 바닥 0 클램프 의도. JoI가 `if (0 < tmp)
  { tmp = 0 }` — **클램프 방향 반전** (양수를 0으로, 음수는 방치).
  v1의 "경계 없는 산술" 잔여 클래스가 실제로 살아남은 실물.
  신 검사기는 반례와 함께 DIVERGE.
- **C08_029 (의심)** — "위쪽(upper) 조명이 켜지면 아래쪽(bottom) 켜기"
  인데 JoI가 **#Bottom을 읽고 #Bottom을 켬** (자기 참조). 액션도
  `switch_switch()` 호출형이라 카탈로그 재감사와 함께 판정 필요.

## 레퍼런스 IR 결함 + 순서 (1건)

- **C14_004** — "10 올리고, 100 도달하면 MaxLevel"인데 IR이 **올리는
  call을 먼저 무조건 실행** 후 검사 → 110 발화 + MaxLevel 중복.
  JoI(먼저 검사, 100 캡)가 의도에 맞음.

## 집합 바인딩 미지원 (1~2건) → §9.4 바인딩 표로 해소 예정

- **C08_032** — IR call 1개(Light.MoveToBrightness)가 hallway+livingroom
  두 그룹을 의도. JoI는 all() 두 문장. §9.4의 "1 op + 집합 바인딩 →
  grounding 언롤"이 구현되면 EQUIV. 현 M3 지름길은 첫 태그만 바인딩.

## 기타

- cron 16건: cron.py 달력 가드 통합 후 판정 (보류)
- ZeroDivisionError 1건 (C13 계열 인접): period 0 계열 — one-shot 작업에서 함께
- 엔진 수정 1건(이슈 #22): 수식 경유(affine) 셀 배분이 태그 없는 키에
  떨어져 실행 키에 도달 못 하던 under-exploration —
  `_closure_device_reads`를 월드 키로 통일. e1 표 회귀 무변화
  (10코퍼스는 단일 태그라 영향 없었음). C14_001이 이 수정으로 EQUIV.
