# Timeline IR — PerCom working draft

Timeline IR specifies the behavior of one automation through explicit operators for time, stored values, and control flow. These operators express behavioral units that imperative code may implement across multiple statements, such as waiting for a condition to remain true for a specified duration. The user confirms the IR and target-device binding, after which the IR guides code generation and provides the executable reference for checking its behavior.

\textbf{A concrete example.} Consider the request, "Starting now, if the living-room temperature stays above 25°C for three minutes, set the living-room air conditioner to cooling mode once."

```json
{"timeline": [
  {"op": "start_at", "anchor": "now"},
  {"op": "wait",
   "cond": "TemperatureSensor.Temperature > 25",
   "edge": "none", "for": "3 MIN"},
  {"op": "call",
   "target": "AirConditioner.SetAirConditionerMode",
   "args": {"Mode": "cool"}}
]}
```

The `wait` requires the condition to remain true for three minutes, restarting the duration if it becomes false. The following `call` sets the cooling mode, after which the sequence ends.

\textbf{Operators and structure.} A `timeline` is an ordered sequence of JSON steps, each identified by an `op` field. It begins with `start_at` and composes the operators below through sequential execution, branches, and cycles. Branches and cycle bodies contain further sequences, with no parallel branches within one automation.

| Operator | Principal fields | Execution meaning |
| --- | --- | --- |
| `start_at` | `anchor`, `cron` | Set the start time. |
| `wait` | `cond`, `edge`, `for`, `timeout`, `on_timeout` | Wait for a condition, an observed change, or a sustained condition, with an optional timeout. |
| `delay` | `duration` | Wait for a duration. |
| `read` | `var`, `src` | Save the current value for later use. |
| `call` | `target`, `args`, optional `var` | Issue an action, or save a query result. |
| `if` | `cond`, `then`, `else` | Select a branch using the current condition. |
| `cycle` | `period`, `count`, `until`, `body` | Repeat a body, waiting `period` after each completion, with an optional count or stop condition. |
| `break` | none | Exit the enclosing cycle. |

*Table caption: Timeline IR operators.*

\textbf{Execution and action trace.} A reaction executes the IR at a given logical time until it must wait or terminates. The execution state $s$ retains the current position, stored values, and waiting and repetition state. The fixed execution model $M$ defines the operator rules, allowed inputs, initialization, and event timing. An input history $u$ gives values at regular update times and holds them between updates. If an update coincides with a timer deadline, the new input is applied first.

We write $\langle I,M,s,u(t),t\rangle\Downarrow(s',A)$ for a reaction at time $t$ that produces the next state $s'$ and ordered action sequence $A$, using the current input $u(t)$. Collecting these actions with their execution times gives the timed action trace $\operatorname{Tr}_M(I;g_0,u)$, where $g_0$ specifies the initial global-variable values. A reaction may emit no action, and termination produces no further actions.

\textbf{Proposition D (input-determinism).} For a supported Timeline IR $I$ that passes preparation checks, each reaction from the same state, input, and time under $M$ has at most one normal result:

\[
\begin{aligned}
&\langle I,M,s,u(t),t\rangle\Downarrow(s_1,A_1),\\
&\langle I,M,s,u(t),t\rangle\Downarrow(s_2,A_2)\\
&\hspace{1em}\Longrightarrow\quad s_1=s_2\ \land\ A_1=A_2.
\end{aligned}
\]

Consequently, fixed $I,M,g_0,u$ determine a unique timed action trace, provided each reaction completes normally in finitely many steps and only finitely many reactions occur in any finite time interval. Thus the same initial state and input history produce the same actions, in the same order and at the same times.

\textbf{Proof sketch.} Fixed values and operator rules determine each next step, so induction over the steps gives a unique reaction result. The resulting state and event policy determine the next reaction time. Repeating the argument gives identical timed trace prefixes, and the progress assumptions extend this equality to the complete trace. The compact appendix gives the detailed proof.

The argument assumes that the frontend and interpreter implement the declared rules. Errors and exhausted execution limits are excluded from normal execution. Section 6 uses this unique reference behavior to check the generated code.

---

## 편집 메모 (논문 본문 아님)

- 사용자 피드백 반영: operator 구성 이유 한 문장 + 짧은 JSON 예제 + 8개 operator 표 + action trace 정의 + D 정리·증명 개요로 축약했다. 별도 Execution rules 문단과 service/type 검사, `$x`, clock/global 관리, readability 단서와 binding 중복을 삭제했다. `cycle.period`의 완료 후 대기는 표에만 설명한다. 예제는 전체 분량에 따라 추후 삭제할 수 있다.
- 제출 원고 부록은 `DETERMINISM_APPENDIX_COMPACT.md`를 유지한다. 전체 operator/식 문법과 상세 증명은 `SYNTAX_AND_DETERMINISM_APPENDIX.md`에 별도 보존한다. 본문의 $u(t)$는 시각 $t$에서 유지되는 입력값을 뜻한다.
- 예제 원본은 `examples/sustain_once.json`. 실제 서비스명과 enum `cool`을 사용한다. 기존의 임의 `AC.on()` 표기를 넣지 않았다. 작은 실행 trace는 설명용이며 사용자 연구나 표현 범위 평가 결과가 아니다.
- SenSys의 "Structurally, an IR is a typed tree", 명시적인 control dimension과 operator 소개는 유지·축약했다. rendering 기반 확인·bounded horizon·finite-state 단정은 현재 계약에 맞춰 제외했다.
- `PRESENTATION_CANDIDATES.md`에 원문 위치와 세 가지 배치 후보를 기록했다. 이 논문들은 표현 방식의 참고자료이지 Timeline의 의미론이나 가독성 주장을 뒷받침하는 인용이 아니다.
- D는 §5, Explorer의 인증 soundness S는 §6에 둔다. 저장소/관측 정규화의 세부 비교 규칙은 §6에서 설명한다.
- 이 파일에는 변경 색상용 `**`를 넣지 않았다. `\textbf`는 문단 리드인이다. `overleaf-paper/sections/timeline-ir.tex`와 `sections/timeline-ir-appendix.tex`에 검정색 LaTeX로 반영한다. PerCom 2027은 부록을 포함한 기술 내용 9쪽과 참고문헌 전용 추가 1쪽을 허용하므로, 나머지 절을 작성한 뒤 전체 분량을 다시 점검한다.
