# Timeline IR handoff

상태: **사용자 피드백에 따라 §5 본문 축약 (2026-09-17). 로컬 Markdown과 `/home/gnltnwjstk/overleaf-paper/sections/timeline-ir.tex`에 반영. 사용자 요청으로 GitHub master에 push 완료 (`6ac24d4`). Overleaf에서 GitHub pull 필요.**

## 최신 수정: 핵심 operator와 결정성 중심으로 축약

- 명령형 코드의 여러 문장에 걸쳐 구현될 수 있는 행동 단위를 operator로 명시한다는 설계 이유를 한 문장으로 추가했다. 코드에서 IR을 추출하거나 operator 자체가 새롭다는 주장은 하지 않는다.
- 별도 Execution rules 문단을 삭제하고 기본 의미는 operator 표에 통합했다. 완료 후 대기라는 `cycle.period` 의미는 표에 남겼다.
- device binding은 도입부에서 한 번만 언급한다. service/type 검사, 갑자기 등장하는 `$x`, read–delay 예, edge+sustain 지원 제한, clock/global 관리, readability 단서를 본문에서 삭제했다.
- JSON 예제는 그대로 두되 설명을 두 문장으로 줄였다. 전체 분량에 따라 예제는 추후 삭제 가능하다.
- reaction은 한 시점에 대기/종료까지 실행하는 단위로 설명하고, action trace와 D 명제·짧은 귀납 근거를 유지한다. $u(t)$는 시각 $t$에서 유지되는 입력값이다. 입력 우선 처리, 정상 유한 reaction과 유한 시간 내 유한 reaction이라는 전제, 구현 의미 대응 가정은 유지했다.
- 제출용 짧은 증명 부록과 상세 보존용 명세는 유지한다. 아래의 두 display 수식·별도 Execution rules 유지 지시는 이번 사용자 피드백으로 대체한다.

- 검증: 기존 예제 5개 통과, Markdown/LaTeX JSON 일치, operator 8개와 binding 1회 언급 확인, Tectonic PDF 빌드 성공. 미해결 참조·overfull 없음. 본문 밖의 underfull·패키지 인코딩·그림 PDF 버전 경고는 남는다. 원격 Overleaf 그림 수정(`ce6f1b8`) 위에 rebase 후 PDF 재빌드를 완료하고 `6ac24d4`를 push했다. 원격 master 일치를 확인했다.

## 최신 수정: 짧은 증명 부록

- `DETERMINISM_APPENDIX_COMPACT.md`가 원고용 부록이다. 연산자별 정상 후속 상태의 유일성, 유한 반응 내부 귀납, event policy와 시간 진행 조건에 따른 trace 귀납을 남겼다. 본문의 JSON·표·두 수식은 이전 LaTeX와 동일함을 검사했다.
- 상세 문서 `SYNTAX_AND_DETERMINISM_APPENDIX.md`는 삭제하지 않았다. 전체 grammar·표기 설명·확장 증명은 별도 명세로 보존하며, 제출 원고의 핵심 논증이 외부 문서 심사에 의존하지 않도록 했다.
- 공식 CFP 확인 결과 부록도 기술 내용 9쪽 제한에 포함된다. 참고문헌만 추가 1쪽 허용: https://percom.org/call-for-papers/. 별도 supplementary 제출·심사 허용은 확인되지 않았다.
- 원격 `c99726d`의 시스템 그림 변경(`system.png`)을 pull해 보존했다. 부록 내용은 약 반 페이지 분량이며 현재 배치상 7–8쪽에 걸친다. 현재 전체 빌드는 8쪽이지만 Explorer·Evaluation 등이 아직 없어 최종 분량 충족을 의미하지 않는다.
- Tectonic 빌드, 참조/overflow 검사, 예제 5개와 frontend 회귀 22개 통과. 기존 underfull/그림 PDF 버전 경고는 남는다. 글꼴 축소나 여백 변경으로 압축하지 않았다.
- 아래 절은 초기 초안 작성 이력이다. 긴 부록을 제출 원고에 포함하거나 규정을 미확인으로 적은 과거 기록은 위 결정으로 대체한다.

- `PerCom_version.md`에 실제 JSON 예제, 8개 operator 표, reaction relation, D 정리와 증명 개요를 넣었다. `SYNTAX_AND_DETERMINISM_APPENDIX.md`에 operator/식 문법, well-formedness, state tuple, 내부 전이, 상세 귀납 논증을 작성했다.
- operator별 예제는 sustain, snapshot, cycle/period를 우선한다. 지원하지 않는 병렬·일반 집계를 예제로 넣지 않는다.
- 결정론 정리는 `explorer/docs/proof/PROOF_OBLIGATIONS.md`의 전제와 정확히 맞춘다.
- `per-automation`, `executable behavioral specification`, `input-deterministic` 용어를 유지한다.
- readability/usability 및 다른 IR보다 표현력이 우월하다는 주장을 넣지 않는다.

## NL → Timeline IR 예제와 사용자 확인의 설명 (2026-09-17)

- **§5 첫머리에 자연어 요청 → 실제 Timeline IR → 확인할 의미를 나란히 보여주는 예제 하나를 넣는다.** 현재 Overview의 "LLM이 IR을 제안하고 사용자가 확정한다"는 설명에서 빠진, 후보 IR에 무엇이 들어가고 사용자가 무엇을 확인하는지를 구체화한다.
- 예제 후보: "온도가 25°C를 초과한 상태가 3분 동안 유지되면 에어컨을 켜줘." 조건은 `wait`의 조건, 3분 유지는 지속시간, 켜기 동작은 `call`, 대상 기기는 확정 binding에 대응시킨다. 실제 지원 문법·서비스를 확인한 IR을 사용하며, 설명용 축약은 축약임을 표시한다. 일회 실행인지 반복인지도 예제에서 명시한다.
- **보여줄 특성은 시간 의미가 primitive operator와 인자에 직접 나타난다는 구조적 명시성이다.** 같은 의미가 생성 코드에서는 타이머·상태 변수·조건문에 나뉘어 구현될 수 있음을 짧게 연결한다. "사용자가 이해하기 쉽다", "오류를 더 잘 찾는다", "다른 표현보다 읽기 쉽다"는 실험 결과처럼 쓰지 않는다. 사용자 이해도·확인 정확도는 평가하지 않았고, 확정 IR이 의도를 반영한다는 가정은 유지한다.
- 표기만으로 실행 의미가 모두 자명하다고 보지 않는다. 예제의 지속 조건이 중간에 깨지면 누적 시간이 초기화된다는 규칙을 한 문장으로 설명하고, 후속 실행 의미 정의에 연결한다.
- NL → IR 설명은 LLM이 요청의 조건·시간 제약·행동을 명시적인 연산자와 인자로 표현한 후보를 제안하고, 사용자가 직접 수정하거나 LLM에 수정을 요청한 뒤 확정하는 흐름이다. 별도 Semantic Parsing·IR Rendering·agent 모듈을 다시 도입할 필요는 없다.
- **배치:** Overview에는 후보 생성과 확인 대상의 짧은 설명 및 §5 참조를, §5에는 실제 IR 예제를 둔다. §5에는 실제 catalog의 `TemperatureSensor.Temperature`와 `AirConditioner.SetAirConditionerMode(Mode="cool")`를 쓰는 one-shot 예제를 반영했다. 아래 Overview 연결 문장의 추가 반영은 아직 하지 않았다.
- Overview 연결 문장 후보: "The LLM proposes a Timeline IR that expresses the requested conditions, temporal constraints, and actions through explicit operators and parameters. The user reviews these choices and may revise them before confirmation (§5)."

## E1 에서 확정된 실행 의미 (2026-09-12, 이 절 본문에 반영할 것)

근거와 재현: `../08_Evaluation/E1_adequacy/` (README §4 계약 절, §6 경계 probe).

- `cycle.period` 는 **회차 종료 후** 대기다. 정각마다 시작하는 fixed-rate schedule 로 쓰지 않는다.
  "매 N" cadence 가 필요하면 회차 시간을 빼야 한다. body 의 timeout 이 이미 cadence 를 담당하면 `period: "0 MSEC"` 가 맞다.
- edge 대기는 첫 평가에서 조건이 이미 참이면 **발화한다**. "사건" 의미가 필요하면 선행 level 대기를 둔다.
- 다른 대기가 도는 동안 일어난 edge 는 latch 에 반영되지 않는다.
- 실행기는 `start_at.anchor == "cron"` 을 거절한다. 앵커를 소거하고 한 발화 창만 실행한다.
- 미초기화 변수는 `null` 이고 null 산술은 0 으로 강제된다. 현재 검증 계약에 명세돼 있지 않다.
- `Clock.Timestamp` 는 초 단위(`now_ms // 1000`), `Clock.Hour/Minute` 은 분 단위다.

## 표현 경계로 쓸 문장 (E1 근거)

**하지 말 것:** 아래 셋을 Timeline 의 한계로 쓰면 틀린다. E1 에서 전부 표현됐다.
- 가변 반복 간격 — duration 피연산자는 리터럴이지만 `cycle(until "k >= $n", count "k"){ delay "1 단위" }` 로 펼치면 된다.
  단위가 곧 해상도이자 상태 수라는 **비용**으로 쓰고, 불가로 쓰지 않는다.
- 도는 중 일어난 사건의 기억·시간창 — `Clock.Timestamp` 스냅샷 + `$t != null` 로 표현된다.
- 자동화가 켜지기 전의 과거 — 언어가 아니라 **서비스·카탈로그** 문제다. 기기별 변경 시각 서비스가 있으면 `read` 한 줄이다.

**쓸 수 있는 것 (E1 depth, 저자 의미 감사 2026-09-13 확정):** `../08_Evaluation/E1_adequacy/breadth/depth/RESULTS.md`
- **Timeline 하나에는 병렬 branch 가 없다. 서로 독립인 흐름은 Timeline 여러 개로 분해해 배포할 수 있다.** E1-092: 한 Timeline 에
  두 흐름을 끼우면 주입한 Alexa 실패가 집 종료 명령까지 멈추고(v1, 0/1), 공유 상태·합류·순서 의존이 없는 두 흐름을 Timeline 두 개로
  나누면 정확히 맞는다(v2, 1/1). **일반 fork–join 이나 공유 상태 병렬성을 지원한다고 넓히지 않는다.**
- **표본 수가 고정된 집계는 표현된다.** E1-095: 시각별 snapshot 변수 5개와 `(v1+…+v5)/5`. Timeline IR 에는 일반 mutable
  accumulator 나 입력 개수에 따라 변하는 집계가 없다 — 이것은 별도 언어 경계로 쓰고, 일반적인 평균·횟수·이력은 backend 서비스
  (예: history/statistics sensor)가 계산하고 IR 은 그 typed 결과를 읽어 orchestration 을 검증하는 방향으로 기술한다.
  이 위임을 IR 의 동적 집계 성공이나 측정하지 않은 효율 향상으로 쓰지 않는다.
- **고정 한도 2 의 rolling window 는 표현된다.** E1-028(시각 슬롯 2개). 실행 시간에 정해지는 N·무제한 이력은 주장하지 않는다.
- **환경 시각은 입력으로 읽는다.** E1-072: 일출·일몰은 플랫폼이 주는 daylight 입력이고 06:00/18:00 은 한 실행의 값이다.

## E2 에서 온 요청 (2026-09-14, whisoo 결정)

- 이 절에 **"Timeline 은 시간·상태·로직을 담고, 어떤 기기를 가리키는지는 사용자가 확정한 binding 이 정한다"** 수준의 문장 하나만 둔다.
- all/any, 셀렉터를 한 줄로 쓸지 나열할지, binding 자리가 여럿일 때의 비교 규칙은 **원고에 쓰지 않는다**(독자에게 noise, 실험 결론에 영향 없음).
  근거 규칙은 `../08_Evaluation/E2_fidelity/BINDING_DECISION_2026-09-14.md` 에만 둔다.

**하지 말 것(추가):** "프로그램이 고정돼 있으니 finite-state" 같은 넓은 문장을 E1 결과처럼 쓰지 않는다(새 probe 없음).
지원하지 않는 병렬·일반 집계를 operator 예제로 넣지 않는다는 기존 방침은 유지한다.

## 결정론성 명제 D의 원고 배치 (2026-09-17)

- **이 절(§5)에 명제 D / input-determinism을 둔다.** 고정된 Timeline IR, 실행 모델, 초기 상태와 timed input history에서 각 정상 반응은 유일하며, 유한 반응·시간 진행 조건을 만족하면 timed action trace가 유일하다. 입력 자체를 하나로 제한한다는 뜻은 아니다.
- 본문은 문법·상태·반응 규칙의 최소 정의 → D의 전제와 명제 → 짧은 증명 개요 순서로 작성한다. 입력과 timer가 동시에 바뀔 때의 순서, 상태 수명, 제어 흐름 결합 규칙을 정의한다.
- **증명 개요:** 원시 연산·명령의 유일성에서 유한 반응 내부 전이 수에 대한 귀납으로 반응 유일성을 얻고, 반응 횟수와 시간 진행에 대한 논증으로 trace 유일성을 얻는다. 상세 규칙별 귀납은 부록에 둔다.
- 기존 [검증 계약 D](../../explorer/docs/model/VERIFICATION_CONTRACT.md), [프런트엔드 §5](../../explorer/docs/proof/FRONTEND_CORRECTNESS.md), [통합 증명 L3·L4](../../explorer/docs/proof/PROOF_OBLIGATIONS.md)가 근거다. 그 수작업 논증을 이 절의 정리·수식·증명 개요와 부록 D1–D3/trace 정리로 편집했다. 기존 L1–L7 식별자를 대체하지 않는다.
- 실행기·프런트엔드의 신뢰 기반을 명시한다. 전체 Python 구현의 기계 검증, 임의 프로그램의 종료, Explorer의 판정 완료 또는 NL→IR의 의도 정확성을 D로 주장하지 않는다.
- Explorer의 검증 soundness 명제 S는 [§6 HANDOFF](../06_Code_Generation_and_Behavioral_Validation/HANDOFF.md)에 둔다. 같은 실행 모델 정의는 필요한 곳에서 참조하고 중복 설명하지 않는다.

## 문법 배치 후보와 이번 작성 범위 (2026-09-17)

- [PRESENTATION_CANDIDATES.md](PRESENTATION_CANDIDATES.md): Flowlog(NSDI 2014), Lucid(SIGCOMM 2021), NetKAT(POPL 2014)의 실제 원문 위치를 확인했다. A=예제+operator 표+정리, B=본문 핵심 grammar, C=JSON/추상 구문/전이 대응의 세 후보를 비교했다.
- 현재 초안은 A를 적용한다. 전체 구조를 부록에 숨기지 않고 본문에 실제 IR을 보여주며, 상세 grammar·증명은 별도 파일에 둔다. 제출판 appendix/supplement 허용과 분량은 미확인이다.
- SenSys grammar의 nested-cycle 금지, bounded-horizon 의미, fixed-rate처럼 읽히는 period 설명은 현재 의미와 달라 복사하지 않았다. 생성 프롬프트의 일부 지시도 현재 계약과 불일치하므로 논문 근거로 삼지 않았다. 실행기·프롬프트 자체는 이번에 수정하지 않았다.
- 예제 점검: `PYTHONPATH=. python3.12 PerCom/05_Timeline_IR/examples/check_sustain_once.py`. 실제 preparation/catalog, 본문 JSON 일치, 연속 true, 중간 reset, deadline에서 false, strict threshold를 확인한다. 선택한 이력의 반복 실행·입력 저장소 비변경도 점검한다. 예제 점검은 D의 증명이나 사용자 가독성 실험이 아니다.
- 사용자 요청에 따라 후보 A를 Overleaf 원고에 적용했다. `overleaf-paper/sections/timeline-ir.tex`는 §5 본문, `sections/timeline-ir-appendix.tex`는 참고문헌 뒤 부록이며 `main.tex`에서 불러온다. 추가분은 검정색이다. 기존 §1–4와 figure 및 bibliography는 보존했다.
- LaTeX에서는 operator 표와 JSON을 한 단 너비로, 긴 수식은 여러 줄로 배치했다. 부록의 긴 operator-case 표는 같은 내용을 문단별로 옮겼다. 한국어 편집 메모·provenance 기록·문헌 배치 후보는 논문에 넣지 않았다.
- 후속: 제출판의 appendix/artifact 위치와 지면 규정 확인. 새 문헌은 표현 방식 참고만 했으므로 공용 BibTeX에 자동 추가하지 않았다.
- 동기화 점검: GitHub pull 후 작업, 원격 master가 `a3c4582`와 일치함을 확인했다. Tectonic으로 PDF 빌드 및 주요 페이지 육안 확인, 참조/JSON 일치 검사, 예제 5개와 frontend 회귀 22개 통과. PDF는 현재 총 9쪽(§5는 5–6쪽, 부록은 7–9쪽)이다. 단 너비 초과·미해결 참조 오류는 없으며, underfull 및 기존 그림 PDF 버전 관련 경고는 남는다. Overleaf 자체 컴파일은 사용자 pull 후 확인한다.
