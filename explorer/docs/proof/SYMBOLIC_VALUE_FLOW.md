# Symbolic value flow v1 — plan and proof boundary

Goal: compare observable input copies and string interpolation without enumerating
the full catalog domain. This supplements the existing concrete BFS, preserving
the agreed D7 refusal policy and all existing explicit-domain behavior.

Later user-approved extension: [SMT trace verification](SMT_VERIFICATION.md)
adds a separate arithmetic fallback. This file still describes the copy/text
path; its D7 statements do not prohibit the new independently checked path.

Implementation plan:

1. Introduce typed input symbols `(grounded read key, input epoch)` and normalized
   text terms. Execute assignments, reads, calls and fixed delays through the
   existing IR/JoI runners; lift only string conversion/concatenation.
2. Certify sequential one-shot programs without input-dependent control flow.
   Identical symbolic ACTION observations prove equality under every valuation.
   Different expressions require a concrete, replayed counterexample; unsuccessful
   witness search is UNKNOWN, never equality or an unconfirmed difference.
3. Connect the fallback to the timed engine/gate and development evaluator when
   automatic observable domains cannot be materialized or exceed the input-combination
   budget. Explicit finite models keep
   the concrete BFS and exact oracle. Do not relabel historical evaluation outputs.
4. Test real C01_009/C01_017/C01_018, source/argument/time mutations, reassignment,
   string normalization, nullable values, numeric representations and fail-closed
   boundaries. Record the proof obligations and current outcomes below.

Scope: catalog-backed sequential one-shot IR READ/CALL/DELAY/END and JoI
assignment/ACTION/fixed delay; literal query arguments; no clock/GV, branches,
loops, waits, periodic schedules or input arithmetic on this new path. Other
programs retain their existing BFS support/refusal. A variable's source is its
executed assignment, never its name or just its declared type.

The input epoch is `floor((now_ms - t0_ms) / input_step_ms)`. Different reads of
the same device/member/query-argument key within an epoch share a symbol; different
epochs are independent. Fixed delays retain exact 1ms deadlines. Missing non-BOOL
values remain permitted inputs except MenuProvider.GetMenu, which is non-null
STRING under the user-approved `menu-string-return-v1` contract. Conversion maps None to empty text, while direct
None ACTION arguments remain invalid under the existing catalog contract.

## Implemented proof obligations

Let U_k be the catalog domain (including the agreed missing/representation
policy), and let a valuation rho assign one element of U_k to every `(k, n)`.
The meaning of an InputSymbol is rho(k,n). The meaning of a TextTerm is the
concatenation of its literal pieces and converted symbols, with `None -> ""`
and otherwise the concrete interpreter's `str` conversion. Numeric source
symbols do not discard the distinction between int, float or signed zero.

1. **Expression preservation.** A read at time t produces `(key, floor((t-t0)/D))`.
   A variable access copies its current register term, so aliases and executed
   reassignments preserve their actual provenance. Literals keep their concrete
   values. The lifted `+` is allowed only with a guaranteed string operand;
   therefore conversion followed by concatenation agrees with the concrete
   operation under every rho. Nullable raw STRING + raw STRING is not assumed
   to be concatenation, because None + None evaluates numerically. Template
   insertion uses the same conversion. Flattening nested TextTerms, deleting
   empty literals and merging adjacent literals preserve concatenation.
2. **Execution preservation.** Structural eligibility excludes all branches,
   loops, waits, input arithmetic, clock/GV reads and repeating schedules from
   this path. Program counters, termination and fixed-delay deadlines thus do
   not depend on rho. By induction over executed instructions, substituting rho
   into each symbolic register/ACTION gives the concrete register/ACTION.
   Existing concrete runners perform the execution; no third DSL interpreter
   chooses assignments, selectors, query keys or call order.
3. **History coverage.** Symbols for different read keys or input epochs are
   independent; repeated reads in the same epoch share the same symbol. Every
   allowed input history induces a rho, and every rho on accessed symbols has
   an extension to such a history. Captured values retain their original epoch
   across delays. The existing event scheduler visits input boundaries and exact
   deadlines, applies new input on ties, and respects the inclusive horizon.
   Unread future inputs cannot affect a terminated one-shot program.
4. **ACTION validity and equality.** Catalog validation accepts a TextTerm only
   for an unrestricted STRING argument: it is a valid string under every rho.
   Raw nullable arguments and other unproved domain inclusions are refused.
   The existing observation function retains method, targets, arguments, call
   order and multiplicity, commuting only independent targets within a fanout.
   Equal normal forms therefore imply equal concrete ACTION observations for
   every rho. This is a sufficient equality test, not a complete word-equation
   solver. Equal variable names/types alone do not establish equality.
5. **Verdicts.** If every visited observation is symbolically equal, the above
   induction proves B(H) from PROOF_OBLIGATIONS.md for all catalog-valued histories
   within the specified horizon. A completed one-shot has an absorbing closure;
   its unbounded invocation can also finish. Bounds/caps retain existing labels.
   Unequal terms only trigger a bounded search for a concrete valuation. Witness
   inputs pass catalog/precision checks and the ordinary concrete runners replay
   the difference. Failure to find/replay a witness or exhausting resources is
   UNKNOWN, folded to REFUSED at the gate. Sampling never establishes equality.

These are a manual argument and code correspondence, not machine verification
of the entire Python implementation. Tests check correspondence and regressions;
they do not replace the quantified argument.

## Integration and current results

`timed_product` attempts this path when automatic catalog-domain materialization
raises Unsupported, or an automatically inferred finite input product exceeds the
input-combination/initial-transition budget, and the pair meets the structural
preconditions. Otherwise
the original concrete BFS/refusal remains. `gate_pair` delegates automatic models
to the timed engine. Explicit finite input domains always keep their original
concrete meaning and never become a full-catalog claim.

Each result carries a JSON `symbolic_certificate`: input specifications, origin,
event times and both symbolic observations. The development/frozen evaluators
label successful certificates `SYMBOLIC_CERTIFIED`; the finite enumeration oracle
is `NOT_APPLICABLE` on this path. Do not count that as oracle agreement or include
it in paired Explorer/oracle speed measurements. Old frozen outputs are unchanged.

- C01_009: EQUIV-BOUNDED(3200ms), one paired symbolic step, full temperature
  domain; no 104,701-value enumeration.
- C01_017, using the approved repaired IR and unchanged candidate code:
  EQUIV-BOUNDED(3200ms), one paired symbolic step, arbitrary menu STRING plus
  missing input handled by text insertion.
- C01_018: still REFUSED, now specifically because a raw nullable query result
  can reach Speak's required STRING argument. An explicit nonmissing finite model
  passes only for that model; None concretely reproduces the type violation.
  A separate test converting the result to text on both sides proves universal
  equality, including None. Neither dataset nor candidate was rewritten for this.

Validation: 25 new regressions, including 54 expression valuations and 81 captured
input histories per runner (162 runner histories, three events each), plus the
159 existing regressions. Fixed-delay/time-origin, source/member/query-argument,
overwrite/static-output, target/count/order, nullable/type/representation, cap,
replay and evaluation-route cases are covered. Evidence is recorded in
`eval/results/symbolic_value_flow_2026-09-07_v1.json`.

## Menu return contract update (2026-09-07)

The earlier C01_018 refusal above is historical. Under the user-approved
`menu-string-return-v1` contract, MenuProvider.GetMenu returns arbitrary STRING,
including empty text, and never None. The adapter records `nullable: false` in
its return spec without altering the catalog or dataset. Concrete domains and
replay snapshots enforce it; symbolic inputs carry the same non-null type.
A raw non-null STRING symbol is valid for an unrestricted STRING ACTION argument.
Other domain inclusions still require their existing checks. Witness search uses
only allowed values, including its combined missing-value candidate.

C01_018 now has a universal EQUIV-BOUNDED(3200ms) certificate. The new development
manifest is `eval/contract_v1_menu_string_development.json`; its results contain
five symbolic certificates and four replay-confirmed differences. Historical
manifests/results retain the previous missing-inclusive model.

## Automatic input-cap fallback (2026-09-07)

The timed engine now also attempts symbolic value flow when automatic catalog
inputs exceed the input-combination or initial-transition budget. It records
whether inputs were automatic before materialization. Explicit finite input
lists retain concrete BFS and their original scope; an over-cap explicit list
remains incomplete. GV/control-flow/unsupported shapes retain existing rules.
The symbolic engine still enforces state, transition and witness-search caps.

This changes strategy selection, not the equality theorem: every returned
certificate still discharges the expression, execution, history and ACTION
obligations above. Source identity alone is insufficient; input epoch, copied
value/conversion, target, call order, multiplicity and timing are preserved.

C01_014 reads PM10 and announces it. Its automatic input list has 110,004 values
(including agreed representations/missing), exceeding the 100,000 combination
cap. It now certifies EQUIV-BOUNDED(3200ms) in one paired symbolic step. The
current implementation may still construct the finite input list before
selection; it avoids executing the scenario separately for each value.
Both the development evaluator and frozen manifest preparation select the same
fallback. Exact finite enumeration is NOT_APPLICABLE for these certificates,
not an agreement vote. The historical frozen incomplete result is preserved.

Eight focused tests cover actual C01_014, explicit-domain scope, both budget
boundaries, static output/read-epoch mutations, unsupported control, symbolic
transition exhaustion, and development/frozen preparation/worker integration.
All 194 regressions pass. `eval/results/symbolic_input_cap_2026-09-07_v1.json`
contains six symbolic certifications and six replay-confirmed mutation differences.
The full existing-candidate rerun `contract_recheck_v4_2026-09-07_v2` has
208 bounded equivalents, 76 confirmed differences, 43 refusals, 59 historical
generation errors, 2 preparation errors, and no Explorer incomplete result.
The 267 jointly completed finite-search pairs agree; four symbolic cases are
counted separately. This is outcome-visible development evidence, not holdout.
