# Figure 4: Timeline IR, rendering, and execution

2026-09-19: 기존 습도 예시를 문 열림 이벤트 → 조명 켜기 → 안내 반복 → 문 닫힘으로 반복 종료 → 조명 끄기 예시로 교체했다. 아래는 실제 교체 PDF에서 추출한 내용이다. 이전 습도 기반 PLAN_KO.md는 집필 이력이며 현재 그림의 기준이 아니다.

- [(a) Timeline IR](../../../overleaf-paper/figures/percom/timeline_ir_example_a.pdf)
- [(b) Plain-language rendering](../../../overleaf-paper/figures/percom/timeline_ir_example_b.pdf)
- [(c) Time-axis view](../../../overleaf-paper/figures/percom/timeline_ir_example_c.pdf)

## 전제와 대응

- 초기 문 상태는 닫힘. ContactSensor.Contact의 true는 닫힘, false는 열림이다. Switch는 현관 조명, Speaker는 안내용 스피커에 바인딩된다. (c)의 Light.On/Off는 (a)의 Switch.On/Off에 해당한다.
- 첫 wait는 열림 조건의 rising을 기다린다. 현 실행기는 첫 평가부터 조건이 참인 경우에도 rising을 발화시키므로, 이 예시의 닫힌 초기 상태를 본문에 명시했다.
- cycle의 period는 0 SEC. 본문 wait가 문 닫힘 또는 30초 timeout을 기다리므로 별도의 반복 대기는 없다.
- (a) 4–5행은 이벤트 대기, 7–14행은 cycle, 12–13행은 timeout을 가진 wait, 15행은 cycle 밖 후속 동작이다.

## (a) Timeline IR

```text
01   {
02       "timeline": [
03         {"op": "start_at", "anchor": "now"},
04         {"op": "wait", "cond": "ContactSensor.Contact == false",
05          "edge": "rising"},
06         {"op": "call", "target": "Switch.On", "args": {}},
07         {"op": "cycle", "period": "0 SEC",
08          "until": "ContactSensor.Contact == true",
09          "body": [
10            {"op": "call", "target": "Speaker.Speak",
11             "args": {"Text": "Please close the door."}},
12            {"op": "wait", "cond": "ContactSensor.Contact == true",
13             "timeout": "30 SEC"}
14          ]},
15         {"op": "call", "target": "Switch.Off", "args": {}}
16       ]
17   }
```

## (b) Plain-language rendering

```text
01   Start now.
02   Wait until the door-open condition becomes true.
03   Turn on the entrance light.
04   Repeat until the entrance door is closed:
05    Run Speaker.Speak(Text=Please close the door.).
06    Wait until the entrance door is closed
07      or 30 seconds elapse, whichever is first.
08    If closed, stop the current repeat loop.
09    Otherwise, repeat with no additional wait.
10   After the loop:
11   Turn off the entrance light.
12   Finish.
```

기존 SenSys 렌더링 규칙을 참고하도록 요청한 표현 예시다. 기존 ir_renderer.py의 자동 출력으로 주장하지 않는다. timeout, period 0에서 추가 대기가 없음, 반복 종료 후의 진행을 명시한다. 이번 확인은 PDF 내용과 코드 규칙을 읽어 대조했으며 렌더러와 IR 실행기는 실행하거나 수정하지 않았다.

## (c) Time-axis view

| 시각 | 제어 흐름 | 기기 명령 |
| --- | --- | --- |
| 0–10초 | 문 닫힘, 열림 이벤트 대기 | 없음 |
| 10초 | 문 열림, 조명 켜기 후 cycle 진입 | Light.On 다음 Speaker.Speak |
| 40초 | wait timeout, 다음 회차 | Speaker.Speak |
| 70초 | wait timeout, 다음 회차 | Speaker.Speak |
| 85초 | 문 닫힘으로 wait 해제, cycle 종료 후 후속 call | Light.Off, 종료 |

100초는 마지막 wait가 timeout되었을 시각이며 실제 실행은 85초에 끝난다. 명령을 물리 상태로 표현하지 않으며, 시간 축은 초 단위의 비례 간격이다.

## Caption

Timeline IR and its presentation and execution. (a) The IR specifies a door-opening event, a reminder cycle, and a light-off action after the cycle. (b) A plain-language view describes the same control flow. (c) The time-axis view shows how timeouts advance the cycle and door closure ends it, allowing execution to proceed to the light-off action.
