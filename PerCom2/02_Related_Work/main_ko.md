# Related Work and Positioning — 한글 검토본

> 같은 폴더의 [main.md](main.md)와 `overleaf-paper/main.tex`의 해당 절을 번역했다. SenSys의 검증 기준에 따른 논리 순서를 유지하면서 중복 설명을 줄이고, 주요 연구의 비교를 표로 정리했다. 추가 피드백을 반영하고 영문과 LaTeX에 동기화했다.

자연어로 생성한 자동화를 검증하려면, 선택된 속성의 만족뿐 아니라 코드가 사용자가 요청한 대로 동작하는지도 확인해야 한다. 그러나 자연어 요청 자체는 실행해 대조할 수 있는 기준이 아니다. 이에 기존 연구를 검사 대상, 검증 기준, 검사 방법의 관점에서 비교한다(Table 1).

**검증 기준이 이미 존재하는 경우.** 트리거–액션 프로그래밍(trigger-action programming, TAP) 규칙을 형식 기법으로 검증하는 연구는 폭넓게 이루어져 왔다. AutoTap~\cite{autotap}은 선형 시간 논리(linear temporal logic, LTL)로 표현한 사용자 지정 안전 속성을 만족하도록 TAP 규칙을 합성하거나 수정한다. TAPInspector~\cite{tapinspector}는 시간 정보를 고려한 규칙 집합의 안전·활성 속성 위반을 모델 검사하고, TAPFixer~\cite{tapfixer}는 이러한 위반을 수정한다. 관련 분석은 규칙 간 취약점과 보안 취약점을 찾아내며~\cite{iruler,soteria}, HAWatcher~\cite{hawatcher}는 추출한 불변식을 기준으로 배포된 자동화를 모니터링한다. 이들 시스템은 시간적 동작과 규칙 상호작용을 포함한 자동화 동작의 속성을 검사한다.

실행 가능한 검증 기준이 제공되는 코드 생성도 있다. GPIoT~\cite{gpiot}는 생성한 신호 처리·기계학습 알고리즘 코드를 실행 테스트로 평가하며, text-to-SQL은 정답 쿼리의 실행 결과를 기준으로 생성 쿼리를 평가한다~\cite{spider}.

**LLM이 생성하는 반응형 자동화.** 자연어 요청으로부터 자동화를 생성하는 시스템들은 생성 결과를 확인하기 위해 서로 다른 검사 기준과 절차를 사용한다. AutoIoT~\cite{autoiot_maude}는 Maude 재작성 논리를 사용하여 생성 규칙의 네 가지 규칙 간 충돌 유형을 검사한다. ChatIoT~\cite{chatiot}는 자연어를 Home Assistant 자동화로 변환하고, LLM Evaluator로 형식 준수와 요청 충족 여부를 평가한다.

AwareAuto~\cite{awareauto}는 이벤트·상태 모드와 시간 조건을 포함한 자동화 규칙을 구성하고, 사용자 검토·수정과 기기 인터페이스 연결을 지원한다. VETS는 이러한 시간적 동작을 변수와 조건문으로 구현한 JOI 코드에 대해, 상태 갱신과 동작 시점이 확정된 Timeline IR의 행동을 보존하는지 검사한다는 점에서 차이가 있다.

자동화 밖에서 LACE~\cite{lace}는 생성된 접근 제어 정책을 자연어로 역변환하여 자연어 추론(natural language inference, NLI) 모델로 원래 요청과의 의미적 동등성을 판단하고, 배경 이론을 고려한 만족 가능성(satisfiability modulo theories, SMT) 솔버로 정책 간 충돌을 별도 검사한다.

본 연구는 명시된 자동화 동작이 별도로 생성된 반응형·시간 기반 코드에서도 보존되는지를 다룬다. VETS는 사용자 확인 Timeline IR을 코드 생성과 검증의 공통 기준으로 사용하고, 생성 코드의 timed action trace가 이 기준과 일치하는지 검사한다.

**Table 1. 검사 대상, 기준, 방법에 따른 대표 시스템 비교.** 각 행은 명시된 검사를 요약하며, 해당 시스템의 모든 구성 요소나 평가 지표를 나열하지 않는다. TAP: trigger-action programming; LTL: linear temporal logic; NLI: natural language inference; SMT: satisfiability modulo theories.

| 시스템                           | 검사 대상                                              | 검사 기준                                           | 방법                                     |
| -------------------------------- | ------------------------------------------------------ | --------------------------------------------------- | ---------------------------------------- |
| AutoTap~\cite{autotap}           | TAP 프로그램                                           | 사용자 지정 LTL 안전 속성                           | 오토마타 기반 합성·수정                 |
| TAPInspector~\cite{tapinspector} | 시간 정보를 포함한 TAP 규칙                            | 안전·활성 속성                                     | 모델 검사(NuSMV)                         |
| GPIoT~\cite{gpiot}               | 생성된 IoT 알고리즘 코드                               | 사람이 작성한 테스트 사례                           | 실행 테스트(오프라인 평가)               |
| AutoIoT~\cite{autoiot_maude}     | 생성된 TAP 규칙의 모델                                 | 네 가지 충돌 정의                                   | Maude 상태 공간 탐색                     |
| ChatIoT~\cite{chatiot}           | 생성된 TAP 표현                                        | 사용자 요청, 맥락, 형식 요구사항                    | LLM Evaluator                            |
| AwareAuto~\cite{awareauto}       | 반응형·시간 기반 규칙과 기기 인터페이스에 연결된 JSON | 사용자 의도와 기기 인터페이스                       | 사용자 수정 및 배포 검사                 |
| LACE~\cite{lace}                 | 생성된 접근 제어 정책                                  | 사용자 요청과 정책 충돌 정의                        | 의미 판단에 NLI, 충돌 검사에 SMT         |
| **VETS**                   | **반응형·시간 기반 JOI 코드**                   | **Timeline IR로 명시된 사용자의 의도한 동작** | **Timed action trace 동등성 검사** |
