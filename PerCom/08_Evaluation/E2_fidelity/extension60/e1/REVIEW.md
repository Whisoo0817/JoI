# Static review of the frozen 48 E1 variants

Reviewed 2026-09-18 after pair freeze, without reference or Explorer execution. This review does not change the frozen source set or assign outcome labels. Read: the original pair scripts and declared mutation allocation, original generator/source, E2 protocol, and binding decision including B2/B5.

## Admissibility

All 48 scripts passed the deployment ANTLR grammar. Inspection found no newly invalid service, selector, method, argument count, or literal type. Every added action is an exact duplicate of an action in its original intended implementation. Timing edits use existing nonnegative integer delays/counters; guard edits compare the same existing values; stored-value edits assign compatible numeric values or remove an update. Missing actions are replaced by an unused local numeric assignment (`extension_noop = 0`) to preserve control-flow blocks. No original script uses that variable. The one order mutation exchanges two existing zero-argument announcement methods and preserves their delays.

These checks do not certify original base correctness, whole-language execution support, or behavioral inequivalence. Existing base defects or engine limitations can remain. Some families deliberately use the same conceptual edit at two occurrences: the duplicated phase-1 deadline/motion updates in E1-099; the common watering duration in E1-086. Counts and exact edits are recorded, so these are not concealed independent edits.

## Review by base

Suffix numbers refer to `ext60-fault1`, `ext60-fault2`, and where allocated `ext60-fault3`.

| Base | Mutation review | Conditions that can hide differences |
|---|---|---|
| C01 | 1 omits initial On; 2 duplicates eventual Off; 3 delays initial On by one second. All affect distinct intended execution points. | No initial armed motion event; no timeout; horizon ends before the modified event. |
| C03 | 1 omits On; 2 duplicates On; 3 changes the high-CO2 boundary to include 1000. | No qualifying event; threshold equality never occurs after readiness; original branch readiness may absorb the initial equality. |
| C04 | 1 omits initial On; 2 duplicates it; 3 delays it. No argument or selector changes. | A sufficiently short or unsupported checked horizon can prevent useful comparison. For a normal nonempty run the intended initial action is changed. |
| C05 | 1 omits only the first alert; 2 duplicates only the first alert; 3 doubles the repeat interval. Context anchors distinguish first and repeat call sites. | Door never remains open long enough; no second alert fits the horizon. |
| C07 | 1 omits initial dimming only; 2 reduces inner blink count; 3 stores zero instead of initial brightness. | Sustained-open/night guard never passes; blink group ends early; initial brightness actually equals zero. |
| C09 | 1 omits Lock; 2 delays Lock; 3 tests absence instead of presence in the ready branch. All retain syntax and state initialization. | No relevant readiness/arrival or subsequent absence sequence. |
| C11 | 1 omits vacuum idle action; 2 removes previous-vacuum-state update. | No curtain-opening transition; previous vacuum value never affects a later guard. |
| C15 | 1 omits On; 2 duplicates Off. | No arrival during night; presence never clears before the horizon. |
| C16 | 1 omits Off; 2 delays Off. | Initial conjunction is false. B5 may also select bindings that affect this conjunction; no universal label follows from the tag-rule branch alone. |
| C18 | 1 omits Unlock; 2 duplicates Lock. | No eligible button edge at hour 15; relock lies beyond horizon. |
| C19 | 1 omits mail; 2 duplicates mail. | No qualifying arrival before deadline. |
| C20-O | 1 omits On; 2 duplicates On. | Window never opens or no qualifying darkening occurs before exit/timeout. |
| E1-028 | 1 duplicates Dispense; 2 records second-slot timestamp as zero. | No admitted dispense; second slot is unused; zero equals the actual timestamp; no later eligibility test distinguishes the timestamp. |
| E1-034 | 1 omits warning; 2 halves continuous-on threshold. | Oven never stays on long enough or relevant actions lie beyond horizon. |
| E1-062 | 1 omits living-room On; 2 removes previous-office-switch update. | No corresponding transitions; B5 can change which input stream the selector observes, so the altered tag-rule transition is not by itself a universal witness. |
| E1-072 | 1 duplicates full arrival fan-out; 2 removes the daylight requirement on departure. | No qualifying arrival/departure. B2 preserves duplicate-call multiplicity, including repeated fan-outs; duplication is not erased merely because devices share a binding set. |
| E1-086 | 1 omits zone-2 Open; 2 halves both zone durations as a shared duration fault. | Cancellation before zone 2 or before the changed deadlines. B5 remaps selectors but does not automatically erase a missing call or changed action time. |
| E1-092-A | 1 omits tasks; 2 swaps news and alarm-setting announcements while retaining delays. | Shutdown trigger absent. B5 does not erase ordering between distinct method names. |
| E1-092-B | 1 omits lock; 2 duplicates alarm Set. | Shutdown trigger absent or horizon ends early. |
| E1-095 | 1 retains only latest chlorine sample; 2 doubles sample-count increments. Numeric operations remain well typed; count guard still avoids division by zero. | No report; values make the altered average coincide (for example zero totals); original sampling trajectory is not exercised. |
| E1-099 | 1 extends initial deadline; 2 substitutes zero for motion timestamp, at both copies of the same lowered phase block. | No deadline/off event; no motion or later guard sensitive to timestamp; start time and history keep the same comparison truth values. |

## Equivalence interpretation

No variant was proven necessarily behaviorally equivalent by this static review. Conversely, none is labeled definitely divergent: the reference checks finite histories, the base is only author-intended, and B5 quantifies over selector assignments. `REF-EQUIV-CHECKED` may reflect missing triggering histories, equal coincidental values, unreachable changed branches, or contract-level equivalence. Report each outcome as measured and retain all 48. This extension adds variants of existing requests, not additional requests.

## Runner review status

The runner was inspected statically after it became available; no runtime evaluation was performed by this reviewer.


### Cache and protocol audit

Runner SHA-256 inspected: `7449629e2a352e4c8e8cb5970fafdca62c145c2229c6d59942994288407db95d`.

- `install_ir_cache` serializes all public `run_ir` positional and keyword arguments, including IR, binding, inventory, event values/order/times, horizon, catalog path, start time, cron, and binding-decision flag. It does not key only by case/history name. JSON serialization preserves mapping insertion order, which matters for fixed binding and inventory semantics. JSON tuple-to-list conversion is compatible with these JSON-backed input structures and event sequences.
- Each cache return is deep-copied, avoiding consumer mutation of the cached result. Cache scope is the worker group; the original function is restored afterward, preventing wrapper accumulation. Catalog content is not in the per-call key but is locked by runtime/input metadata; this depends on the stated frozen-file discipline.
- B5 selector assignments affect the JoI execution, not `run_ir`; omitting a JoI assignment from the IR cache key is correct. The runner delegates assignment enumeration/folding to unmodified `run_e2.reference_side`, with binding decision and assignment flags asserted enabled. It does not share JoI results between assignments.
- Original histories are passed intact to `run_pair`. Supplementary histories run only after original-history `REF-EQUIV-CHECKED`; only a supplementary divergence changes the combined reference label. Supplemental unsupported/error results remain explicitly recorded. This matches `run_binding_v1.work` and the historical conditional policy.
- Inherited limitation: original and supplementary B5 calls quantify assignments separately. They may find different equal assignments on the two sets. The combined label is therefore the historical fold, not evidence of a single assignment equivalent on their union. This is not a new runner regression.
- Resume locks include runtime freeze, pair/history/supplement file hashes, catalog hashes, selected IDs, settings and stage. Reusing a result file with changed inputs is rejected.
- Source-freeze coverage observation: the inspected `runtime_files()` includes Explorer, timeline_ir, grammar, reference and E1 Python files, but omits the `lowering` tree. The deployment generated parser is in `lowering/parser/generated`; include its dependencies if full transitive source coverage is claimed. This is a provenance coverage issue, not evidence that the cache or current execution changed behavior. Reported to the parent before execution freeze.

No cache-key or conditional-supplement behavior defect was found in this static audit. An independent cached-versus-uncached smoke check remains the executor team's responsibility. No frozen pair sources were changed during review.
