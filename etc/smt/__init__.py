"""SMT-based IR↔JoI trace-equivalence gate (OVLA v2).

Replaces the simulator-based boundary-trace verifier with a symbolic
translation-validation check: encode the Timeline IR and the generated JoI
block as symbolic transition systems and ask the solver for a divergent
input trace (UNSAT = equivalent within the modeled fragment).

Modules:
    fragment  — M0: classify (IR, JoI) pairs into encoder fragments
                (oneshot / periodic-affine / cron / fail-closed).
"""
