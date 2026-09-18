# All remaining72 E1 requests

> **Author-review correction (2026-09-19):** The author confirmed personally reviewing all 72 extension cases. Earlier statements that these cases had not received author review were incorrect. Agent preparation and author review are both part of the record. The initial execution counts and raw candidate labels below remain historical records.

> **Follow-up, 2026-09-18:** E1-024 now has an ordinary Timeline IR rolling-budget implementation: original3/3 plus9/9 expiry/boundary histories. See [the revision](e1_024_rolling/README.md) and [raw results](e1_024_rolling/results.json). The71/72 and239/241 counts below describe the preserved initial candidates. Substituting this revision on the same original histories yields72/72 and241/241, subject to the recorded interpretations and integer-second scope. The initial raw results remain unchanged.

Start with [SUMMARY.md](SUMMARY.md). All72 were attempted on the unchanged reference IR runtime. **71 requests reproduced all their frozen histories;239/241 main histories match exactly.** The interpretations were initially prepared by agents, and the author personally reviewed all 72 cases (confirmation dated 2026-09-19). The partial E1-024 candidate and its stronger demand-serving interpretation remain visible.

The author explicitly requested Astra subagents and autonomous interpretation from the prior20 without intervention. Work was split into33 elicited/research,22 official and17 community cases. The exact cohort comes from the100-row corpus minus the actual completed20; the stale TODO had duplicated062/072 and omitted061/071. No original20 case, result or runtime was changed. No manuscript update, commit or push is part of this execution artifact.

Before encoding, each batch froze source-linked interpretation, assumptions/alternatives, inputs, and expected timed actions. Distinct batches preserve their manifests and before-encoding versions. Later independently reviewed sensitivities were separately frozen before IR repair and do not change the original241-history denominator. A total of8 supplemental histories now pass; pre-repair failures are retained. E1-024's separately run JoI fallback passes3/3 short-prefix histories, without implementing rolling expiry.

- [Elicited/research report](batch_er/REPORT.md):33 cases,97/99 exact main histories.
- [Official report](batch_official/RESULTS.md):22 cases,90/90 exact main histories; live-source drift and waveform/interpretation qualifications in its README.
- [Community report](batch_community/README.md):17 cases,52/52 exact main histories, plus4 later diagnostic histories.
- [Machine-readable summary](summary.json): every case, assumptions/qualifications, measured counts, operator composition trees and nesting paths.
- [Flat outcomes](results.csv): one row per request.

`run_batch.py` imports the original `depth/run_depth.py` for lowering, frontend/catalog checks, compiling the reference IR, and T5 action comparison. It builds an E1-local typed fixture catalog. Fixture values are observations; neither histories nor controllers are computed in the fixture. Independent automations share only the declared input history. No Explorer check or hardware measurement is included.

The runner saves expected and actual traces, frontend/grammar results, hashes, and full lowered IR. Subsequent runs archive prior outputs. Initial v1 encodings are separately retained where repairs were needed. Per-batch source/freeze files and summaries document exceptions and interpretation bias. `summarize.py` checks exact membership against `../extension72_plan/cohort_snapshot.json` and rebuilds aggregate files; it does not reclassify a trace mismatch as a pass.

All outputs are finite examples, and assumptions may narrow a source requirement. The same agent family authored assumptions/oracles and encodings despite their temporal freeze. The author also personally reviewed all 72 cases. A pass describes reproduction of the reviewed interpretation on tested histories; it does not establish all-input equivalence or general IR expressiveness.
