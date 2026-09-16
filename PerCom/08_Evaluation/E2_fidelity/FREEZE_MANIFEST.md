# E2 freeze manifest

Written before the reference or the Explorer is run on any E2 pair or history. Any later change to a file
below is a new version, logged with a reason taken from the specification or protocol, never from a result.

| File | sha256 |
|---|---|
| PROTOCOL_DRAFT.md | `97f909cd25ecec383c728410ea3f1be2ebc1d075bc768637071049ebffa94393` |
| histories/e1_histories.json | `b5d5d6dc7f41e092877e3b2b252a38ab61d786a58cd466fcdc9f6d268ba0e083` |
| histories/make_388_histories.py | `10058b1576b6cb0e79e38fcec832450a1a31118f34c26c903b6401683d4b1583` |
| histories/make_e1_histories.py | `27598646fb857966e5716aa4dc8d67b7f9330782638077d180bed21f2117741c` |
| histories/sample_388_histories.json | `7adaf783e58b9611d877ed356c3a5aaffb676be505ec1081ac2b895e6f1d6d8c` |
| pairs/build_388_pairs.py | `4f5d65424893788a2d42905f6fdd79838401503362e414973a238130293ba964` |
| pairs/build_e1_pairs.py | `b797188ed85bf99cae2dd58a857e2e421fcd551cd54dd73e67ac3e972359e702` |
| pairs/e1_pairs.json | `de3650666279bc8281038b383f4ecae0eaf1cb386d79dad9e7d09be4384cd821` |
| pairs/e1_pairs_src.py | `38240b54b42101a069415c76338a0298b12d06c1387d6aba7d5418d5eaa67478` |
| pairs/sample_388.json | `42d944f0b17b4ac9bc3de928336969c36413c36e01af074cdee82f92e8a78adf` |
| pairs/sample_388_pairs.json | `88628f1cbb0ea7784b3a4c75c0651d90b6b96a307ac7e963887e3afc08dd8b26` |
| pairs/select_388_sample.py | `83263d49318af6fac8924d6893c8aa23f5294b26fdde2d0c017fec47b9be44ea` |
| reference/CONFORMANCE.md | `28191e28a59981570ec80090dc18104c3883f13ca4cada757d1e38e9e576d3d4` |
| reference/READ_LOG.md | `bc2b4b95179b8eb7b2920ade97d8c30a5c34c896ac8c153dfa27ea75ed93cc06` |
| reference/SMOKE_388.md | `7ca53545f36116be75b829de558b9ea7eef6acf9d985b93642075dc57fccf01f` |
| reference/SPEC_GAPS.md | `7770b8086057a8a9362e08173b8402c7e74df0dbeb88af3a71cba2cff815a848` |
| reference/common.py | `8c0dc91eb5c2b1299047338222dbd2f0a4b0add00d14ae0cab5955b726943215` |
| reference/conformance_results.json | `12ed7f8d60ef2e381becd748e565aa822eda6fc712f53188fba97e515f2ba5e9` |
| reference/grammar/JOILang.g4 | `49f28792ad886e124748e3d79b334d807cdbd250025dae8c6576d107b722f718` |
| reference/grammar/JOILang.interp | `1d9436a02b787398640d028f25ebe1e38555b79c9b8c22ea6fe6796a91aace75` |
| reference/grammar/JOILang.tokens | `1f18f496fb7434c46ba0c15190ae2e487a85c14f15c3e69bc98f810b597d201a` |
| reference/grammar/JOILangLexer.interp | `f65681e85e1249e244be69c5b9df5ab55712c356950fe9b97980ed02e95f07d4` |
| reference/grammar/JOILangLexer.py | `fd17d23945a4daf9ceedbd6be69bfdb9966e64a0337dd03a8f1d3bda5c6f1400` |
| reference/grammar/JOILangLexer.tokens | `1f18f496fb7434c46ba0c15190ae2e487a85c14f15c3e69bc98f810b597d201a` |
| reference/grammar/JOILangListener.py | `43164db5792fe8ed791963f6b07ff548c589e95edd3d89b0a970e1f69d5aec9b` |
| reference/grammar/JOILangParser.py | `dcd38b0f4356807efa06a7af7789314935d12119709d981221d0db674f3a1588` |
| reference/ir_ref.py | `4218bc83600050db27ced2383f458a05121b89732e4c21e5dd6141cbe99fd1fe` |
| reference/joi_ref.py | `39bf3546fe9c3afefe590d7cb2dfa62020477fb59ec256570ab041ad023279a1` |
| reference/run.py | `ae6969906b1f3f30f13557da139370e08655ed40f19090e0915b53a314453694` |
| reference/smoke_388.py | `2bfebe95167d1ce4df06b9bf8efc1edd4d50b4e047c9d67c19f23d8f86dbb40a` |
| reference/smoke_388_results.json | `450ade096b2dc20db08de11ef0cc472d982cf927d2a7b7a87b6af48c29333910` |
| reference/test_e1_conformance.py | `209dc920705505d7eb957830f72efda2b22419984810bfadc9ed2587189e6a6d` |
| reference/test_independence.py | `1a86fdad62b3a6bf2de717f84375e0ab0df5c5bd0cd90b6419da9e12a166884b` |
| run_e2.py | `e046e9b7f53aeab0db4248c0aa91980db608e70c85981aee15b17f24c5932b4d` |

Explorer under test: repository HEAD `490e884e974235929299ab37473e8813ce40b44f` at freeze time, `explorer/` tree `a0d49661b5014fb838e47ddda1ceeb0342ad53d3` (unchanged since).

## Harness corrections after the freeze

| Date | File | Change | Reason | Not affected |
|---|---|---|---|---|
| 2026-09-14 | run_e2.py `witness_events` | add each witness entry's dwell before applying its inputs, not after | Explorer `Divergence.path` entries are (held inputs, dwell since the previous node) (`timed.py` `path()`); the first rows showed witnesses shifted one entry early (e.g. C01/fault4 replayed as equal). Found from the conversion itself, not from an agreement count. | Explorer verdicts, reference outcomes, pairs, histories, reference code. Witness replays were first recomputed by `recheck_witnesses.py`; that output was not kept, and `rerun_reference.py` (`runs/e2_run.ref-frozen.jsonl`, `runs/e2_run.ref-current.jsonl`) replaced it. The original run file is kept. |
| 2026-09-14 | reference (ir_ref.py / joi_ref.py / common.py, SPEC_GAPS G3/G4) | ordered comparison with a None operand evaluates to false (was REF-UNSUPPORTED) | author decision (whisoo): the contract includes None in non-BOOL input domains but no document fixes the comparison result; surfaced by Explorer witnesses containing a missing CO2 value (C03 faults), not by an agreement count | pairs, histories, Explorer verdicts. Reference outcomes of the frozen run are recomputed with the new version and both are reported. |

## Later versions (the hashes above are the frozen ones; these files have changed since)

| Commit / date | Files | Change | Record |
|---|---|---|---|
| `c76fd76` | PROTOCOL_DRAFT.md, reference/READ_LOG.md, reference/SPEC_GAPS.md, reference/common.py, run_e2.py | the two harness corrections above | table above |
| `193203c` | PROTOCOL_DRAFT.md (§9), histories/make_supplement.py, histories/supplement_histories.json(.gz) | supplementary histories, committed before any reference run on them | `histories/supplement_histories.json.sha256` |
| `3b728e4` | reference/common.py, ir_ref.py, joi_ref.py, run.py, READ_LOG.md, SPEC_GAPS.md, run_e2.py | binding contract B1/B2 (reference by the separate agent; `run_e2.py` switch `E2_BINDING_DECISION`) | `BINDING_DECISION_2026-09-14.md` |
| 2026-09-14 (working tree) | reference/joi_ref.py, SPEC_GAPS.md (G35), READ_LOG.md, test_binding_decision.py | `any(...)` outside a condition (ACTION position, assignment, argument) is a syntax error (author decision); C03_008/llm is outside the 140-pair population. `reference/SMOKE_388.md` is not rerun; under this rule its C03_002 entry (`IsAvailable = any(...)`, listed as unsupported) would be a syntax error | `handoff_timer/e2_population.json` |
| 2026-09-16 (working tree) | reference/common.py (`RefRuntime`), joi_ref.py (`check_assigned`), run.py (status `runtime-error`), SPEC_GAPS.md (G4), run_e2.py, explorer/runtime/interp.py, explorer/verification/service_model.py, explorer/docs/model/RUNTIME_CONTRACT.md (R14) | arithmetic on a variable that was never assigned is a runtime error: the instance stops for good and the stop is observable, so one side ending this way differs from a side that runs on (author decision whisoo, `uninitialized-arith-v1`). Scope is variables only — `+` with a STRING operand is S8 concatenation and a missing non-BOOL input read (R10) is unchanged, as is IR arithmetic. Reach: a definite-assignment check over all 142 frozen pairs and over the 382 E3 inputs finds C24_003/llm and nothing else; an A/B rerun of the reference over the frozen histories leaves every other pair's outcome unchanged. Only that pair's row of `runs/e2_run.timer-binding.jsonl` was recomputed (its previous values are kept in the row as `reference_before_r14` / `explorer_before_r14`) | `INSPECTION_2026-09-14.md` "C24_003/llm after R14" |

The population used for every reported table is the 140 pairs of `handoff_timer/e2_population.json`.
