# E2 원고 작성 계획 (2026-09-14, whisoo 확인 전 초안 — 원고 파일은 아직 쓰지 않음)

근거 수치는 `E2_SUMMARY.md` §4 와 `RESULTS.md` "Final version" 절. 원고(`PerCom/6_Evaluation/PerCom_version.md`)는 whisoo 가
이 계획을 확인한 뒤 쓴다.

## 1. 논문 안에서의 위치

- **Evaluation 의 두 번째 실험.** E1(요구 표현 적합성)이 "Timeline 으로 적을 수 있는가" 였다면, E2 는 **"그 Timeline 을 기준으로 한
  Explorer 판정을 믿을 수 있는가"** 이다.
- **뒤 실험의 전제.** E3(생성 결과 평가)는 Explorer 판정을 그대로 결과로 쓴다. E2 가 "DIVERGE 는 진짜 차이, EQUIV 는 반례 없음,
  미결정은 두 유형뿐" 을 보여야 E3 수치를 읽을 수 있다.
- **분량**: 약 0.6 쪽 (설정 한 문단, 표 1개 또는 2개, 결과 두 문단, 한계 몇 줄).

## 2. 핵심 문장 (확정 후보)

> Explorer 가 판정한 131쌍 중 독립 정답기와 어긋난 판정은 없었다(130쌍 확인, 1쌍은 정답기가 JoI 를 실행할 수 없음).
> LLM 생성 후보 39개는 전부 판정했고, 직접 만든 경계 요구 20개 중 18개를 판정했다.
> 남은 2개는 상태 폭발과 동작 횟수에 따른 시한이라는 두 유형이다.

영문 초안(확정 전):
> *None of the 131 verdicts the Explorer issued was contradicted by the independent reference (130 confirmed; for one,
> the reference cannot execute the generated JoI). The Explorer decided all 39 valid LLM-generated candidates and
> 18 of the 20 hand-built boundary requirements; the two remaining requirements fall into two classes: state
> explosion from nested repetition and timers, and deadlines that grow with the number of actions.*

## 3. 절 구성

1. **질문과 방법 (한 문단)**
   - 독립 정답기: 명세만 보고 별도 작성자가 만든 IR·JoI 실행기. E1 기대 결과와 일치(41/41, 12/12, 15/15).
   - 쌍: E1 요구 20개의 올바른 쌍 21 + 오류 쌍 81(12 계열), 388 데이터셋 무작위 LLM 후보 40.
   - 비교: 정답기 이력(원래 + 보강 약 5만 개)에서의 차이, Explorer 반례의 정답기 재생.
   - 판정 범주와 분모: 거절·시간 초과를 분모에 남김. 바인딩(기기 지목·한정자)은 범위 밖으로 둔다는 규칙을 한 줄로.
2. **표 (Table E2)** — 두 부분을 한 표로 합치는 것을 권함.
   - 윗부분 "Fidelity": 판정 131 / 정답기 확인 130 / 확인 불가 1 / 어긋남 0 / 관찰된 오류 75 중 DIVERGE 69, 놓침 0, 미결정 6.
   - 아랫부분 "Coverage": LLM 39/39, 직접 만든 요구 18/20(쌍 92/102), 미결정 원인 2유형(각 5쌍) + 입력 오류 1.
3. **결과 문단 1 — 신뢰성**: 핵심 문장 1. 반례로만 확인된 8쌍은 정답기 이력이 닿지 못한 입력임을 한 문장으로(정답기 "같음" 은 이력 범위 안).
4. **결과 문단 2 — 판정 범위**: 핵심 문장 2·3. 두 유형을 C07·E1-099 예로 짧게. C20_011 은 입력 검증 단계에서 거절된 LLM 오류로 분리.
5. **한계 (Limitations 절로 보내거나 E2 끝 2–3 줄)**
   - 정답기 "같음" 은 이력 범위 안의 증거.
   - 명세 수준 독립성은 없음(같은 명세).
   - 개선(보강 이력, 바인딩 규칙, 타이머·unroll)은 같은 쌍을 보고 추가한 개발 평가, 동결판도 보존·보고.
   - 오류 쌍은 요구별로 묶여 독립 표본 아님, LLM 표본 40.

## 4. 쓰지 않을 것

- "정확도 100%", "동등성을 증명", "명세가 옳음을 확인".
- 92%(131/142)를 정확도로 부르기. 판정 비율과 판정 신뢰성을 섞지 않는다.
- C07·E1-099 를 분모에서 빼기, LLM 39/39 를 388 전체로 일반화하기.
- 동결판 수치를 조용히 최종판으로 바꾸기(부록·아티팩트에 판별 경과를 남긴다).
- 바인딩 범위 밖 3쌍을 "놓친 오류 없음" 에서 숨기기(표 각주에 명시).

## 5. 결정 필요 (whisoo)

1. 표를 하나(Fidelity + Coverage)로 합칠지, 둘로 나눌지.
2. 판별 경과(동결판 → 최종판) 표를 본문에 한 줄로 둘지, 부록/아티팩트로만 둘지. 권장: 본문 한 문장 + 아티팩트.
3. 바인딩 범위 밖 규칙을 E2 방법 문단에 둘지, Timeline/바인딩 절에서 정의하고 E2 에서는 참조만 할지.
4. 한계 항목을 E2 안에 둘지 Limitations 절로 모을지.

## 6. 작업 순서

1. whisoo 가 위 결정 4개와 핵심 문장 표현을 확정.
2. `PerCom_version.md` 에 E2 절 초안(표 포함) 작성, 수치는 `RESULTS.md` 에서만 가져온다.
3. `3_Timeline_IR/HANDOFF.md`·`8_Limitations_and_Future_Work/HANDOFF.md` 에 바인딩 범위 밖 규칙과 한계 항목 반영 요청.
4. E3 계획이 E2 의 판정 범주·분모 규칙을 그대로 쓰는지 확인.
