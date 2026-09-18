# Remaining72 E1 reference execution

> **Author-review correction (2026-09-19):** The author confirmed personally reviewing all 72 extension cases. Earlier statements that these cases had not received author review were incorrect. Agent preparation and author review are both part of the record. The initial execution counts and raw candidate labels below remain historical records.

> **Follow-up, 2026-09-18:** E1-024 now has an ordinary Timeline IR rolling-budget implementation: original3/3 plus9/9 expiry/boundary histories. See [the revision](e1_024_rolling/README.md) and [raw results](e1_024_rolling/results.json). The71/72 and239/241 counts below describe the preserved initial candidates. Substituting this revision on the same original histories yields72/72 and241/241, subject to the recorded interpretations and integer-second scope. The initial raw results remain unchanged.

All72 requests were attempted. 71/72 candidates reproduced every frozen history; 239/241 histories matched exactly. Interpretation drafts were prepared by Astra agents using source records and the prior20. The author also personally reviewed all 72 cases, as confirmed on 2026-09-19.

## What this result means

The measured unit is a request under its explicitly frozen interpretation, not every possible interpretation of the source. The original20 remain unchanged. These72 extend the in-scope cohort to92 requests. The initial candidate results below precede the E1-024 revision; the current final aggregate is 92 requests and 294/294 main histories. The language, fixed selections, waveform assumptions, independently deployed Timelines and other qualifications are retained in per-case records. These are finite test histories, not all-input verification or physical-device validation.

E1-024 is a partial candidate: a conservative single-session cooldown matches1/3 histories and fails the two legal split-session/cumulative-budget histories. The demand-serving interpretation adds an availability obligation beyond the source's literal never-exceed safety constraint: refusing legal requests could satisfy that literal safety property. Thus the two failures concern the declared stronger interpretation, not an inherent source or IR impossibility. A separately executed JoI mutable-accumulator fallback matches3/3 on these shorter-than48h histories; it does not implement general rolling-window expiry and is not claimed complete.

## Main frozen cohort

| Batch | Requests | Exact histories |
|---|---:|---:|
| batch_er | 33 | 97/99 |
| batch_official | 22 | 90/90 |
| batch_community | 17 | 52/52 |

## Supplemental diagnostics kept separate

- `batch_community/runs/sensitivity_results.json`: 4/4 exact after repairs; these are additional diagnostics on existing cases, not new requests or additions to the241 main histories.
- `batch_er/sensitivity/runs/results.json`: 4/4 exact after repairs; these are additional diagnostics on existing cases, not new requests or additions to the241 main histories.

Known pre-repair failures and encoding changes are retained in each batch archive. Parent review exposed gaps after candidates passed their initial histories; expectations were frozen before those repairs. A main-cohort pass therefore must not be promoted to an all-input semantic guarantee.

## Bias and scope

- The same project and related agents developed assumptions, expected traces and encodings, although expectations were hashed before encoding. The author personally reviewed all 72 cases. Temporal freezing and author review are recorded as distinct parts of the procedure.
- Prior20 conventions guide event/startup/reentry and property-to-controller choices; assumptions can make a requirement easier or narrower. Alternatives are recorded rather than counted as validated.
- Official examples were checked against live2026-09-17 source after the corpus2026-09-13 freeze. Source drift, especially E1-068 prose versus YAML, is disclosed; this is not a claim that every live variant equals the frozen normalization.
- E1-078 adopts manual-rearm lockout; E1-089 follows the source startup priority with overlapping thresholds. These material interpretations are visible in the community batch.
- E1-020 controls serialized admitted starts under an observed acknowledged lifecycle; it does not prove mutual exclusion for uncontrolled external starts. E1-031 uses a fixed two-use phase representation, not general history aggregation.
- Fixed waveform, selected device sets and independent flow decomposition do not establish arbitrary cardinality, physical fading, joins or shared-state concurrency.
- Typed fixtures expose raw observations and atomic output leaves. Timing and controller decisions are encoded in IR. No Explorer verdict enters the result.
- Legacy T5 groups equal-time actions as an unordered multiset; raw action order and ordered comparison diagnostics remain available. Calendar tests using clock comparisons do not establish unrelated scheduler reliability.

## Reproduce

```sh
/home/gnltnwjstk/temp/bin/python PerCom/08_Evaluation/E1_adequacy/breadth/remaining72/run_batch.py batch_er
/home/gnltnwjstk/temp/bin/python PerCom/08_Evaluation/E1_adequacy/breadth/remaining72/run_batch.py batch_official
/home/gnltnwjstk/temp/bin/python PerCom/08_Evaluation/E1_adequacy/breadth/remaining72/run_batch.py batch_community
/home/gnltnwjstk/temp/bin/python PerCom/08_Evaluation/E1_adequacy/breadth/remaining72/summarize.py
```

Run batch-specific sensitivity/fallback commands from their READMEs to reproduce supplemental records. `summary.json` records operator composition trees and nesting paths for all72. These are measured compositions, not a claim to cover every possible operator combination.

## Case outcomes

| Case | Exact histories | Recorded candidate label |
|---|---:|---|
| E1-013 | 3/3 | complete under agent-fixed interpretation |
| E1-014 | 3/3 | complete under agent-fixed interpretation |
| E1-016 | 3/3 | complete under agent-fixed interpretation |
| E1-019 | 3/3 | complete under agent-fixed interpretation |
| E1-020 | 3/3 | complete for serialized request admission with acknowledged lifecycle |
| E1-021 | 3/3 | complete under agent-fixed interpretation |
| E1-022 | 3/3 | complete under agent-fixed interpretation |
| E1-023 | 3/3 | complete under agent-fixed interpretation |
| E1-024 | 1/3 | partial: conservative one-session cooldown |
| E1-025 | 3/3 | complete under agent-fixed interpretation |
| E1-026 | 3/3 | complete under agent-fixed interpretation |
| E1-029 | 3/3 | complete under agent-fixed interpretation |
| E1-030 | 3/3 | complete under agent-fixed interpretation |
| E1-031 | 3/3 | complete for fixed-two raw-event interpretation |
| E1-032 | 3/3 | complete under agent-fixed interpretation |
| E1-033 | 3/3 | complete under agent-fixed interpretation |
| E1-035 | 3/3 | complete under agent-fixed interpretation |
| E1-038 | 3/3 | complete under agent-fixed interpretation |
| E1-039 | 3/3 | complete under agent-fixed interpretation |
| E1-040 | 3/3 | complete under agent-fixed interpretation |
| E1-041 | 3/3 | complete under agent-fixed interpretation |
| E1-042 | 3/3 | complete under agent-fixed interpretation |
| E1-043 | 3/3 | complete under agent-fixed interpretation |
| E1-044 | 3/3 | complete under agent-fixed interpretation |
| E1-045 | 3/3 | complete under agent-fixed interpretation |
| E1-046 | 3/3 | complete under agent-fixed interpretation |
| E1-047 | 3/3 | complete under agent-fixed interpretation |
| E1-048 | 3/3 | complete under agent-fixed interpretation |
| E1-049 | 3/3 | complete under agent-fixed interpretation |
| E1-050 | 3/3 | complete under agent-fixed interpretation |
| E1-051 | 3/3 | complete under agent-fixed interpretation |
| E1-052 | 3/3 | complete under agent-fixed interpretation |
| E1-053 | 3/3 | complete under agent-fixed interpretation |
| E1-054 | 4/4 | complete under frozen interpretation |
| E1-055 | 3/3 | complete under frozen interpretation |
| E1-056 | 4/4 | complete under frozen interpretation |
| E1-057 | 3/3 | complete under frozen interpretation |
| E1-058 | 4/4 | complete under frozen interpretation |
| E1-059 | 5/5 | complete under frozen interpretation |
| E1-060 | 5/5 | complete under frozen interpretation |
| E1-061 | 3/3 | complete under frozen interpretation |
| E1-063 | 4/4 | complete under qualified single-flight interpretation |
| E1-064 | 4/4 | complete under frozen interpretation |
| E1-065 | 4/4 | complete under frozen interpretation |
| E1-066 | 3/3 | qualified complete for frozen pulse waveform |
| E1-067 | 4/4 | complete under frozen interpretation |
| E1-068 | 4/4 | complete under source-YAML absence interpretation |
| E1-069 | 4/4 | complete under frozen interpretation |
| E1-070 | 4/4 | qualified complete for frozen pulse waveform |
| E1-071 | 3/3 | complete under frozen interpretation |
| E1-073 | 4/4 | complete under frozen interpretation |
| E1-074 | 5/5 | qualified complete for success-based suppression |
| E1-075 | 6/6 | complete under frozen interpretation |
| E1-076 | 5/5 | complete under frozen interpretation |
| E1-077 | 5/5 | complete under frozen interpretation |
| E1-078 | 3/3 | complete for qualified manual-rearm interpretation |
| E1-079 | 3/3 | complete |
| E1-080 | 3/3 | complete |
| E1-081 | 3/3 | complete |
| E1-082 | 3/3 | complete |
| E1-084 | 3/3 | complete |
| E1-085 | 3/3 | complete |
| E1-087 | 3/3 | complete |
| E1-088 | 3/3 | complete |
| E1-089 | 4/4 | complete for source final-YAML interpretation |
| E1-090 | 3/3 | complete |
| E1-093 | 3/3 | complete via independent Timelines |
| E1-094 | 3/3 | complete via fixed independent stepped-fade Timelines |
| E1-096 | 3/3 | complete for fixed selected sensor set |
| E1-097 | 3/3 | complete via independent Timelines |
| E1-098 | 3/3 | complete |
| E1-100 | 3/3 | complete |
