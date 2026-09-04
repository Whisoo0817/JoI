# Legacy Claims and Evidence

이 표는 기존 원고의 자산을 보존하되, 새 설계에 자동으로 전이되지 않도록 구분한다.

| Legacy ID | 기존 주장 또는 증거 | 근거 | 새 방향에서의 상태 |
|---|---|---|---|
| L-C1 | 사용자 확인용 rendering과 검증 oracle을 한 Timeline IR로 연결 | S1 Abstract, §1, §5 | 개념적 선행 자산. 새 논문은 readability 주장을 제거하고 executable authoritative specification 역할만 유지 |
| L-C2 | IR→FSM→boundary event→bounded trace-equivalence의 deterministic gate | S1 §1, §4, §6 | 대체되는 핵심. 새 논문은 boundary-point sampling을 reachable behavior exploration으로 확장하므로 결과 승계 불가 |
| L-C3 | 생성·검증이 edge에서 가능하고 gate는 LLM-free | S1 §1, §8.4 | 이번 새 flow의 중심 contribution이 아님. 시스템 구현 배경으로만 재사용 가능 |
| L-C4 | 382 automation benchmark와 24 behavior categories | S1 §8, Appendix B | E2/E3의 후보 입력 자산. 새 grammar·semantics에 재인코딩하고 provenance를 공개해야 재사용 가능 |
| L-E1 | 1,552 genuine mutants 중 1,541 검출, 99.3% | S1 Abstract, §8.2, Table 3 | old boundary-event verifier의 선행 결과. 새 Explorer/observer의 성능 증거가 아님 |
| L-E2 | Qwen3.5-9B에서 35개 후보 flag, 11 repair, 24 reject, divergent deployment 0 | S1 Abstract, §8.3 | 기존 end-to-end pipeline의 결과. 새 lowering 및 semantics가 같을 때만 제한적으로 비교 가능 |
| L-E3 | 최종 배포 집합에 35,800 randomized dense replay | S1 Abstract, §8.3 | 독립 replay라는 아이디어는 E3 control로 유용. 수치는 승계 불가 |
| L-E4 | Mac mini M4에서 gate median 0.97 ms, p95 0.7 s, worst 8.4 s, peak 54 MB, 5.5 W | S1 Abstract, §8.4 | old algorithm의 cost. 새 Explorer scalability는 새로 측정해야 함 |
| L-E5 | Raspberry Pi 기반 hub와 실제 기기에서 6개 automation 배포 | S1 §8.4, Table 6 | integration existence proof. 새 논문의 physical correctness 증거로 사용 불가 |

## 승계 가능한 자산

- Figure 1의 핵심 대조: syntactically different but behaviorally equivalent idioms와 syntactically plausible but behaviorally divergent idiom.
- 382개 command 및 24개 behavior category의 원자료가 완전한 provenance와 함께 존재한다면 E2/E3의 한 corpus로 재사용 가능.
- 기존 genuine LLM failures와 missed mutants는 E3의 outcome-informed selection을 투명하게 표시한 exploratory/adversarial set으로 재사용 가능.
- randomized dense replay는 새 checker의 false-accept를 교차 점검하는 보조 oracle 설계에 참고 가능.

## 승계할 수 없는 것

- old boundary-event verifier의 recall을 새 reachable Explorer의 recall로 표기.
- old interpreter/simulator agreement를 새 formal semantics conformance로 표기.
- 단일 JoI backend 결과로 backend independence를 주장.
- six-automation deployment로 real-world completeness 또는 physical-device correctness를 주장.
- rendering fault coverage로 사용자가 IR을 올바르게 이해한다는 주장을 대체.

