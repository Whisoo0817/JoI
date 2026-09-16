# Related Work — PerCom working draft

## Behavioral specification and user confirmation

Natural-language specification systems translate requirements into temporal logic or structured intermediate forms and often involve users in resolving ambiguity. nl2spec maps natural-language fragments to temporal subformulas that users can add, remove, or revise, while ARTEMIS and related work use intermediate representations and candidate explanations to improve temporal formalization. Smart-home authoring systems such as AwareAuto and CASPER likewise make automation behavior inspectable. VETS assumes that this process has produced a correct confirmed specification; its contribution begins with using that specification as the reference for a separately generated imperative implementation.

## Smart-home automation verification

Formal analyses of trigger-action systems check safety, liveness, conflict, and security properties over rule and environment models. AutoTap synthesizes or repairs rules against temporal properties, and TAPInspector extracts timing-aware rule models, applies slicing and state compression, and model-checks safety and liveness. IoTSan, Soteria, iRuler, IoTGuard, and related systems further demonstrate that IoT code and rules can be translated into analyzable transition models. VETS does not claim that these systems lack time or executable semantics. Its verification relation compares a confirmed per-automation executable reference with a generated JoI candidate for equality of timed observable actions under one declared model.

## Reactive synthesis and translation validation

Reactive synthesis and executable temporal languages can derive implementations from formal specifications, while translation validation checks whether a particular compilation result preserves a source program. VETS adopts the latter reference-centered perspective for LLM lowering: each generated candidate is checked against the confirmed Timeline rather than trusted because it follows a prompting template. Unlike an export to NuSMV or another model-checker language, the present implementation jointly explores the Timeline and JoI semantic interpreters. This design avoids a separate code-to-model-checker translation but still relies on faithful interpreters and justified abstraction.

## Execution-time policy checking and LLM evaluation

Runtime systems such as AgentSpec and VIGIL check policies against observed agent or tool-call traces, and HAWatcher detects deviations from learned invariants. Their contracts concern observed executions or policy satisfaction; VETS asks about the generated program across modeled input histories before deployment. LLM-as-a-judge research has also shown that code scores can change under meaning-irrelevant surface variation. We use that evidence to motivate execution-based validation and study trace-equivalent reactive-temporal idioms separately; general code-judge surface bias itself is not our claimed discovery.

**[FINAL PRIMARY-SOURCE CITATIONS AND BIBTEX KEYS PENDING]**
