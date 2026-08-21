"""코드 검증기(게이트) — paper 브랜치 explorer(68c8a09)에서 그대로 가져옴.

무엇을 하나: 정답 Timeline IR 과 후보 JoI 코드를 같은 기기 묶음(binding)으로
접지한 뒤, 두 실행기를 한 tick 씩 나란히 돌려 행동(기기 호출·변수 쓰기)이
갈라지는지 본다. 판정은 셋 중 하나:
  EQUIV   — 어떤 입력·시각에서도 행동이 같음 (탐색 범위 안에서 증명)
  DIVERGE — 갈라지는 입력 열(반례)을 찾음 (+ 되밟기 확인)
  REFUSED — 지원 문법 밖이라 판정 안 함 (fail-closed)

slm 파이프라인과 잇는 어댑터는 adapt.py 에 있다. 이 안의 나머지 모듈은
paper 브랜치와 자구 동일하게 유지한다 (고칠 게 생기면 양쪽에 같이).
예외: pause.py — delay 로 멈췄던 run 을 끝낸 tick 에 새 run 을 잇는 수정이
들어갔다(허브의 "period 마다 재실행" 의미, joi_cycle.md). paper 쪽에도 같은
수정이 필요하다 — 아직 안 옮김.
"""
from .gate import GateResult, gate_pair          # noqa: F401
from .adapt import gate_row, make_binding        # noqa: F401
