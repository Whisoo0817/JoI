# Experiment Plan

## Context

- **Problem:** establish whether a confirmed Timeline IR can serve as an executable behavioral reference for LLM-generated reactive-temporal IoT code.
- **Evaluation goal:** support only the approved C1–C5 claims with the smallest decisive set: E1 conformance, E2 adequacy, E3 equivalence discrimination, and E4 scalability/frontier.
- **Operating mode:** standalone advisor pack; no experiment execution in this phase.
- **Upstream artifacts:** Phase 0 logic/scope, Phase 1 literature and PerCom pattern map, Phase 2 claims, Phase 3 formal decisions.
- **Constraints:** one backend; finite model/bounds; no intent/usability/physical/unbounded/repair/portability claim; no active optional extension.
- **Dominant contribution:** user-confirmed executable Timeline IR plus reachable-history IR/code observable-behavior comparison.
- **Critical reviewer concerns:** circular oracle, boundedness language, favorable corpus/fault selection, generalization, implementation fidelity, incomplete outcome suppression.
- **Current evidence class:** exploratory; predecessor evidence only.
- **Requested evidence class:** confirmatory for the frozen E1–E4 protocols.
- **Selection history:** selected before observing any new-OVLA result.
- **Material predecessor failures:** old mutation/replay evidence does not validate the redesigned semantics/Explorer; earlier reviewers challenged breadth, determinism, bounds, and systems motivation.

## Claim Map

| Claim ID | Type | Why it matters | Minimum convincing evidence | Anti-claim to rule out | Falsifier | Decision if unproven |
| --- | --- | --- | --- | --- | --- | --- |
| EC-01 | primary | Supports behavioral verification and implementation fidelity | E1 independent conformance plus E3 independently labeled positive/negative pairs | self-oracle, mutation-only evidence, incomplete-search passes | semantic discrepancy, exact-case false accept/reject, leakage, or pass with frontier | narrow/reframe |
| EC-02 | primary | Supports bounded expressive and practical scope | E2 frozen taxonomy/external corpus plus E4 preregistered factorial/real-anchor frontier | favorable corpus and median-only scalability | unstable taxonomy, hidden exclusions, missing outcomes, or uncharacterized frontier | narrow/reframe |

## Experimental Storyline

| Block | Role | Paper placement | Why it exists |
| --- | --- | --- | --- |
| E1 | semantic non-vacuity and implementation foundation | methods/evaluation, mandatory | The reference interpreter must be trustworthy before it labels E3. |
| E2 | supported-domain boundary | evaluation, mandatory | Defines what “adequate” means and supplies representative anchors. |
| E3 | main verification evidence | evaluation anchor, mandatory | Tests equality and divergence on independent positive/negative cases. |
| E4 | practical finite-scope frontier | evaluation, mandatory | States where exhaustive bounded exploration completes and what it costs. |

PerCom alignment is achieved inside these four blocks: real pervasive cases enter E2/E4; independent controls and failure accounting enter E1/E3; resource/tail measurements enter E3/E4. There is no fifth block.

## Non-Vacuity Preflight

- **Discriminating cases:** E1 must catch seeded faults in timer ties, reentry, merge order, missing values, and conflicts; E3 must include one syntax-different equivalent pair and one deep-history divergent pair.
- **Plausible comparator outcome:** the checker should accept the positive pair and return the shortest canonical counterexample for the negative pair under identical inputs.
- **Complete loss contract:** success, discrepancy, false accept/reject, invalid, error, skip, null, retry, timeout, OOM, and incomplete frontier are retained.
- **Case-selection independence:** freeze semantics, taxonomy, corpus, gold pairs, factor grid, normalization, hardware, and thresholds before confirmatory outcomes.
- **Gate result:** planned; it becomes `pass` only after the stated pilot discriminators work. The pilot calibrates feasibility, not confirmatory thresholds from desired outcomes.

## Experiment Blocks

### E1 — Interpreter conformance

- **Claim/reviewer question:** EC-01; does the implementation conform to frozen semantics without circular self-checking?
- **Minimum protocol:** property-generated well-formed AST/state/event cases; permutation and merge-law tests; explicit boundary suite; exhaustive successor uniqueness on small models; differential comparison with an independently implemented evaluator.
- **Decisive metrics:** discrepancy/uniqueness/merge-law violations, construct-combination coverage, invalid-case rate, runtime distribution.
- **Necessary control:** seeded faulty interpreter variants and independently reviewed expected boundary outcomes.
- **Criterion:** zero unresolved discrepancies in the frozen suite; uncertainty bounds still reported.
- **Failure:** block EC-01, repair/version, and rerun; never explain away a failed stratum.
- **Paper artifact:** construct-by-boundary conformance matrix and discrepancy table.

### E2 — Expressive adequacy

- **Claim/reviewer question:** EC-02; what declared reactive-temporal space is represented exactly, partially, or not at all?
- **Minimum protocol:** freeze taxonomy before scoring; use the predecessor corpus only with provenance, add an independently sourced corpus and unsupported negative controls; two independent technical annotations plus adjudication.
- **Decisive metrics:** exact/partial/unsupported rates with Wilson CIs by construct and combination, agreement/adjudication, unsupported reasons.
- **Necessary control:** unsupported cases that must not be labeled exact; external cases selected before scoring.
- **Criterion:** report category-specific evidence rather than impose a universal coverage threshold.
- **Failure:** narrow the target behavior-space claim; do not add operators after seeing failures within the same confirmatory round.
- **Paper artifact:** behavior-space taxonomy and stratified adequacy table.

### E3 — IR–code equivalence verification

- **Claim/reviewer question:** EC-01; does the checker recognize both behavior-preserving implementation variation and real divergence?
- **Minimum protocol:** positives from behavior-preserving transforms and independent implementations; negatives from frozen genuine LLM failures, held-out non-IR-derived faults, and stratified mutants; exact small-model gold labels; dense replay as secondary cross-check.
- **Decisive metrics:** false accepts, false rejects, 95% CIs, completion/errors/timeouts, fault class, counterexample length, median/p95/max latency.
- **Necessary control:** labels frozen before checker output; no expected-trace/fault-label access; clean execution state and identical timed inputs.
- **Criterion:** zero errors on completed exact gold cases for the strong bounded claim; statistical bounds and scope remain explicit.
- **Failure:** false accepts block the strong claim; false rejects or incompletion narrow it.
- **Paper artifact:** effectiveness table plus representative shortest counterexample.

### E4 — Explorer scalability

- **Claim/reviewer question:** EC-02; what finite models and bounds complete under stated time/memory resources?
- **Minimum protocol:** factorial synthetic generator varying state-domain, events, timers, rules, AST depth, and horizon; multiple structural instances; preselected E2 real-workload anchors; exact BFS or history-tree fallback according to adapter state completeness.
- **Decisive metrics:** states/histories, transitions, time, peak RSS, frontier, completion class, median/p95/max.
- **Necessary control:** immutable factor grid, fixed timeout/memory cap, randomized run order, raw process metrics.
- **Criterion:** a reproducible completed/incomplete frontier, not a speedup claim.
- **Failure:** narrow the practical envelope; semantic determinism remains a separate theorem.
- **Paper artifact:** capacity-frontier heatmap/table with real-anchor overlay and all timeout cells.

## Run Order

| Order | Block | Purpose | Dependency | Gate ID | Stop / go gate | Est. cost |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | E1 | establish trustworthy reference execution | formal freeze | G-E1 | do not use interpreter as E3 oracle until pass | 1 workstation-day after pilot |
| 2 | E2 | freeze and measure supported behavior scope | E1 semantic contract | G-E2 | narrow taxonomy/claim if systematic gaps | annotation team budget |
| 3 | E3 | decisive equivalence discrimination | E1 and E2 | G-E3 | block/narrow EC-01 on any exact-case error | 2 workstation-days after pilot |
| 4 | E4 | characterize completion/resource frontier | E1 and E2 | G-E4 | report bounded frontier; stop at fixed caps | 3 workstation-days |

## Decision Gates

| Gate ID | Opens after | Decision question | Proceed if | Revise if | Stop if |
| --- | --- | --- | --- | --- | --- |
| G-E1 | E1 | Can the interpreter serve as reference implementation evidence? | frozen suite has zero discrepancies and full declared coverage | oracle/semantics/version is repaired and rerun | unresolved discrepancy remains |
| G-E2 | E2 | Is the declared behavior-space claim evidence-bearing? | all strata and unsupported outcomes are reported | narrow taxonomy/claim and version a new round | provenance or annotation independence fails |
| G-E3 | E3 | Does evidence support the bounded checker claim? | zero exact-case errors and honest completion accounting | narrow fault/construct/model scope | leakage or unresolved false accept remains |
| G-E4 | E4 | Is practical bounded scope characterized? | all grid outcomes and real anchors are accounted | rerun only preregistered technical failures | missing/selectively removed outcomes prevent a frontier |

## Risks and Confounds

- **Self-oracle:** separate evaluator and independent boundary review.
- **Fault leakage/easy mutants:** genuine LLM and held-out non-IR-derived faults; freeze split and labels.
- **Favorable expressiveness corpus:** independent corpus, negative controls, exact/partial/unsupported outcomes.
- **State-merging unsoundness:** require full product-state serialization or use history-tree fallback.
- **Post-outcome thresholding:** freeze criteria after development-only pilot; version any change.
- **Legacy-result contamination:** old results are motivation/candidate provenance, never new-system evidence.
- **PerCom realism pressure:** use real anchors and hardware resource subconditions inside E2/E4 without adding physical-correctness or portability claims.

