# Abstract result wording for the v3 bounded evaluation

## Recommended English sentence

At a 32-tick horizon, Behavioral Explorer matched exhaustive tick-by-tick
traversal on all 311 evaluable IR–code pairs (231 equivalent and 80 divergent),
with no observed false accepts or false rejects, while reducing pair-transition
evaluations by 73.4% on equivalent pairs; its p95 analysis time was 52.1 ms.

## Recommended Korean rendering

32-tick 범위의 평가에서 Behavioral Explorer는 평가 가능한 311개 IR–코드
쌍(동치 231개, 비동치 80개) 모두에 대해 완전 tick-by-tick 탐색과 동일한
판정을 내렸으며, 관측된 false accept와 false reject는 없었다. 또한 동치
쌍에서 pair-transition 평가 횟수를 73.4% 줄였고, 분석 시간의 p95는
52.1 ms였다.

## Denominators and boundaries that must remain visible in the paper

- Total preregistered attempts: 388
- READY and completed: 311 (80.15% of all attempts; 100% of READY pairs)
- Exact labels: 231 bounded-equivalent, 80 divergent
- False accepts: 0/80; Wilson 95% upper bound 4.58%
- False rejects: 0/231; Wilson 95% upper bound 1.64%
- Non-READY: 61 generation errors, 15 unsupported, one preparation error
- Transition reduction: 427,685 exact versus 113,558 Explorer evaluations,
  measured only on the 231 full-space equivalent pairs
- Explorer latency: median 0.65 ms, p95 52.09 ms, maximum 280.12 ms on an
  Intel Core i9-11900K
- Scope: the frozen per-case finite input models and H=32

Do not paraphrase the result as “100% verifier accuracy.” The exhaustive
oracle and Explorer share the concrete IR/code one-step runners, so this
experiment validates the Explorer's search reductions. Independent semantic
conformance of those runners is a separate E1 obligation.
