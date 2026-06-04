# Overleaf 수기 반영 가이드 (2026-06-04)

기준: **ovla.tex(Overleaf 현재본) → ovla2.tex(로컬 수정본)** 의 전체 diff + 오늘 새로 나온 실험 결과.
교수님이 §1/§2 수정 중이므로 **A절(§1/§2 건드리는 것)** 과 **B절(§3 이후, 충돌 없음)** 분리.
각 항목: 위치 → 바꿀 내용 (LaTeX 복붙 가능). 우선순위 ★=수치 무결성(필수), ☆=표현/정리.

---

## A. §1/§2 + Abstract/preamble (교수님과 조율 필요한 구역)

### A1. ★ Abstract 끝부분 (수치 정직화)
기존:
> ...repairing 31\% of them and rejecting the rest. Under 1,562 injected temporal bugs, it detected 99.3\%, while its synthesized scenarios exercised 97.4\% of the targeted boundary cases, improving end-to-end correctness by 2.4 percentage points, all without...

교체:
```latex
...repairing 31\% of them and rejecting the rest fail-closed; the only cost was two
commands rejected because their gated-run lowerings never became valid within the
repair budget. Under 1,562 injected temporal bugs, it detected 99.3\%, while its
synthesized scenarios exercised 97.4\% of specification-side obligations and 96.8\%
of generated-code branches, raising the share of correctly deployed automations
from 90.8\% to 93.2\%, all without any LLM in the verification loop.
```
이유: (i) "the rest"가 over-reject 2건을 숨김(리뷰어 지적), (ii) "end-to-end correctness"는
e2e 정확도 실험이 없으므로 오해 소지, (iii) two-sided coverage 병기 = circularity 방어.
※ over-reject 2건의 정체 = verifier FP 아님(아래 B5 참조).

### A2. ☆ Preamble 정리
- `\usepackage{svg}` 삭제 (미사용)
- `\usepackage{pifont}` + `\cmark`/`\xmark` 정의 3줄 삭제 (미사용)
- fig:arch 위의 한국어 주석 3줄 삭제 (제출 전 필수)

### A3. ★ C4 contribution (§1 끝)
"and on-device feasibility and deployment (\S8.4)" → "and **on-device cost** and deployment (\S8.4)"
이유: "feasibility"가 §5의 feasibility gate(IR∈L(G))와 용어 충돌.

### A4. ☆ §2 verification 그룹에 AgentSpec 1문장 추가 (TaskSense 문장 뒤)
```latex
AgentSpec~\cite{agentspec} enforces trigger-predicate safety rules on LLM agents at
runtime with a deterministic DSL, but the rules are fixed and hand-written rather
than derived from the request being served.
```
refs.bib 추가 (원문 확인됨: ICSE 2026, arXiv:2503.18666):
```bibtex
@inproceedings{agentspec,
  title     = {AgentSpec: Customizable Runtime Enforcement for Safe and Reliable LLM Agents},
  author    = {Wang, Haoyu and Poskitt, Christopher M. and Sun, Jun},
  booktitle = {Proceedings of the 48th IEEE/ACM International Conference on Software Engineering (ICSE)},
  year      = {2026},
  publisher = {ACM}
}
```

### A5. ★ refs.bib: ChatIoT articleno 110 → **103** (원문 ACM ref format 확인됨)

### A6. ☆ §1 C3 문구 주의 (아직 미적용, M4 실측 후 결정)
"verification runs in milliseconds"는 실측상 **median 1.7ms / worst ~21s** (x86; M4 재측정 예정).
M4 수치 나오면 "verification completes in milliseconds at the median"으로 완화 권장.

---

## B. §3 이후 (충돌 없음, 바로 반영 가능)

### B1. ★ §3 instability 문단: surface 그룹 재정의 (자체 데이터와 모순 수정)
기존: surface = (SEL, AND, VAR, **ADD**) ... "flip 6–9%"
→ 실데이터: SEL 2.5%, AND 6.9%, VAR 8.7%, **ADD 28.1%** (ADD는 surface 범위 밖)
교체:
```latex
The rewrite types divide into surface rewrites (SEL = selector order, AND =
$A{\wedge}B{\leftrightarrow}B{\wedge}A$, VAR = variable renaming) and
logic/arithmetic rewrites (ADD = $x{+}n{\leftrightarrow}n{+}x$, BR = branch swap,
DN = double negation, DM = De Morgan, IDM = idiom replacement)
(Figure~\ref{fig:instability}). Purely surface rewrites already flip up to 9\% of
the 9B judge's verdicts (14\% for the cloud judge), and logic and arithmetic
rewrites flip up to 81\%.
```
※ instability figure에 그룹 구분선/색이 있으면 ADD를 logic 쪽으로 옮겨 figure도 일치시킬 것.

### B2. ☆ §4 중복 문장 삭제
"OVLA is organized around a single principle..." 문단의 둘째 문장
"\emph{Precisely because} lowering is an LLM stage, a deterministic checker is needed." 삭제 (§1과 중복).

### B3. ☆ §6.1 첫 문단 cross-ref
"As \S2 and \S3 showed, the execution DSL has no primitives" → "As \S2 observed, ..."

### B4. ☆ §7 No-cloud co-design 문단 (§1과 중복 제거)
기존 둘째 문장("The same decision is also...one design decision yields both trust and deployability.") 교체:
```latex
The no-cloud assumption excludes a cloud LLM judge from the gate, so the gate must
be a deterministic, LLM-free check; the instability results of \S3 show that the
same constraint-driven choice is independently justified.
```

### B4b. ☆ §7 routing 문단 단어 교정 (금지어 가드)
- "as **verified** automations accumulate" → "as **verifier-passed** automations accumulate"
- "generic retrieval over **unverified** examples" → "... over **unchecked** examples"

### B5. ★ §8 Setup 수정 (약속-이행 정합 + 용어)
- Baseline 문장: "for every judge we state the prompt, the input artifact (IR, code, rendering, or trace), temperature, retries, and voting" →
```latex
for every judge we state, with the result it accompanies, the input artifact
(request, IR, or code), temperature, and voting configuration.
```
- Metrics: "safety (silent-wrong deployed)" → "safety (silently divergent code deployed)";
  "feasibility (latency distribution, memory, power)" → "on-device cost (latency distribution, memory, power)"
- Hardware: "(feasibility is measured on the M4" → "(on-device cost is measured on the M4";
  "zero silent-wrong is invariant" → "zero silent divergence is invariant"

### B6. ★ §8.1 RQ1: reject 산수 + over-reject 정체 (가장 중요한 수정)
기존: "(11 repaired, 24 rejected fail-closed, at the cost of over-rejecting 2 correct candidates)"
교체:
```latex
OVLA's bounded IR↔code check reduces this to zero: of the 35, 11 are repaired and
24 are rejected fail-closed; 2 further commands are rejected, for 26 rejections in
total. The 2 further rejections are not verifier false positives: in both, every
gated-run regeneration contained a real syntax or catalog violation within the
2-attempt repair budget, while the ungated run's independent generation of the same
command happened to be correct. The cost is generation variance, 2 of 347 commands
with a correct ungated lowering (0.6\%), not a misjudged program.
```
근거(아티팩트 검증 완료): C09_3=stray-paren parse error×2, C09_16=비실재 메서드명
(`SetAirPurifierMode`/`Off`) catalog 위반×2. rejected_fail_closed=26=24+2.

- 같은 절 "Repair is not the safety evidence" 문단에 1문장 추가:
```latex
Because the gate is deterministic, this property does not depend on generation
stochasticity: whichever candidates the model produces, a divergent one cannot
deploy silently.
```
- 같은 문단 "and the 2 over-rejects alongside" → "and the 2 generation-variance rejections alongside"

### B7. ★ §8.2 real layer 문장 (RQ1과의 이중계상 명시)
"...were flagged, and zero silent-wrongs escaped." →
```latex
...were flagged, and none escaped silently (the same 35 cases as \S8.1, restated
here as detection rather than additional evidence).
```

### B8. ★ §8.2 survivor 문장 (표와 모순 수정 — 아티팩트 재검증 완료)
기존: "8 are >=→> comparators ..., 1 is a dropped duplicate call in a fan-out, and 2 are arithmetic read-modify-write cases..."
교체:
```latex
The 11 survivors are characterized exhaustively rather than bucketed: 8 are
\texttt{>=}→\texttt{>} comparator mutants on sustain tick-counters whose 1-tick
difference lies below the tolerance (max 500ms, 10\%; by design); 1 is a dropped
duplicate call in a two-room fan-out (\texttt{call\_drop}); and 2 sit in a single
arithmetic read-modify-write automation that boundary seeding cannot reach (one
\texttt{call\_drop}, one \texttt{cmp\_direction}), the continuous-arithmetic limit
of \S6.5.
```
(survivors 실명단: comparator×8=C07_21,C20_1..7; call_drop=C08_32,C14_4; cmp_direction=C14_4)

### B9. ☆ §8.2 three-claims 문장 ② 교정
"② it detects neighboring construct faults (mutation neighbor-kill)" →
"② a one-construct perturbation of correct code is caught (the mutation kill rate)"

### B10. ★ §8.2 circularity 방어 2문장 추가 ("every construct is reached..." 문장 뒤)
```latex
Mutation alone, being keyed to the same construct set the verifier checks, measures
the reach of the mechanism rather than external validity; external validity rests
on the real-fault layer above, and the implementation-side coverage shows the
synthesized scenarios exercise the generated code, not only the spec.
```

### B11. ★ §8.2 "vs. an LLM judge" 문단 전체 교체 (P=0.71는 죽은 수치 — 어느 아티팩트에도 없음)
```latex
\textbf{vs.\ an LLM judge.} We compare the same IR↔code judgment against an LLM
judge in the cloud-judge style of ChatIoT's Evaluator~\cite{chatiot}. The judge is
given the IR, the JoI grammar, and the same equivalence definition including the
timing tolerance, at temperature 0 with a single query; ground truth is objective
(a verifier-clean lowering is correct, a non-trace-equivalent mutant of it is
wrong). On 346 such programs (277 faulty, 69 correct), the 9B judge misses 36 of
the faulty programs (recall 0.87) and falsely rejects 17 of the 69 correct ones; a
strong cloud judge (GPT-5.1) still misses 16 (recall 0.94) and falsely rejects 14.
On 30 behaviorally-correct idiom variants of the same intents (multi-GT), the 9B
judge over-rejects 2 and the cloud judge 1, while the trace check passes all 30
idiom-invariantly. (This setting gives the judge the IR; it is a different
experiment from the NO-IR motivating experiment of \S3.)
```
근거 파일: injected_9B_direct.json(R .870/FP 17), injected_gpt51_direct.json(R .942/FP 14),
multigt_9B.json(FP 2/30), multigt_gpt51_explicit.json(FP 1/30).

### B12. ★ §8.4 제목/문구 (feasibility 용어 충돌 해소)
- 제목: "RQ4: On-Device Feasibility and Deployment" → "RQ4: **On-Device Cost** and Deployment"
- 본문 "\textbf{Feasibility.} We report latency..." → "\textbf{On-device cost.} We report latency..."

### B13. ★ §8.4 Deployment 문단 교체 (익명화 + 9케이스 출처 + 73/52 정합)
```latex
\textbf{Deployment.} On a commercial home-automation platform (name withheld for
review) with a Raspberry Pi based edge hub and about ten physical devices, we
register 12{--}15 automations as a demonstration (an existence proof, not
statistics). Of the 382 automations, 73 are physically realizable on this testbed
(temperature readings are provided by an air-quality detector); the registered set
covers the idiom families of \S8.2 and includes the 9 cases from the \S8.1 runs in
which the verifier intervened on this subset (7 rejects, 2 repairs). The
representative scenario is a meeting-room sustain automation: when presence stays
false for 10 minutes, all meeting-room lights must turn off, whereas the buggy
lowering turns them off after 1 minute; Figure~\ref{fig:rq4}(b) shows the observed
device trace against the IR-predicted trace, without and with the gate.
```
근거: deployment_pool.json (9케이스 재유도: reject 7 = C03_24,C16_5,C23_1,C23_3,C23_4,C24_2,C24_4 /
repair 2 = C20_9,C23_5; 73-set 기준. Mysmax 실명은 double-blind 위반이라 삭제).

### B14. ☆ §9 Limitations: "variable-to-variable comparisons, quantifiers, arithmetic"
→ "variable-to-variable comparisons and arithmetic" (실데이터의 9건 = 7 var-var + 2 arith)

---

## C. 오늘 새로 나온 결과 → 논문에 추가할 것 (데이터 준비됨/진행 중)

### C1. ★ 3-모델 generator 표 (§8.1 또는 §8.4) — gemma 끝나면 완성
"보장은 생성 모델과 무관"(C3)의 데이터 증거. 현재까지:
| Generator (4-bit, no FT) | OFF silent-wrong | ON silent-wrong | repaired | rejected | ON deployed-correct |
|---|---|---|---|---|---|
| Qwen3.5-9B (AWQ) | 35 (9.2%) | **0** | 11 | 26 | 356 (93.2%) |
| Qwen3-8B (AWQ)   | 63 (16.5%) | **0** | 16 | 49 | 333 (87.2%) |
| gemma-4-E4B (AWQ) | 57 (14.9%) | **0** | 15 | 45 | 337 (88.2%) |
서사: 모델이 약하면 lowering 오류 최대 1.8배(특히 multi-step C12: 2→14), 그래도 **silent-wrong=0은
3개 모델 모두 불변**. OFF 오류율이 모델 순위와 단조가 아니라는 점(8B>E4B)도 "어떤 생성기가 오든
게이트가 막는다"는 주장에 부합.
LaTeX 표 제안 (§8.1 끝 또는 §8.4):
\`\`\`latex
\begin{table}[t]
\centering
\caption{The gate across generation models (382 automations, confirmed IR).}
\label{tab:models}
\small
\begin{tabular}{lrrrrr}
\toprule
Generator (4-bit, no FT) & \multicolumn{1}{c}{Silent-wrong} & \multicolumn{1}{c}{Silent-wrong} & Rep. & Rej. & Deployed \\
 & \multicolumn{1}{c}{w/o gate} & \multicolumn{1}{c}{w/ gate} & & & correct \\
\midrule
Qwen3.5-9B  & 35 (9.2\%)  & \textbf{0} & 11 & 26 & 356 (93.2\%) \\
Qwen3-8B    & 63 (16.5\%) & \textbf{0} & 16 & 49 & 333 (87.2\%) \\
Gemma-4-E4B & 57 (14.9\%) & \textbf{0} & 15 & 45 & 337 (88.2\%) \\
\bottomrule
\end{tabular}
\end{table}
\`\`\`
※ 표 추가 시 §8.1 RQ1 본문은 9B 수치를 기준으로 유지하고, 표를 가리키는 1-2문장만 추가:
"The same gate holds across generation models: weaker generators produce up to 1.8x more
divergent lowerings, but none deploys silently (Table~\ref{tab:models})."
주의: 8B/E4B arm은 "yields per backend" 문구와 정합; Setup에 세 모델 명시 필요.
M4 배포 모델 = Qwen3-8B(MLX 4-bit) — Setup에 "AWQ on the GPU server, MLX on the M4" 한 줄.

### C2. ★ Verifier latency 분포 — **M4 실측 완료** (`m4_verifier_latency.json`)
M4, 378행×10rep: **p50 0.97ms / p95 0.70s / worst 8.4s / RSS 54MB / CPU 5.5W·GPU 0W**.
- worst는 전부 C19(level-triggered 1초 polling × 7-day horizon → tick 캡 30만) = 비용 축은
  구조 복잡도가 아니라 "명세가 매 tick 행동하는가". boundary 추상은 시나리오 수를 유한하게
  하는 것이고, 한 시나리오 내 JoI 실행은 tick 충실도가 필요(상태 진화 + 발화율이 비교 대상).
- §8.4 권장 문구: "median sub-millisecond; the worst case (8.4s) is the class whose
  specification itself acts on every tick (1-second level-triggered polling), bounded by the
  tick cap, and still cheaper than a single local judge call."
- C3 "runs in milliseconds" → "completes in about a millisecond at the median" 권장 (A6 참조).

### C3. ★ Judge / E2E / 메모리 / 전력 — **M4 실측 완료**
- **Judge per-check** (`m4_judge_latency.json`, 20건): p50 **5.1s** / p95 25.3s.
  → fig:rq4(a) 3-bar 데이터 확정: verifier **0.97ms** vs local judge **5.1s** (측정) vs
  cloud judge (인용: 초 단위 + 과금 + 네트워크 의존). 로그 스케일 권장. p50 기준 ~5,200×.
- **E2E authoring** (`m4_e2e_stage_latency.json`, 1 cold + 9 warm): cold 150.6s,
  warm 70~155s (행 복잡도 의존). prefix cache 효과는 확인됐으나 cache 3GB 한계로
  thrashing 관찰 → "authoring is a one-time cost of a few minutes; the deployed
  automation makes zero LLM calls" 서사로 보고.
- **메모리** (`m4_memory.json`): vLLM Metal peak **11.6GB** (16GB 기기에 fit),
  verifier 프로세스 54MB.
- **전력** (`m4_power.json`): idle ~0.05W / 생성 중 GPU 10.2W mean (peak 11.3) /
  verifier CPU 5.5W·GPU ~0W. "the gate never touches the GPU" 문장 가능.
- 환경 명시: Mac mini M4 16GB, macOS 26.2, vllm-mlx, mlx-community/Qwen3-8B-4bit.
  (정확도 arm은 AWQ 4-bit, M4는 MLX 4-bit — Setup에 1줄: "4-bit quantized Qwen3-8B on
  both backends (AWQ on the GPU server, MLX on the M4)".)

### C4. 남은 TODO
- [x] gemma-4-E4B Stage-B 382 → C1 표 완성
- [x] M4 측정 (verifier 분포/judge/warm e2e/memory/power) — 모델 로드 시간은 제외하기로 결정
- [ ] 실배포: deployment_pool.json의 9케이스 + 통과 자동화로 12–15개 등록, fig:rq4(b) trace 캡처
- [ ] fig:rq4(a)(b) 제작 → figtodo 교체, RQ4 시제 과거형 전환 + 위 실측 수치 본문 반영

---

## D. 참고 (수정 아님, 확인 사항)
- RQ1 11/24/2/26/356 숫자는 아티팩트 재검증 결과 **정확** (_summary 357/25는 배포결정 무관 성적 집계 — 정의 차이)
- instability 27.0%는 진짜 로컬 9B 산출 (아티팩트 메타데이터 `model=gpt-4o`는 스크립트 stale 기본값이었음 — 수정 커밋됨)
- figs/system.pdf, instability.pdf는 Overleaf에만 존재 — 컴파일 확인만
