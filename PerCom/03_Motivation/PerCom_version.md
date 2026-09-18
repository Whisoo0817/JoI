# Problem and Motivation — PerCom working draft

> 2026-09-18: 중복 축약 반영본. 아래 본문은 변경 표시를 제외한 현재 원고다. 이번 수정 직전 Overleaf 커밋 `82d4073` 대비 삭제 취소선·추가 빨간색은 `overleaf-paper/main.tex`에서 확인한다.

A deployment check requires an explicit behavioral reference and consistent verdicts. Against the same specification, two programs with the same behavior must receive the same deploy/reject verdict. Repeated evaluations of the same program should likewise agree.

**Candidate checking approaches.** One could ask the model that produced the code to inspect and repair it. However, SimuHome~\cite{simuhome} reports limited recovery from scheduling errors through self-correction. One could show the generated code to the user for approval. However, prior research in TAP-Debug~\cite{tapdebug} demonstrated that non-experts frequently misread even the basic IF (event) and WHILE (state) conditions of raw rules. These findings motivate a behavioral check that does not rely solely on model self-assessment or users' inspection of implementation details.

LLM judge evaluation. Another approach is to hand the request
and the code to a separate LLM to verify whether they align. To evaluate
verdict consistency, we submitted each of 217 JoI programs three times to
Qwen3.5-9B, GPT-5.4-mini, and Claude-Sonnet-5. Each call contained the
natural-language request, language documentation, and one program. We then
evaluated 168 behavior-preserving rewrites of the 52 originals accepted by
every judge in at least two of three evaluations
(Table~\ref{tab:judge}). Both originals and rewrites were verified against their
confirmed Timeline IR under the declared execution model by Behavioral Explorer
(§6).

Temporal structure rewrites. Qwen's three evaluations agreed for every
unchanged original, yet it rejected 31 of 48 temporal rewrites (64.6\%),
compared with 3.8\% for notation and 2.4\% for logic rewrites. These rejections
included 10 of 11 loop-unrolling variants and 16 of 17 variants that halved the
execution period while using a flag to execute the body on alternate
iterations. Under the tested configuration, repeatability on identical code did
not ensure consistent verdicts across implementations with the same timed
behavior.

Repeated evaluations. GPT and Claude produced different verdicts across
the three identical submissions for 36 and 21 of the 217 originals (16.6\% and
9.7\%), respectively. Their verdicts thus varied even without changes to the
code. Because the table's repeated-evaluation and rewrite rows use different
populations and definitions, they do not isolate an additional effect of
rewriting for these judges.

Implications. Qwen's sensitivity to temporal rewrites and the hosted
judges' disagreement on unchanged code undermine reliance on these judges alone
for deployment decisions under the tested conditions. The experiment assesses
verdict consistency, with rewrite results conditional on the common accepted
set. It does not measure bug-detection accuracy, and consistency alone would not
establish correctness.

**Design direction.** VETS uses the confirmed Timeline IR as the executable reference for checking generated code, as described in Section~\ref{sec:system-overview}.

---

## Table 1 — working placement

> 본문의 Table~\ref{tab:judge}에 대응하는 작업용 표시다. 수치와 캡션은 `motivation_judge/results/table1.tex`와 동기화했다. 표·캡션의 굵은 차분 표시는 생략한다.

Table 1. LLM-judge verdict inconsistency. None repeats unchanged programs; other rows apply behavior-preserving rewrites.

| Rewrite | n | Qwen3.5-9B | GPT-5.4-mini | Claude-Sonnet-5 |
| --- | ---: | ---: | ---: | ---: |
| None | 217 | 0.0 | 16.6 | 9.7 |
| Notation | 79 | 3.8 | 12.7 | 3.8 |
| Logic | 41 | 2.4 | 14.6 | 9.8 |
| Temporal | 48 | 64.6 | 2.1 | 6.2 |
| All | 168 | 20.8 | 10.1 | 6.0 |

## 이전 편집 기록 (2026-09-18 축약 전, 논문 본문 아님)

- M1–M7은 위 일곱 본문 문단을 뜻한다. SenSys의 요구사항 → 검사 대안 → judge 실험 → 설계 방향을 유지하고 R1·R2는 M1, 세 candidate는 M2에 통합했다. R3 on-device/privacy, 렌더링, 모든 후보의 배제·유일한 해법 주장은 삭제했다.
- 실험 수치는 `motivation_judge/RESULTS_2026-09-16.md`의 최종 공통집합을 따른다. 471쌍은 검증된 전체 집합, 168쌍은 Table 1의 재작성 분모다. 동일 코드 3회 평가는 217개 전체를 사용한다.
- 동등성 근거는 본 연구의 동결 Explorer다. Judge 판정과는 별개이나 VETS와 독립된 검증 도구는 아니다. 이 실험을 Explorer 정확도의 독립 평가로 쓰지 않는다. Judge에는 확정 IR을 제공하지 않는다.
- 본문은 기존 Fig. 2와 voting 표를 사용하지 않는다. 표의 행·모델·수치는 기존 Table 1을 보존했다. 짧은 캡션을 `render_table.py` 및 생성된 `.tex`와 동기화했다. 변환별 불완전한 열거 대신 세 분류의 의미를 설명한다.
- 재검토 후 M1의 reference 설명 중복과 M3의 전체 후보 규모 설명을 줄였다. M4는 동일 코드 반복 일치와 시간 구조 재작성 거부의 대비로 시작하고, M5는 GPT·Claude의 반복 불일치에 집중한다. M6는 모델별 관찰과 결론의 범위를 구분한다. M7은 reference 요구와 일관성 관찰을 함께 받아, 같은 확정 IR을 기준으로 한 코드 생성과 행동 검증으로 연결한다.
- 기존 초안의 Moon 인용 문장은 이번 압축에서 제외했다. 이 절은 자체 reactive-temporal 실험으로 직접 연결하며 신규 문헌을 추가하지 않는다. On-device·SLM framing은 전체 초안 완성 후 통합하기로 했으므로 이번 본문에는 반영하지 않았다.
- 실험 상세에 남길 사항: 정확한 모델 식별자와 설정(Qwen temperature 0, hosted 모델은 사용 API에서 temperature 조정 불가), 원본 단위 bootstrap 2,000회의 구간, Qwen 예산 강제 200/1,122건, 오류·무효 응답 0건, 변환별 결과, E3와 씨앗 공유. `period_halve`는 초기 결과를 본 뒤 추가했고 추가 규칙은 해당 judge 결과를 열기 전에 고정했다. 이 경위는 `PROTOCOL_2026-09-16.md` §8을 근거로 부록 또는 실험 상세에 반드시 공개한다. 부록 위치는 아직 미정이다.
- 3회 중 2회 통과는 만장일치가 아니다. 공통집합 선정이 자연어의 모호함을 제거하거나 NL 대비 정답을 확정했다고 주장하지 않는다. None과 재작성 비율을 빼서 재작성의 순효과를 추정하지 않는다.
- 문헌 확인: [SimuHome §5.4](https://arxiv.org/html/2509.24282)는 workflow self-correction 결과이며 JoI 코드 검사 결과가 아니다. [TAP-Debug](https://people.cs.uchicago.edu/~shanlu/paper/UbiComp23.pdf)는 event/state 조건 해석의 어려움을, [Moon et al.](https://aclanthology.org/2026.findings-eacl.70/)은 코드 judge의 surface variation 민감성을 뒷받침한다. 이 연구들로 모든 self-checking·human inspection·LLM judge가 불가능하다고 결론짓지 않는다.
