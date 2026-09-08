# 과거 실험·진단 도구

특정 문제를 조사하거나 이전 설계를 시험했던 도구를 모았다. 현재 검증 진입점은
`explorer.verification.gate.gate_pair`이며, 현재 작업 상태·증명·평가는 [Explorer README](../README.md)를 따른다.
이 폴더의 과거 E1/cron/다중 시나리오 정책을 현행 검증 계약으로 사용하지 않는다.

| 파일 | 보관 목적 |
| --- | --- |
| [demo_tick.py](demo_tick.py) | 초기 tick 실행을 단계별로 출력하는 예제 |
| [m3_check.py](m3_check.py) | 초기 정답 IR·코드 쌍의 매핑/동작 대조 |
| [legacy_conformance.py](legacy_conformance.py) | 이전 SenSys 실행기와 제한된 의미론 비교 |
| [differential_sweep.py](differential_sweep.py) | 구버전 bounded 탐색과 tick 기준 실행의 불일치 조사 |
| [e3_classify.py](e3_classify.py) | 이전 서비스·바인딩·수량 정책에 따른 실패 분류 |
| [prevalence.py](prevalence.py) | 당시 미지원 패턴의 발생 빈도 조사 |
| [e1.py](e1.py) | 초기 단일 프로그램 탐색/오류 주입 보고서 생성 |
| [cron.py](cron.py) | 초기 cron→tick 변환 실험. 현행 gate의 앵커 검사는 별도 |
| [composite.py](composite.py) | 여러 시나리오가 GV를 공유하는 탐색 실험 |
| [obligations.py](obligations.py) | 초기 탐색 그래프의 무행동·초기 GV 의존 진단 |
| [project.py](project.py) | 초기 탐색 그래프의 경로·행동 투영 |
| [replay.py](replay.py) | 센서 이력과 배치 후 행동의 진단 실험. 현행 반례 재생은 `explorer.verification.product` |

저장소 루트에서 새 모듈 경로로 실행한다. 예:

```bash
python -m explorer.diagnostics.demo_tick
python -m explorer.diagnostics.differential_sweep --help
```

옛 보고서의 `python -m explorer.<이름>`은 이동 전 명령이다. 현재는
`python -m explorer.diagnostics.<이름>`으로 실행한다. 보고서·평가 소스 ZIP의 원문은 보존했다.
기존 `runs/` 출력과 `corpus/` 입력 경로는 유지한다. 현재 논문용 평가 하네스·입력 감사는
[eval/](../eval/), 회귀 테스트는 [tests/](../tests/), 기준 실행기는
[tests/oracles/](../tests/oracles/)에 있다.

이동과 import/명령 표기 수정은 [등록부](../docs/index.json)에 기록한다. 문서 관리 검사는
동결 소스 ZIP에 정확히 그 수정만 적용한 결과와 현재 파일을 대조한다. 새로운 평가로
교체할 때 이 이전 버전용 경로 대응도 검토하거나 제거한다.
