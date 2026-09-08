# Explorer

확정된 Timeline IR과 생성 JoI 코드의 timed ACTION trace를 비교한다.
**현재 상태·다음 작업의 기준은 이 README다.** 논문 전체 배경은 [프로젝트 README](../README.md)를 따른다.

## 폴더별 역할

```text
explorer/
├── README.md                 시작점·상태·다음 작업
├── __init__.py               Python 패키지
├── requirements.txt          검증 의존성
├── runtime/                  언어 파싱·접지·IR/JoI 실행기
├── analysis/                 변수·입력·지원 구문을 위한 공통 정적 분석
├── verification/             동등성 검증 엔진·입력 모델·관찰·반례 재생
├── tests/                    구현을 호출하는 회귀·의미론 검사
│   └── oracles/              직접 전수 실행하는 비교 기준
├── eval/                     후보 생성·입력 감사·평가 실행·결과 집계
│   └── results/              실행별 동결 결과·프로토콜·소스
├── diagnostics/              과거 문제 조사·이전 설계 실험
├── docs/
│   ├── model/                무엇을 어떤 규칙으로 검증하는가
│   ├── proof/                왜 검증이 옳고 결정적인가
│   ├── paper/                논문에 연결할 평가 요약
│   ├── archive/              완료 계획·인계·중간 자료의 보관본
│   ├── index.json            문서 위치·선택 평가·경로 이동 기록
│   └── manage.py             문서/평가/소스 정합성 검사
├── candidates/               생성된 후보 원본
├── corpus/                   기존 고정 시나리오 입력
└── runs/                     과거 진단 보고서
```

실행 코드를 찾으면 `runtime/`·`analysis/`·`verification/`, 검증 근거를 확인하려면
`tests/`·`eval/`, 설명을 읽으려면 `docs/`로 들어간다. 과거 실험의 목록과 실행법은
[diagnostics 안내](diagnostics/README.md)에 있다.

## 문서 읽는 순서

| 목적 | 기준 문서 | 상세 자료 |
| --- | --- | --- |
| 모델·지원 범위·판정 이해 | [검증 계약](docs/model/VERIFICATION_CONTRACT.md) | [런타임 규칙](docs/model/RUNTIME_CONTRACT.md), [서비스 모델](docs/model/SERVICE_MODEL.md), [지원 구문](docs/model/SUPPORTED_FRAGMENT.md) |
| 보장 명제·soundness·결정성 | [통합 증명](docs/proof/PROOF_OBLIGATIONS.md) | 같은 `proof/` 폴더의 입력·실행·탐색·기호/SMT·관계·시간 보조정리 |
| 논문에 쓸 평가 근거 | [평가 요약](docs/paper/EVALUATION.md) | 요약에서 연결하는 `eval/results/` 원본·프로토콜·감사 |

평소에는 이 README와 위 기준 문서 세 개만 읽으면 된다. 상세 부록은 당시 버전의
기술 근거이며, 그 안의 과거 수치·TODO를 현재 지시로 사용하지 않는다.

## 현재 상태와 다음 작업

- Explorer 개발·증명은 **일시 중단**했다. H 없는 탐색, 서비스 명세 입력, typed 값 흐름,
  제한된 SMT 산술, 정수 관계 검증, 무관찰 대기 생략과 catalog clock 범위를 구현했다.
- [D/S 통합 증명](docs/proof/PROOF_OBLIGATIONS.md#통합-정리의-도출)은 독립 검토 보완까지 완료했다.
  선언 모델·고정 인증 알고리즘에 대한 수작업 증명이며 실행기/프런트엔드 신뢰 기반을 명시한다.
- 실제 JoI 서버 측정은 이 모델 내 IR–코드 동치 주장의 필수 작업이 아니다.
- 다음은 **논문 전체 구성·핵심 주장부터 정하고 Explorer 방법·증명·평가의 배치를 결정**하는 것이다.
  이후 집필에서 같은 명제·버전·분모와 신뢰 기반·평가 한계를 사용한다.
- 별도 이슈 C15_005/C18_003: IR·코드가 함께 자정 종료 의도를 놓친다. 쌍의 동등성과
  자연어 정답성은 별개이며, 의도 수정은 별도 데이터 버전으로 처리한다.
  현재 판정을 뒤집거나 평가 분모에서 제외하지 않는다.

논문 전체 후속 과제에는 표현 범위(E2), 비용·확장성(E4), 원고·초록 정합화도 있다.

## 실행과 검사

저장소 루트에서 실행한다. 폴더 정리 후의 공개 진입 경로:

```python
from explorer.verification.gate import gate_pair

result = gate_pair(ir, binding, devices, joi_block,
                   horizon_ms=None, input_step_ms=100,
                   verification_mode="auto")
print(result.verdict)
```

```bash
python -m explorer.tests.test_contract
python -m explorer.eval.frozen_contract --help
python explorer/docs/manage.py render
python explorer/docs/manage.py check
```

새 코드는 역할에 맞는 하위 패키지에 둔다. 최상위에 구현·실험 스크립트나 설명 MD를
다시 추가하지 않는다. 현재 상태는 이 README, 모델은 검증 계약, 증명은 통합 증명,
평가 수치는 원본에서 생성한 평가 요약에만 기록한다.

## 기록 보존과 경로 변경

- 원시 평가·감사·소스 ZIP은 변경하지 않는다. [등록부](docs/index.json)는 이동 전후 경로를 관리한다.
- `manage.py check`는 동결 소스에 import/명령·저장소 경로·소스 수집 변경만 적용한 결과와
  현재 파일을 바이트 단위로 대조한다. 기술 부록도 원문을 보관하고 링크/경로 변경만 대조한다.
  알고리즘 변경을 폴더 정리로 통과시키지 않으며, 과거 평가를 새 실행으로 기록하지 않는다.
- 다음 평가를 선택할 때 현재 `source_layout`의 이전 버전 대응을 재검토한다.
- 완료 계획/인계는 [문서 보관본](docs/archive/pre-consolidation-2026-09-08.zip),
  중복 생성 IR 1,940개는 [중간 IR 보관본](docs/archive/generation-ir-staging-2026-09-08.zip)에 있다.
  ZIP의 원래 경로·바이트·SHA를 관리 명령이 검사한다. 필요하면 임시 폴더에 풀어 확인한다.
- `__pycache__/`는 재생성 가능한 캐시다. 후보·원시 결과와 구별하며 Git에 추가하지 않는다.
