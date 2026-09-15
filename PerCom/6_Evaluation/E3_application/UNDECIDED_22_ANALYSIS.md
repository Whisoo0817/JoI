# E3 undecided 22% root-cause analysis

Analysis date: 2026-09-15
Source run: `runs/e3_gemma_v3_b5_hnone_20260915/`
Scope: the 85/388 cases that did not produce an Explorer decision.

## Conclusion

The 85 cases must not be reported as one Explorer `undecided` bucket. The run
mixed failures before Explorer with genuine fail-closed Explorer refusals:

| Root cause | Cases | Share of all 388 | Interpretation |
|---|---:|---:|---|
| E3 generation-harness mapping failure | 61 | 15.72% | Invalid E3 execution: the harness re-inferred mapping from natural language instead of consuming the confirmed binding plan |
| Invalid generated candidate/lowering | 13 | 3.35% | No valid program semantics were supplied to Explorer |
| Reference IR/binding defect or ambiguity | 3 | 0.77% | The evaluation input itself needs correction or a declared aggregation rule |
| Genuine Explorer supported-fragment refusal | 8 | 2.06% | Validly reached Explorer, but Explorer intentionally failed closed |
| **Total without an Explorer decision** | **85** | **21.91%** | Not a homogeneous Explorer coverage number |

Accordingly, at least 74 cases (61 harness failures plus 13 invalid candidates)
never supplied Explorer with a valid comparison problem. They cannot be used as
evidence that Explorer was unable to decide a valid input.

## 1. Generation-harness mapping failures (61)

All 61 records have `error_code=device_not_connected`. Their confirmed
`binding_gt` device IDs are present in `connected_devices`; none references a
missing device. The error arose because E3 injected `ir_gt` but the lowering
pipeline still ran its natural-language mapping extractor instead of injecting
the confirmed binding plan.

The messages expose four overlapping failure patterns:

- 39 cases treated a predicate, threshold, location phrase, or available
  service as an unconnected entity. Examples include `1도 이상 차이가 나면`,
  `비가 오고 있으면`, and `초미세먼지 농도`.
- 27 cases falsely rejected an action/capability, such as dimming a `Light`,
  closing a `WindowCovering`, or stopping an air conditioner switch.
- 2 cases failed tag/selector resolution despite a confirmed binding.
- 1 case invented a speaker requirement for an image-generation/file-save
  request.

These pattern counts overlap for eight multi-error cases. The 61 distinct IDs
are:

`C01_015`, `C03_005`, `C03_019`, `C03_020`, `C03_023`, `C05_001`,
`C05_002`, `C05_009`, `C05_010`, `C05_012`, `C05_013`, `C05_015`,
`C05_017`, `C05_018`, `C05_023`, `C05_027`, `C05_030`, `C06_002`,
`C06_004`, `C07_010`, `C07_013`, `C07_021`, `C08_013`, `C08_019`,
`C08_034`, `C09_006`, `C09_009`, `C09_012`, `C09_016`, `C10_004`,
`C11_001`-`C11_008`, `C12_004`, `C14_004`, `C14_007`, `C15_006`,
`C15_011`, `C17_004`, `C17_010`, `C18_010`, `C19_005`, `C20_001`,
`C23_001`-`C23_005`, `C25_001`-`C25_005`, `C26_001`, `C26_002`,
`C26_005`.

Disposition: fix the E3 harness so that both the confirmed Timeline IR and
confirmed binding plan are inputs to candidate generation. Do not hand-edit
only these outputs or reinterpret them as Explorer decisions.

## 2. Invalid generated candidate/lowering (13)

These cases reached preparation, but the generated JoI program was malformed
or used a service inconsistent with the confirmed device capability:

- Wrong service/capability (9): `C06_001`, `C06_003`, `C06_005`, `C06_006`,
  `C12_010`, `C17_008`, `C20_004`, `C20_011`, `C20_016`.
  Typical examples are emitting `AirQualitySensor.temperature` for a
  `TemperatureSensor`, or `Charger.power` for a device bound as `Plug`.
- Wrong catalog method/domain (2): `C01_023`, `C02_018`. The reference calls
  `SetRobotVacuumCleanerCleaningMode`, while the candidate emits
  `SetRobotVacuumCleanerRunMode("stop")`, which violates the catalog enum.
- Selector/occurrence collapse (1): `C21_005`. Two distinct temperature-sensor
  binding slots were collapsed into repeated `all(#TemperatureSensor)` scalar
  reads (and the action selector also drifted to `#Plug`).
- Syntax error (1): `C26_006`, with an unmatched `)` in the generated script.

Disposition: classify these as invalid candidate/generation outcomes in an
end-to-end study. For the narrower E3 question—what Explorer decides on a valid
candidate—they are outside the Explorer-decision denominator.

## 3. Reference IR/binding defects or ambiguity (3)

- `C15_009`, `C15_010`: a scalar `GetMenu` result is bound to two
  `MenuProvider` devices. The reference does not define which result is passed
  to the speakers or how multiple results are aggregated.
- `C17_003`: the reference IR attaches `var: "Speaker.Volume"` to the
  effectful `SetVolume` call while also reading `$Speaker.Volume` in its
  argument. This is not a clean read-then-write representation.

Disposition: correct the reference or explicitly define its aggregation/value
flow semantics before rerunning. These are not Explorer failures.

## 4. Genuine Explorer supported-fragment refusals (8)

- `C01_006`: SMT could not establish universal validity of the dynamic
  `SetChannel` action domain.
- `C01_019`: return-valued `CloudServiceProvider.ChatWithAI` is not modeled as
  a silent external input.
- `C03_003`: an observable large/unbounded catalog value lacks an explicit
  finite input domain.
- `C14_001`, `C14_002`, `C14_005`, `C14_006`: arithmetic/min/max expressions
  passed as action arguments are outside the current supported pattern.
- `C18_006`: a grouped Boolean read under negation has no explicit declared
  comparison/aggregation semantics.

These are the defensible Explorer `REFUSED` cases for this run. Relative to all
388 cases, the observed supported-fragment refusal rate is 8/388 = 2.06%. A
coverage rate over valid Explorer inputs should only be computed after the
other three buckets are corrected and rerun.

## Protocol caveat

Five of the 85 cases (`C01_006`, `C14_001`, `C14_005`, `C14_006`, `C14_007`)
also belong to the seven cases where the reused candidate payload differs from
the current `dataset.csv`. Their current classifications are useful for root
cause diagnosis, but they cannot serve as final current-dataset measurements.

The prior run remains a development/predecessor run. A corrected run may be
the reported E3 result only if the corrected input contract and handling rule
are fixed before producing the replacement outcomes, with the predecessor
failure and its disposition retained in provenance.
