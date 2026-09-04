# Results Audit

`results-audit.json` is the canonical machine-readable audit record. This
Markdown view does not promote development numbers into paper evidence.

## Audit Summary

- Paper ID: `new-ovla-percom2027`
- Identity version: 1
- Audit status: complete
- Overall caveat: repository validation establishes declared consistency only;
  it does not establish scientific validity or independent verification.

## Audit E3-DEV-MANIFEST-H8

- Claim ID: EC-01
- Bounded verdict: inconclusive
- Attained assurance class: exploratory
- Audited claim effect: inconclusive
- Source: outcome-visible development sweep over all 388 existing generated
  candidates at an eight-tick horizon
- Evidence: 356 comparisons agreed; 27 were unsupported and five failed
  preparation. Of the completed pairs, 213 were bounded-equivalent and 143
  divergent, with A=0 and B=0. The Wilson 95% upper bounds were 2.62% and
  1.77%. Equivalent full-space comparisons used 142,685 exact and 16,372
  Explorer pair-transition evaluations (88.5% fewer); maximum Explorer time
  was 81.14 ms.

The harness is useful for continued development: it exposed one timer-age
false accept, and the repaired bounded Explorer subsequently agreed with exact
tick traversal under the stress model. The results do not support the
abstract's final A/B or R claims. Cases were visible during development, both
sides share one-step runners, and the outcome-blind serialized domains still
come from shared static axis analysis.

The minimum corrective action is to independently review and freeze the input
manifest, version the implementation, execute E1 interpreter conformance, and
run a distinct held-out A/B set without method changes.

## Audit E3-HELDOUT-GEMMA-V2-H32

- Claim ID: EC-01
- Bounded verdict: supports_exploratory_follow_up
- Attained assurance class: exploratory
- Audited claim effect: strengthen
- Scope: all 388 preregistered Gemma-4-26B attempts; 309 statically READY
  pairs; frozen finite input manifest; 32 logical ticks
- Evidence: all 309 READY pairs completed. The exact traversal labeled 228
  bounded-equivalent and 81 divergent, and Behavioral Explorer agreed on all
  of them (A=0, B=0). Exact and Explorer evaluated 424,105 and 109,834
  pair-transitions on full-space equivalent pairs, a 74.1% reduction. The
  metadata-corrected retry had median 0.60 ms, p95 50.67 ms, and maximum
  268.14 ms Explorer time.

The case set was fixed before generation, the first 388-error generation
attempt was retained, and the successful v2 candidate and input manifests were
frozen before A/B outcomes. All 63 generation errors, 15 unsupported cases,
and one preparation error remain visible; the Explorer completed 100% of the
309 READY cases. Zero observed errors has Wilson 95% upper bounds of 4.53% for
false accepts and 1.66% for false rejects.

This does not yet support a confirmatory abstract claim. The exact and
optimized searches share one-step runners, the independent E1 pilot covers
only six cases, the input-domain review is not independent, and evaluator
source was not bound from a clean commit before the first outcome. Complete
those gates before inserting N/A/B/R/T into the abstract.

## Audit E3-HELDOUT-GEMMA-V3-H32

- Claim ID: EC-01
- Bounded verdict: supports_confirmatory_claim
- Attained assurance class: confirmatory
- Audited claim effect: strengthen
- Scope: all 388 preregistered post-repair Gemma-4-26B attempts; 311
  statically READY pairs; frozen finite input manifest; 32 logical ticks
- Evidence: exact tick traversal and Behavioral Explorer completed and agreed
  on all 311 READY pairs. Exact traversal labeled 231 bounded-equivalent and
  80 divergent, yielding A=0/80 false accepts and B=0/231 false rejects.
  Equivalent full-space comparisons used 427,685 exact and 113,558 Explorer
  pair-transition evaluations (73.45% fewer). Explorer median, p95, and
  maximum times were 0.65 ms, 52.09 ms, and 280.12 ms.

The v2 domain audit exposed an outcome-relevant input-axis omission before v3
generation. The repair was regression-tested only on v2, the evaluator was
committed, and all 388 v3 cases were selected before the new model sample was
drawn. Candidate hashes, explicit input domains, initial states, periods, and
H=32 were frozen before A/B inspection. A static read audit that does not use
the Explorer's axes covered all 311 READY cases. The remaining outcomes—61
generation errors, 15 unsupported pairs, and one preparation error—remain in
the denominator accounting. Wilson 95% upper bounds are 4.58% for false
accepts and 1.64% for false rejects.

The supported confirmatory claim is deliberately narrow: within these frozen
finite models and H=32, the optimized search agrees with exhaustive tick
traversal and evaluates fewer pair transitions. It does not establish that
the shared IR/code one-step runners implement every intended domain semantic,
nor that the verifier has 100% population accuracy. Those broader claims
still require expanded E1 conformance and E2 adequacy evidence.
