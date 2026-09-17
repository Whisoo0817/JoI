# Timeline IR — PerCom working draft

Timeline IR connects user confirmation to the behavioral check of generated code. It specifies the temporal behavior of one automation through explicit operators and parameters. The LLM proposes a candidate, which the user may edit or ask the LLM to revise before confirmation. Once confirmed, the same IR guides code generation and provides the executable behavioral reference. Timeline specifies time, state, and control flow, while the confirmed binding identifies the target devices.

\textbf{A concrete example.} Consider the request, "Starting now, if the living-room temperature stays above 25°C for three minutes, set the living-room air conditioner to cooling mode once." The following JSON uses the implemented IR syntax and service catalog.

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

The threshold appears in `cond`, the continuous duration in `for`, and the requested operation in `call`. The sequence ends after that call, making the request one-shot. If the condition becomes false before the wait completes, its accumulated duration is discarded. For example, suppose the condition is true on $[0,120)$ seconds, false on $[120,150)$, and true thereafter. The call occurs at 330 seconds. The user reviews these choices and the device binding before confirmation. Intent-correct confirmation remains an assumption, and this example does not establish readability or confirmation accuracy.

\textbf{Operators and structure.} Structurally, an IR is a typed tree serialized as a JSON object whose steps carry an `op` tag. A `timeline` begins with `start_at` and contains an ordered sequence of steps. Branches and cycle bodies contain further sequences. The operators map temporal and control choices to named fields, as summarized below.

| Operator | Principal fields | Execution meaning |
| --- | --- | --- |
| `start_at` | `anchor`, `cron` | Select the start anchor. |
| `wait` | `cond`, `edge`, `for`, `timeout`, `on_timeout` | Wait for a level, an observed edge, or a sustained condition, with an optional timeout. |
| `delay` | `duration` | Suspend unconditionally for a duration. |
| `read` | `var`, `src` | Save the value read at this point. |
| `call` | `target`, `args`, optional `var` | Emit an ACTION, or save the result of an approved read-only query. |
| `if` | `cond`, `then`, `else` | Select one branch when reached. |
| `cycle` | `period`, `count`, `until`, `body` | Repeat a body with a post-completion interval and optional stopping condition. |
| `break` | none | Exit the enclosing cycle. |

*Table caption: Timeline IR operators.*

Conditions combine typed service values, stored variables, and arithmetic or Boolean expressions. A service reference reads the current input, whereas `$x` uses the snapshot previously saved in `x`. For example, a `read` followed by a `delay` can support a later comparison with the earlier value. The preparation checks resolve service names and types, validate arguments, and reject unsupported combinations, including an edge wait with a positive sustain duration. The IR has sequential control within one automation, without parallel branches.

\textbf{Execution rules.} Execution preserves stored values and the selected continuation across waits. An `if` condition is evaluated when the branch is entered, rather than re-evaluated when a delay inside that branch resumes. An edge wait updates its history only when that wait is evaluated. A rising-edge wait therefore fires on its first evaluation if the condition is already true, and its history persists across cycle iterations. A `cycle` initializes its counter on entry and increments it after each completed iteration. If an iteration completes at $t_c$ with period $d$, the next iteration becomes eligible at $t_c+d$. The period is a delay after completion, rather than a fixed-rate start schedule. For a cron anchor, preparation checks agreement with the candidate code and evaluates one invocation at the common start time.

\textbf{Reaction and timed trace.} Fix the execution model $M$, including the binding, typed input domains, initial-state policy, start time $t_0$, and input interval $\Delta$. The model also fixes typed operations, evaluation order, and store updates. Derived clocks depend on logical time, and external inputs do not overwrite program-owned globals. An input history $u$ supplies a snapshot at each $t_0+n\Delta$, held until the next update. Event times are exact integer milliseconds, and internal deadlines are not rounded to the input grid. A state $s$ records the continuation, stored values and relevant global variables, timers, edge history, cycle state, and termination status. We write

\[
\langle I,M,s,u_n,t\rangle\Downarrow(s',A),
\qquad n=\left\lfloor\frac{t-t_0}{\Delta}\right\rfloor,
\]

for a reaction that applies the current input and then executes until blocking or termination, producing the ordered ACTION sequence $A$. When an input update coincides with a deadline, the input is applied first. Thus a false condition at a sustain deadline cancels the wait, while an unconditional delay still expires. Concatenating these ACTION sequences with their reaction times gives the timed trace $\operatorname{Tr}_M(I;g_0,u)$, where $g_0$ is the allowed initial global-variable environment. Termination produces no further ACTIONs.

\textbf{Proposition D (input-determinism).} For a prepared Timeline IR $I$ under the supported semantics, each reaction from fixed $M,s,u_n,t$ has at most one normal result:

\[
\begin{aligned}
&\langle I,M,s,u_n,t\rangle\Downarrow(s_1,A_1),\\
&\langle I,M,s,u_n,t\rangle\Downarrow(s_2,A_2)\\
&\hspace{1em}\Longrightarrow\quad s_1=s_2\ \land\ A_1=A_2.
\end{aligned}
\]

Consequently, for fixed $I,M,g_0,u$, execution has a unique timed ACTION trace provided each reaction completes normally in finitely many internal steps and the run either advances logical time without a finite accumulation point or terminates and remains silent.

\textbf{Proof sketch.} At fixed state, input, and time, expression values and the continuation determine at most one normal internal step. Induction over internal steps gives reaction uniqueness. The event policy then selects the least subsequent input-grid point, active deadline, or required clock boundary. Induction over reactions gives equal finite timed trace prefixes, and the progress assumption extends equality to complete traces. The compact appendix provides the operator cases and induction argument.

This is a property of the declared execution semantics. The argument relies on the frontend and interpreter implementing those rules, rather than a machine-checked proof of the full implementation. Errors, unsupported cases, and exhausted execution limits do not count as normal silent termination. Section 6 uses this unique reference behavior to check the generated code.

---

## 편집 메모 (논문 본문 아님)

- 본문 배치안: 실제 JSON 예제 + 8개 operator 표 + 실행 의미 + D 정리·증명 개요를 유지한다. 제출 원고 부록은 `DETERMINISM_APPENDIX_COMPACT.md`의 연산자별 유일성·반응 및 trace 귀납 증명으로 압축했다. 전체 operator/식 문법과 상세 증명은 `SYNTAX_AND_DETERMINISM_APPENDIX.md`에 별도 보존한다.
- 예제 원본은 `examples/sustain_once.json`. 실제 서비스명과 enum `cool`을 사용한다. 기존의 임의 `AC.on()` 표기를 넣지 않았다. 작은 실행 trace는 설명용이며 사용자 연구나 표현 범위 평가 결과가 아니다.
- SenSys의 "Structurally, an IR is a typed tree", 명시적인 control dimension과 operator 소개는 유지·축약했다. rendering 기반 확인·bounded horizon·finite-state 단정은 현재 계약에 맞춰 제외했다.
- `PRESENTATION_CANDIDATES.md`에 원문 위치와 세 가지 배치 후보를 기록했다. 이 논문들은 표현 방식의 참고자료이지 Timeline의 의미론이나 가독성 주장을 뒷받침하는 인용이 아니다.
- D는 §5, Explorer의 인증 soundness S는 §6에 둔다. 저장소/관측 정규화의 세부 비교 규칙은 §6에서 설명한다.
- 이 파일에는 변경 색상용 `**`를 넣지 않았다. `\textbf`는 문단 리드인이다. `overleaf-paper/sections/timeline-ir.tex`와 `sections/timeline-ir-appendix.tex`에 검정색 LaTeX로 반영한다. PerCom 2027은 부록을 포함한 기술 내용 9쪽과 참고문헌 전용 추가 1쪽을 허용하므로, 나머지 절을 작성한 뒤 전체 분량을 다시 점검한다.
