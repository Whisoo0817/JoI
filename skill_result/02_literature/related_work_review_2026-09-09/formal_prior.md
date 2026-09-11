# Formal specification / synthesis / translation validation strand

작성일: 2026-09-09. 목적: Introduction의 motivation과 Related Work에서 기존에 해결한 문제를 새 문제처럼 제시하지 않도록 원문 근거를 수집한다. 이 문서는 독립 문헌 카드이며 전체 strand의 최종 종합/novelty 판정은 아니다.

현재 VETS 비교 계약: NL→사용자가 확인한 executable Timeline IR→LLM 생성 JoI 코드. 지원되는 고정 선언 모델 아래 모든 허용 초기 상태·입력 이력에 대해 successful unbounded certificate가 정확한 timed ACTION 관측(시간, 대상, method, typed arguments, multiplicity, 명시적 순서)의 일치를 보장한다. NL의 진짜 의도, 물리 세계, 임의 concurrent automation 전체를 보장하지 않는다.

접근 방법: OpenCite skill을 읽었다. Root가 보고한 OpenCite rate limit 때문에 primary web/저자 PDF로 fallback. 아래 PDF들은 /tmp/formal_prior_read에 내려받아 pdftotext -layout으로 해당 방법·보장·평가·한계 부분을 읽었다. “전문 확보”는 모든 증명을 독립 재증명했다는 뜻이 아니다. 페이지는 별도 표시 없으면 해당 PDF 1-based page. 검색 스니펫의 크롤링 날짜를 출판 날짜로 쓰지 않았다.

## F1. Murphy et al. — Combining LLM Code Generation with Formal Specifications and Reactive Program Synthesis

- **서지**: William Murphy, Nikolaus Holzer, Feitong Qiao, Leyi Cui, Raven Rothkopf, Nathan Koenig, Mark Santolucito. 2024 preprint, arXiv:2410.19736v1. 정식 학회 출판 확인은 이 조사에서 하지 않음.
- **원문/접근**: [arXiv HTML](https://arxiv.org/html/2410.19736v1), [PDF](https://arxiv.org/pdf/2410.19736). 8p 전문 확보; Introduction, System Overview, Formal Verification Assisted Code Generation, Evaluation을 확인.
- **문제·명세**: LLM의 복잡한 reactive control 구현 오류와 검토 부담. 상세 NL assumptions/guarantees 및 function/predicate 분리를 입력받아 TSL로 변환. TSL은 시간논리, input/output stream, 값을 저장하는 cell, function/predicate terms를 갖는다. **“이 연구에는 시간/값/상태 명세가 없다”는 주장은 틀린다.**
- **구현·보장**: Fig.1(p.2)은 (a) synthesized code를 유지하고 LLM으로 wrappers/functions를 작성하는 경로, (b) synthesized code를 prompt seed로 전체 코드를 LLM이 재생성하는 경로를 구별한다. p.4의 보장은 TSL의 reactive control 관계에 기반하며 function interpretation을 전칭한다. 하지만 pure-function 모델에 대한 이 전칭을 임의 부작용을 가진 wrapper의 정확성으로 확대하면 안 된다. 평가(p.5–6)는 남은 unverified lines도 직접 센다. 최종 platform runtime의 모든 호출을 별도 executable reference와 대조하는 validator는 이 제시 workflow에 없다. (b)는 보장 보존 경로로 취급하지 않는다.
- **A/B와 비교**: A의 sustained condition을 temporal control로 명세할 수 없다고 단정 불가. 5분의 실제 clock과 I/O runtime 연결은 별도 모델링 사항이다. B의 과거 값을 cell에 보존해 나중에 사용한다는 data-flow 관계는 TSL 표현 대상이다. 다만 concrete sensor API가 의도한 값을 읽고 notification API가 그 인자를 전달한다는 구현 의미는 synthesized controller의 universal uninterpreted-function guarantee만으로 정해지지 않는다.
- **반박 강도**: **높음** — “NL→reactive code에 formal guarantee가 없었다”, “NL을 temporal spec으로 명시하면 처음 검증할 수 있다”를 직접 반박.
- **정확한 차이 후보**: TSL control을 합성해 보장하는 경로와, 확인된 operational reference에 대해 실제 생성된 JoI 프로그램의 concrete timed observations를 검증하는 경로의 차이. 이는 guarantee target 차이이며 VETS가 더 일반적이라는 뜻은 아니다.

## F2. Finkbeiner et al. — Temporal Stream Logic: Synthesis Beyond the Bools

- **서지**: Bernd Finkbeiner, Felix Klein, Ruzica Piskac, Mark Santolucito. CAV 2019, LNCS 11561, pp.609–629. DOI [10.1007/978-3-030-25540-4_35](https://doi.org/10.1007/978-3-030-25540-4_35).
- **원문/접근**: [저자 PDF](https://www.marksantolucito.com/papers/cav-19.pdf), [연구실 소개](https://finkbeiner.groups.cispa.de/publications/2019-temporal-stream-logic-synthesis-beyond-the-bools/). 저자 PDF 22p 전문 확보. §2, §4, §5, §6 확인.
- **명세 특징**: §4(pp.6–9)는 arbitrary-typed streams, input/output, cells, pure function/predicate terms, updates를 정의한다. cell은 시점 t의 값을 저장하여 이후 계산에 사용한다. LTL식 next/until와 derived temporal operators를 제공한다. **Temporal/data 결합 자체가 Timeline IR의 최초 특징일 수 없다.**
- **구현·보장**: §4 realizability(p.9)는 `∃ strategy ∀ input streams ∀ function interpretations`로 명시된다. §5는 undecidable 일반 문제에 대해 LTL abstraction+CEGAR를 제시한다. §6(pp.12–15)는 Control Flow Model이라는 추가 IR과 Haskell FRP module 생성, 외부에서 제공하는 initial state와 pure transformations를 설명한다. 따라서 단순 “IR만 만들고 실행/보장은 없다”도 틀리다.
- **A/B와 비교**: §2 Android music-player 예제 자체가 pause 이전 상태를 기억하고 resume 때 행동하는 문제를 보인다. B의 저장값 수명/전달을 표현할 cell이 있다. A 역시 논리적인 sustained-condition 제약을 담을 수 있다. metric 5분을 VETS와 같은 100ms input grid/1ms deadline/tie order로 구현·검증한다고 원문이 말하는 것은 아니다. 반대로 그러한 clock encoding이 원리적으로 불가능하다는 결론도 못 낸다.
- **반박 강도**: **높음** — temporal relation, value history, formal semantics, executable control generation의 최초성 주장 반박.
- **차이 후보**: VETS의 표기 편의와 domain operators를 TSL보다 높은 표현력이라고 주장하지 말고, smart-home input/service semantics와 관측 equality를 연결하는 구체적 검증 의무를 제시해야 한다.
- **인접 참고**: [Temporal Stream Logic modulo Theories](https://doi.org/10.1007/978-3-030-99253-8_17), Finkbeiner/Heim/Passing, FoSSaCS 2022, pp.325–346는 interpreted functions/equality/Presburger arithmetic 확장을 다룬다. 이번에는 publisher abstract 및 §3 검색 노출만 확인했으므로 상세 별도 카드 수준의 전문 검토는 아님. TSL 계열을 “uninterpreted라서 arithmetic을 못 다룬다”로 통째로 제한하면 안 된다.

## F3. Zhang et al. — AutoTap

- **서지**: Lefan Zhang, Weijia He, Jesse Martinez, Noah Brackenbury, Shan Lu, Blase Ur. *AutoTap: Synthesizing and Repairing Trigger-Action Programs Using LTL Properties*. ICSE 2019, pp.281–291. DOI [10.1109/ICSE.2019.00043](https://doi.org/10.1109/ICSE.2019.00043).
- **원문/접근**: [저자 PDF](https://hewj.info/papers/autotap.pdf). 11p 전문 확보. §II–V, §VII 확인. UChicago mirror는 web renderer 오류가 있었지만 hewj.info PDF 읽기 성공.
- **명세 특징**: 사용자 property templates→LTL; expert는 LTL safety property 직접 입력도 가능. EVENT–STATE–ACTION TAP, device transition systems. §II-B(p.283)는 모든 가능한 infinite executions가 property를 만족한다는 TS satisfaction을 정의한다. **검증이 없거나 finite test만 하는 시스템이 아니다.**
- **시간 특징**: §V-A(pp.285–286)는 `t#e`(최근 t초 내 event)와 `t*ap`(ap가 최소 t초 연속 유지됨)를 명시. `t*ap` timer는 ap가 false가 되면 즉시 -1로 바뀐다. 최소 positive timer만큼 tick을 진행하는 timing abstraction도 설명한다. **A의 sustain/reset을 기존 IR/명세가 표현하지 못한다는 사례로 쓰면 안 된다.**
- **구현·보장**: device model+existing TAP+property의 violating executions automaton을 만들고, good executions를 유지하면서 bad executions를 제거할 rule synthesis/repair를 수행(§V). 조건을 만족하는 제어 규칙을 합성하는 것이다. §VII(p.290)는 bridge edge 존재 및 단일 TAP rule로 cut 가능해야 하는 prototype limitation을 명시한다.
- **A/B와 비교**: A의 continuity는 직접 지원된 timing proposition으로 설명 가능. 이것만으로 VETS의 exact off-at-deadline/multiplicity 규약을 AutoTap UI가 모두 이미 채택한다고 말할 수도 없다. B의 arbitrary saved sensor value와 나중의 API argument equality는 제시된 seven-template interface의 독립 primitive로 확인되지 않았다. 하지만 finite device states 확장으로 못 인코딩한다는 불가능성 주장은 하지 않는다.
- **반박 강도**: **높음** — “사용자의 시간 의도를 명시하고 formal verification하는 smart-home 방법이 없다”를 반박.
- **차이 후보**: property-satisfying behaviors를 허용/수정하는 계약과, 선택된 executable IR가 각 입력 이력에 결정하는 concrete ACTION trace를 별도 생성 코드가 그대로 보존하는 계약의 차이. LTL이 원리적으로 완전한 행동을 지정할 수 없다는 식의 표현은 금지.

## F4. Pnueli, Siegel, Singerman — Translation Validation

- **서지**: Amir Pnueli, Michael Siegel, Eli Singerman. TACAS 1998, LNCS 1384, pp.151–166. DOI [10.1007/BFb0054170](https://doi.org/10.1007/BFb0054170).
- **원문/접근, 후속 갱신**: [publisher 기록](https://link.springer.com/chapter/10.1007/BFb0054170), [1998 전문 PDF](https://link.springer.com/content/pdf/10.1007/BFb0054170.pdf). 최초 검토에서는 전문 미확보였으나 후속 정밀 검토에서 16p 전문을 확보했다. STS·clocked mapping·REF 의무·생성기 구조 가정은 [정밀 카드](translation_validation_deep.md)에 기록했다. TACAS 1998 정식 논문이며 arXiv-only가 아니다.
- **방법·보장**: compiler 전체의 정확성을 먼저 증명하는 대신 각 번역 결과가 source를 올바르게 구현하는지 별도 validation. source와 target의 공통 semantic framework, refinement relation, simulation-based proof method가 핵심 구성 요소.
- **직접 관련성**: 원 연구의 예가 synchronous multi-clock SIGNAL→asynchronous sequential C이다. **“reactive 시스템의 source–implementation 보존 검증은 기존 compiler validation과 다른 새 문제”라고 하면 반박된다.**
- **A/B와 비교**: 원조 MUX 예제부터 이전 값을 기억하는 `ZN`을 다룬다. B의 저장값 개념 자체는 새롭지 않다. A의 플랫폼별 timer/input 규약과 동일한 구현을 이미 평가했다는 뜻은 아니며, 기존 formalism으로 표현 불가능하다는 결론도 내리지 않는다.
- **반박 강도**: **매우 높음** — “신뢰할 수 없는 생성기의 출력만 검증”이라는 원리 자체를 novelty로 세우면 안 됨.
- **차이 후보**: VETS는 이 원리를 자연어 authoring에서 확정한 reference 및 JoI input/service/deadline semantics에 적용한다. 그 적용에 필요한 모델/추상화/인증 성질이 논문의 실질 기술 기여인지 별도로 입증해야 한다.

## F5. Ngo et al. — Modular Translation Validation of a Full-sized Synchronous Compiler using Off-the-shelf Verification Tools

- **서지 주의**: Van Chan Ngo, Jean-Pierre Talpin, Thierry Gautier, Loïc Besnard, Paul Le Guernic. 같은 제목의 SCOPES 2015 invited presentation/abstract(pp.109–112)는 [저자 publication list](https://channgo2203.github.io/publications/)에서 확인. **`jar15.pdf` 파일명만으로 JAR 2015 출판이라고 쓰지 않는다.** 읽은 상세 PDF는 표지에 “Noname manuscript No.”, Received/Accepted date placeholders가 있는 37p 저자 manuscript이며 이번 검색에서 journal DOI/volume/year를 확정하지 못했다.
- **원문/접근**: [상세 저자 manuscript](https://channgo2203.github.io/pdfs/jar15.pdf), [SCOPES short version](https://channgo2203.github.io/pdfs/scopes15.pdf). 상세 전문 확보. §1, §3–4, §6–8의 관련 내용 확인; 모든 정리 독립 검증은 하지 않음.
- **명세·구현**: SIGNAL compiler의 clock synthesis, static scheduling, generated C를 단계별 validation. clock models, Synchronous Data-flow Dependency Graph, Synchronous Data-flow Value-Graph 등 여러 IR/공통 의미 모델을 사용(§3 Fig.1; §4–6).
- **강한 겹침**: §6(pp.24–25)는 source의 각 output signal과 생성 C counterpart가 **모든 시점에 같은 값**을 갖는지 검사한다고 명시. Shared value-graph를 구성하고 rewrite/normalization으로 비교한다. §6.5(pp.31–32) generated C 예제는 이전 값 `m.N`과 현재 입력을 명확히 구별한다. **시간과 저장값 관계를 가진 실제 생성 코드의 동등성 검증이 처음이라는 주장을 반박한다.**
- **보장·신뢰 경계**: clock 부분은 trace inclusion/refinement이며 모든 단계를 무조건 exact equality라 부르면 부정확. §4 p.11은 abstraction soundness proof를 지면상 제시하지 않는다고 한다. 결론의 “formally verified compiler verifier” 문구만으로 source-level mechanized proof 완료라고 추론하지 않는다. Compiler는 black box로 취급하되 formal model builder/validator 및 rewrite rules에 신뢰가 필요하다.
- **A/B와 비교**: B의 stored/current 값 구분은 이 연구의 데이터 보존 검증과 직접 가까움. A의 JoI timer cancellation·input/deadline simultaneous order는 그대로 같은 platform 의미가 아니다. 다만 synchronous clock/state 프로그램으로 그런 행동을 인코딩 못한다는 결론도 못 낸다.
- **반박 강도**: **매우 높음** — “temporal/data IR + implementation equivalence”만으로는 차별화 불충분.
- **차이 후보**: 정해진 compiler 단계의 데이터구조 변환 검증과 임의 LLM-produced 지원 JoI candidate의 실행 의미 검증에서 필요한 invariants/abstraction/coverage를 구체적으로 비교. ‘LLM이 생성한다’라는 provenance만으로 새 verification 알고리즘이 되지는 않는다.

## F6. Li and Song — Natural Language based Specification and Verification (NLForge)

- **서지**: Zhaorui Li, Chengyu Song. arXiv:2605.11315v1, 2026-05-11. 표지 NeurIPS 2026 형식 표기는 있으나 **arXiv preprint로 기록; 정식 acceptance 확인 없음**.
- **원문/접근**: [HTML](https://arxiv.org/html/2605.11315v1), [PDF](https://arxiv.org/pdf/2605.11315). 27p 전문 확보. §1, §3, §4.2, §5 확인.
- **문제·명세**: C/C++ memory safety의 interprocedural reasoning. 사용자 의도를 temporal task로 구체화하는 시스템이 아니라 code에서 allocation/free/initialization/contracts를 추출하여 typed JSON+자유 NL 설명으로 저장한다(§3.2 p.5). `target`, `contract_kind`, `size_expr`, `condition` 등과 symbolic expressions를 사용한다.
- **검사**: call graph에서 bottom-up summaries를 합성하고 LLM이 callee pre/post조건으로 caller를 검사한다(§3.3 pp.5–6). 즉 actual code checking을 하므로 “검증하지 않는다”는 말은 부정확하다. 다만 **LLM 자체가 checker**이며 §4.2(p.7)는 false positive/negative가 있고 standalone sound verifier가 아님을 명확히 인정한다. §5(pp.8–9)도 soundness limitation을 반복한다.
- **A/B와 비교**: temporal automation/timed ACTION trace를 연구 대상으로 삼지 않는다. 일반 memory lifetime과 VETS B의 sensor read snapshot은 서로 다른 correctness 계약이다.
- **반박 강도**: broad “NL specification을 이용해 LLM-generated code를 검사”에는 **중간**, temporal automation의 정식 unbounded certificate에는 **낮음**.
- **차이 후보**: executable deterministic reference semantics 및 model-based sound certificate vs 자유 NL summaries를 사용한 LLM memory-safety 판단. 이 연구가 “formal spec이 반드시 필요하다”는 motivation 문구에 제기할 수 있는 반론은 받아들이되, 보장의 기준을 분리하면 된다.

## F7. Mendoza et al. — ARTEMIS (새 직접 후보)

- **서지**: Daniel Mendoza, Anastasia Mavridou, Andreas Katis, Caroline Trippel. *Automating Requirements Formalization: Using LLMs and Low-Complexity Distinguishing Traces for Semantic Validation*. ICSE 2026, 13p. DOI [10.1145/3744916.3787815](https://doi.org/10.1145/3744916.3787815).
- **원문/접근**: [저자 PDF](https://cs.stanford.edu/people/trippel/pubs/mendoza_ICSE26.pdf). 13p 전문 확보. §1–4, §7.1–7.4 확인, §5–6 proxy/trace generation relevant definitions 확인.
- **명세**: unstructured NL→structured NL IR(FRETish/PSP)→deterministic TL mapping. FRETish의 scope, condition, timing, response는 temporal 관계를 명시하며 “within N ticks”, “upon” vs “whenever”도 구별(§2.2 pp.2–3). **‘NL에서 temporal info를 가진 IR을 만든다’는 바로 이 연구의 작업이다.**
- **validation**: NL decomposition을 사용자 확인하고, candidate fragments에서 proxy specs를 만든 뒤 허용 행동을 가르는 distinguishing traces를 accept/reject하여 후보를 제거한다(§3 Fig.2, §4). Semantic validation은 실제 개별 생성 구현의 equivalence 검증과 다르다. 모델검사 도구를 사용하므로 “formal checking 전혀 없다”도 부정확.
- **평가·경계**: §7.3(p.10)는 전문가 명세를 oracle로 **사용자를 simulate**하고 후보에 expert spec을 추가하여 적어도 하나의 plausible candidate를 보장한다. 이를 실제 사용자 선택 정확성 user study로 읽으면 안 됨. §7.4는 structured-NL expressiveness 밖의 요구를 인정한다. trace 길이≤20은 prefix+cycle 표현 길이이며 단순 20-step 유한 테스트가 아니다. Universal implementation safety/equivalence certificate를 제시한 평가도 아니다.
- **후속 정밀 검토**: [ARTEMIS 정밀 카드](artemis_deep.md)에 §§5–6의 proxy 적합성·balanced-query 조건과 공개 구현의 의미 동등성 중복 제거를 기록했다. 후보 접기와 구별 trace 모두 선행이 있으며, 무조건 O(log n) 질문 보장으로 인용하지 않는다.
- **A/B와 비교**: A의 scope/condition/timing 해석과 interruption 구별을 확인하는 motivational 방향이 가까움. B의 임의 sensor value를 저장해 action argument로 나중에 넘기는 operational primitive는 제시된 FRETish Boolean response 모델에서 독립적으로 확인되지 않았다. 불가능성을 주장하지 않는다.
- **반박 강도**: **매우 높음** — 명세 모호성 해소, temporal IR, 사용자 확인, trace로 후보 선택이라는 서사는 이미 가까운 사례가 있음. VETS는 확정 명세의 플랫폼 구현 보존으로 범위를 구분해야 한다.
- **차이 후보**: 확정할 명세를 찾는 ARTEMIS의 작업 이후에도, 그 명세를 구현한 platform code가 같은 time/value actions를 만드는지는 별도 의무라는 연결. 명세 해석 자체의 새 알고리즘을 VETS가 제안하지 않는다면 ARTEMIS보다 해석을 잘한다는 주장을 하지 않는다.

## F8. Ma et al. — Req2LTL / OnionL (새 직접 후보)

- **서지**: Zhi Ma, Cheng Wen, Zhexin Su, Xiao Liang, Cong Tian, Shengchao Qin, Mengfei Yang. *Bridging Natural Language and Formal Specification—Automated Translation of Software Requirements to LTL via Hierarchical Semantics Decomposition Using LLMs*. ASE 2025. DOI [10.1109/ASE63991.2025.00104](https://doi.org/10.1109/ASE63991.2025.00104); arXiv:2512.17334 (posted 2025-12-19). [IEEE record](https://ieeexplore.ieee.org/document/11334235) confirms conference 2025, Xplore added 2026-01-28; these are distinct dates.
- **원문/접근**: [arXiv PDF](https://arxiv.org/pdf/2512.17334), [저자 repository](https://github.com/Meng-Nan-MZ/Req2LTL). PDF 13p 전문 확보. §III–V, §VI-F, §VII 확인.
- **IR 특징**: OnionL은 temporal/mode scopes, logical/temporal relations, atomic propositions의 recursive tree. `Globally`, `Eventually`, `Next`, Until variants; sustained precedence와 arithmetic-form predicates도 예시로 제시(§IV-A pp.4–5, Fig.3). **기존 IR는 temporal scope나 데이터 관계가 없다고 일반화하면 반박된다.**
- **검사·출력**: structural/type/arity 검사와 optional visual human inspection 후, deterministic structure-preserving OnionL→LTL 변환(§V pp.6–7). §V-B의 의미 보장은 **OnionL이 원 요구를 올바르게 담았다는 조건부**이다. model checker와의 integration 가능성을 설명하지만 이 논문의 end-to-end output은 LTL spec이다. 실제 별도 생성 platform implementation의 timed-trace equality certification을 평가하지 않는다.
- **motivation 겹침**: §VI-F/§VII(pp.10–11)는 “as soon as possible” 등의 implicit timing, context 없이는 F/Next 선택을 정할 수 없음, human correction 필요를 직접 설명. 사용자의 motivation 2와 매우 가까움.
- **A/B와 비교**: A의 continuous until relation 및 scope는 IR에 있다. 그러나 specific 5min sustain-cancel/restart API semantics가 검증된 primitive라는 증거는 없음. B의 arithmetic expressions는 AP에 나타나나 executable READ binding/lifetime를 독립 semantics로 제공했다고 확인되지 않음. 이를 표현력 불가능성과 혼동하지 않는다.
- **반박 강도**: **매우 높음** — “ambiguous NL→explicit temporal behavior IR→user confirmation”만으로는 차별화 불충분.
- **차이 후보**: 생성된 논리 명세를 downstream verification input으로 만드는 것과, 사용자 확인한 IR를 각 input history의 실행 oracle로 삼아 실제 생성 JoI와 관측 동등성을 검증하는 것의 역할 차이. Deterministic mapping이나 human inspection 자체는 차별점이 아니다.

## 이 strand에서 반드시 유지할 비교 규칙

1. “verification 있음/없음” 이분법 대신 **specification validation / controller synthesis / property checking / generated implementation equivalence / LLM judging**를 구별한다.
2. “temporal/data 없음”을 말하기 전에 해당 formalisms가 clock, cell, arithmetic, state를 어떻게 담는지 확인한다. 표현력, 제공된 primitive, 실제 evaluated workflow를 서로 구분한다.
3. A/B는 생성 코드의 preservation problem을 구체적으로 보여주는 예이지 prior work expressiveness 불가능성 증명이 아니다. AutoTap과 TSL/translation validation은 A/B의 주요 요소를 이미 다룬다.
4. 현재 확보한 차이는 **논문이 실제로 해결한 verification contract와 pipeline 범위**이다. ‘최초’ 판정, 타 접근으로 해결 불가능, VETS의 우월성은 아직 도출하지 않는다.
5. TV1998 전문 source gap은 후속 정밀 검토에서 해소했다. `jar15.pdf`의 정확한 journal publication metadata는 여전히 미확인이다. ARTEMIS/Req2LTL은 별도 cross-strand 비교에 포함한다.
