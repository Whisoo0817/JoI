# Section 6 draft notes

2026-09-17. User requested a compact section, with the manuscript taking precedence over figure labels. This is an editorial/source record, not a new experimental result or a full proof audit.

## Scope and layout

- Candidate generation: two sentences referencing Fig. 2. Inputs: confirmed IR, binding, language syntax, generation prompt.
- Two subsections: Joint Behavioral Exploration; Completion and Soundness.
- One conceptual algorithm, one displayed proposition, inline product-state/difference-constraint notation.
- Counterexample/repair: two sentences. Implementation: three sentences, absorbed from the former standalone section.
- No new architecture figure, example listing, route table, or proof appendix. Existing §5 examples, operator table, equations, and compact appendix are unchanged.
- Initial Tectonic build: §6 begins on p. 7 and ends in the upper half of the left column on p. 8, about 1.25 pages including Algorithm 1. Total draft: 9 pages including references and appendix. Evaluation and closing sections remain absent. This is not a final submission-length claim.
- References currently precede the appendix. Revisit final ordering when fitting the complete paper, particularly any references-only extra page.

## Source correspondence

| Manuscript content | Local source | Boundary retained |
| --- | --- | --- |
| Preparation, shared inputs, initial globals, observation | `../../explorer/docs/model/VERIFICATION_CONTRACT.md` | Same initial environment does not mean equal local stores; program-owned globals are not overwritten by external input |
| Input coverage and exact exploration | `../../explorer/docs/proof/PROOF_OBLIGATIONS.md`, `../../explorer/verification/timed.py` | Threshold outcomes alone do not cover arbitrary stored/output values |
| Timer/counter relations | `../../explorer/docs/proof/TIMER_ZONES.md`, `timer_analysis.py`, `timer_product.py` under `../../explorer/verification/` | Grid-aligned restricted path; expansion is forward coverage, not equivalence of every merged state |
| Completion and S | `VERIFICATION_CONTRACT.md` definition of Accept-infinity; `PROOF_OBLIGATIONS.md` B0–B3/common induction; `TIMER_ZONES.md` B0–B3 | No fixed-horizon extrapolation, guaranteed termination, arbitrary-program completeness, or silent treatment of errors |
| Implementation | `../../explorer/verification/gate.py`, `../../explorer/verification/timed.py`, `../../explorer/requirements.txt` | JoI semantic interpreters, optional Z3 arithmetic paths, not physical devices |

Algorithm 1 is a schematic of shared obligations and eligible-path fallback, not a literal description of a single backend's dispatcher. A failed abstract mismatch check abandons that attempt rather than allowing certification from a partially explored frontier. An eligible fallback may still be attempted within its budget.

Proposition S is accompanied by a proof sketch. Detailed existing manual arguments remain in the local proof documents and are not silently counted as an included appendix or a permitted submission supplement. Trust in the frontend, interpreters, and solver is explicit. The sketch is not an independent audit or machine verification of the implementation.

## Fig. 2 review

Inspected `overleaf-paper/figures/system.png` after pulling remote `bab3ffa`. The main workflow, input-model construction, paired execution, timed comparison, three outcomes, and optional repair match the text. The image itself was not edited.

Recommended label clarifications for the user:

- Latest terminology feedback (2026-09-17): replace `Service catalog & execution contract` with `Input types & execution rules`. Keep the box and its arrow to input-model construction. Shared execution model now describes the values read by both programs, their types, and shared execution rules directly. Markdown and local LaTeX updated; the user-maintained image remains unchanged.

1. `Shared initial state & timed inputs` → `Shared initial environment & timed inputs`. The common initial environment is shared, while program-local stores and control states differ.
2. `JoI code execution` → `JoI semantic execution` (or `JoI interpreter`), to avoid implying actual server/device execution during exploration. `Timeline IR execution` may remain, or become `Timeline IR interpreter` for symmetry.
3. If `Inconclusive` is intended to include unsupported pairs, use `Uncertified` or `Inconclusive / unsupported`; the prose explicitly includes both. This is a labeling clarification, not an additional successful outcome.

No extra syntax/prompt box is necessary: generation inputs are stated briefly in the text. The candidate code is an excerpt, not an executable or certified example, and was not tested as one.

## Citation and prose pass

- Added `bengtsson2004timed` for the established DBM technique, not for VETS-specific timer/counter correspondence or novelty.
- Primary text: https://uppaal.org/texts/by-lncs04.pdf . Publisher: https://link.springer.com/chapter/10.1007/978-3-540-27755-2_3 . The publisher confirms 2004, LNCS 3098, pp. 87–124, Johan Bengtsson and Wang Yi.
- OpenCite DOI lookup returned noisy metadata (2003, `Article`, `Yi Wang`); the checked BibTeX corrects these using the publisher and author PDF. Section-local and Overleaf BibTeX copies agree.
- SenSys source: `../../docs/ovla0606.tex`, old Verifier section. Reused the exact sentence “This trace comparison detects both commission and omission.” Current compact PerCom preparation/product/observation wording was retained where compatible. Old boundary synthesis, bounded horizon, timing tolerance, solver-free, and verdict-determinism claims were not reused.
- Humanizer audit of the draft: repeated completion/coverage wording is retained only where needed to define the algorithm and proof; generic filler, em-dash insertions, rhetorical questions, and promotional novelty claims are absent. Final pass made numeric normalization explicit and clarified algorithm abandonment. IEEE title case and the local bold paragraph lead-ins are intentional house-style exceptions.
- Validation: 37 tests passed (`python3.12 -m unittest explorer.tests.test_frontend_conformance explorer.tests.test_timer_zones`). These are regression checks, not evidence replacing S's proof. No runtime code changed.
- Final build remains 9 pages. No overfull boxes, missing citations, or unresolved cross-references. Existing underfull/PDF-version warnings remain, along with a Tectonic decoding warning in an `algorithm.sty` package comment. Pages 7–8 were visually checked. Main text font and margins were not reduced.
- Overleaf/GitHub commit: `7886c30` (`Draft compact behavioral validation and integrate implementation`). Local PerCom Markdown changes remain uncommitted for review.


## 2026-09-17: 시간 구현 비교 문단 간소화

사용자 피드백에 따라 지속 조건 대기에서 시간을 추적한다는 설명부터 시작하고, 서로 다른 IR–JoI 구현을 함께 탐색하는 한 방법으로 소개한다. 본문에서 DBM 수식과 세부 적용 제약을 빼고 지원 범위에 대한 한정은 유지했다. 상세 설명은 아래에 보존하며, 기존 proof 문서를 변경하거나 새 부록을 추가하지 않았다.

**Relating timers and counters.** A sustained wait in the IR may become a tick counter in JoI (Figure 2). For supported synchronous programs, difference-bound matrices [@bengtsson2004timed] represent relations \(x_i-x_j\le c\) between integer counters and IR timers measured in input-grid units. This method requires grid-aligned deadlines and restricted counter updates and uses, while keeping ordinary variables and execution locations explicit. When a represented set expands, the Explorer rechecks actions and all successors over the enlarged set. This set may include unreachable states, but must retain every reachable state. Programs outside these restrictions need another applicable checking method or remain uncertified.


## 2026-09-17: 특정 시간 idiom 문단 삭제

사용자 지적에 따라 `Comparing different time implementations` 문단을 영문·한글·LaTeX 본문에서 삭제했다. JoI는 tick counter 외에 clock timestamp 차이로도 경과 시간을 표현할 수 있으므로, 특정 counter 관계 탐색 경로를 공통 절차처럼 소개하지 않는다. 기존 DBM 상세 내용은 위 편집 이력에만 보존한다. 이번 편집은 timestamp idiom의 검증 지원 범위를 새로 주장하거나 구현을 변경한 것이 아니다. 공통 입력·시간, timed action 비교, 알고리즘, 완료 조건과 명제 S는 유지한다.


## 2026-09-17: 알고리즘 1 이후 표현 간소화

- Algorithm 1은 유지하고 checking path/frontier/justified keys/expanded states를 쉬운 절차 설명으로 대체했다. 방법별 시도, 구체 재실행으로 확인한 불일치, 완료 후 동등 판정, 자원 한도와 미확정 처리는 보존했다.
- 알고리즘 뒤의 중복 판정 설명을 삭제하고 완료 조건을 명제 기호보다 먼저 설명했다. 정상 실행·시간 진행은 §5를 참조한다.
- 내부 명령 단계가 같아야 한다는 인상을 주는 execution step을 comparison point로 고쳤다. 구현의 모듈 구성은 삭제하고 수작업 증명/기계 검증 여부는 Implementation으로 옮겼다.
- 알고리즘부터 끝까지 영문 공백 기준 534 → 493단어. 명제 수식은 그대로 유지하고 영문·한글·LaTeX에 반영했다. PDF 빌드 통과. Push하지 않았다.
