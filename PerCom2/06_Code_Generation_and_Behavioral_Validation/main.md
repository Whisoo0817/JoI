# Code Generation and Behavioral Validation

As shown in Figure 3, the LLM generates JOI code from the confirmed Timeline IR and device binding. Behavioral Explorer checks whether the IR and generated code produce the same timed action trace for every allowed initial state and timed input sequence within the specified input ranges and execution rules.

## Comparing Behavior under Shared Inputs

Timeline IR and JOI express behavior at different levels. An IR wait can directly require a condition to remain true for a duration, whereas JOI code may implement that wait through variables, conditionals, and repeated execution. Explorer uses a semantic interpreter for each representation. Each interpreter follows its own execution rules and retains its own variables, timers, and execution position. Both receive the same external input values and share a logical clock.

Each interpreter records the device commands it issues, together with their times, to form a timed action trace. Explorer compares the target, method, arguments, number, and order of commands at each time. Internal assignments and control steps need not match. In the temperature example from Section 1, an extra On() command while the temperature remains high exposes a mismatch even though the air conditioner stays on in both executions. A missing or delayed command also produces a mismatch.

To make this comparison meaningful, Explorer sets the device binding, start time, allowed initial states, and input ranges before checking. Inputs such as sensor values and device states may change at regular update times and remain constant between updates. Explorer advances logical time to the next point that can affect execution, such as an input update or timer deadline, and resumes both executions there. Each program retains its previously stored values.

## Exploring Possible Executions

Matching timed action traces for one timed input sequence does not establish equivalence. Starting from the allowed initial states, Explorer considers each possible next input, advances both executions, and compares the actions emitted at that time. It retains both programs' states and adds any resulting state or continuation not already covered to the remaining checks. Repeating this process covers successive input changes, including how earlier inputs affect later actions.

Enumerating every input value and every repetition can be expensive. Explorer reduces this work where it can preserve the behavior being compared. When input values are used only to evaluate conditions, Explorer groups values that produce the same result for every condition in both programs. For example, if the IR tests whether temperature exceeds 22 degrees and the code tests whether it exceeds 25, exploration must distinguish values at or below 22, above 22 through 25, and above 25. The middle group exposes the difference. If an input value is also used as an action argument or in another computation, Explorer checks differences in the actual values because they can change the action arguments or subsequent behavior.

Repeated execution also requires accounting for different representations of time. The IR interpreter uses timers to manage waits. JOI code can implement the same wait by counting periodic executions or by saving a start time and computing the difference from the current time. Explorer checks whether each supported implementation issues actions at the same times as the IR. For code that uses a counter, for example, it checks the initial value and the timing of increments and resets to establish how the counter corresponds to elapsed time in the IR. These relations allow Explorer to represent and check multiple states together, reducing exploration without enumerating timer and counter values individually.

## Verdicts and Feedback

Explorer reports a divergence only after replaying a timed input sequence from initialization and confirming a difference in the timed action traces. It returns the initial environment, that input sequence, and expected and actual actions. The LLM can use this evidence to revise the code; Explorer checks the revision against the same IR and binding.

Equivalence requires a completed check. All possible terminating paths must have matching timed action traces. For automations that repeat without terminating, every possible continuation must lead to states already covered by the check, with matching actions and timing. When states are grouped, these conditions must hold for all represented states. Unsupported operations, execution errors, or exhausted checking budgets leave the pair uncertified and do not authorize deployment.

VETS implements Explorer in Python and uses Z3, a tool for reasoning about expressions and constraints, to compare arithmetic expressions. Checking uses semantic interpreters without LLM calls. The equivalence guarantee applies within the specified input ranges and execution rules, assuming correct parsing, interpretation, and Z3 results. It does not establish that the confirmed IR captures the user's intent.
