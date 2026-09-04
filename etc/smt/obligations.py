"""Assumption-switch decomposition of the miter's divergence query.

The miters used to assert one monolithic query:

        s.add(Or(*every_mismatch_disjunct))

One check() answers "do the two programs diverge anywhere?" — sufficient for
a gate, but opaque: an UNSAT certifies everything at once and a SAT model
names nothing. The relational (code↔code) miter needs per-contract verdicts
("the preserved role's emissions on THIS output channel are unchanged"), so
the same disjuncts are grouped here into labeled *obligations*, keyed by
output signature (method/arity — the unit a role contract talks about), and
each is installed behind an assumption switch b_k:

        s.add(Implies(b_k, Or(disjuncts_k)))     for every obligation k
        s.add(Or(*switches))                     # keeps plain check() meaningful

Both query styles then coexist on one solver:

  * s.check()      — the monolithic query, verdict-identical to the old
                     encoding (Or over switches forces >= 1 violated
                     obligation, and each true switch forces its violation);
  * s.check(b_k)   — the per-obligation query: "can obligation k alone be
                     violated?"  UNSAT = that contract is preserved, with its
                     own (smaller) proof; SAT = a counterexample localized to
                     one named output channel.

Label vocabulary used by the encoders:

    sig:<method>/<nargs>     M1 per-action value/time disagreement
    shape:count|method       M1 action-list shape disagreement on a path pair
    align:<method>/<nargs>   ordered/run engines: i-th emission differs
    count:<method>/<nargs>   ordered/run engines: emission counts differ
"""

from __future__ import annotations

from dataclasses import dataclass

import z3


@dataclass
class Obligation:
    label: str
    disjuncts: list


class ObligationSet:
    """Ordered, label-grouped collection of divergence disjuncts."""

    def __init__(self) -> None:
        self._by_label: dict[str, Obligation] = {}

    def add(self, label: str, expr) -> None:
        ob = self._by_label.get(label)
        if ob is None:
            ob = self._by_label[label] = Obligation(label, [])
        ob.disjuncts.append(expr)

    def __len__(self) -> int:
        return len(self._by_label)

    def install(self, s: z3.Solver, tag: str = "ob") -> "Installed":
        switches: dict[str, z3.BoolRef] = {}
        violations: dict[str, z3.BoolRef] = {}
        for i, ob in enumerate(self._by_label.values()):
            viol = ob.disjuncts[0] if len(ob.disjuncts) == 1 \
                else z3.Or(*ob.disjuncts)
            b = z3.Bool(f"{tag}!{i}!{ob.label}")
            s.add(z3.Implies(b, viol))
            switches[ob.label] = b
            violations[ob.label] = viol
        # no obligations at all → the programs cannot disagree → plain
        # check() must stay UNSAT, as the old `Or([]) = False` did
        s.add(z3.Or(*switches.values()) if switches else z3.BoolVal(False))
        return Installed(switches, violations)


@dataclass
class Installed:
    switches: dict[str, z3.BoolRef]
    violations: dict[str, z3.BoolRef]

    @property
    def labels(self) -> list[str]:
        return list(self.switches)

    def violated_in(self, model) -> list[str]:
        """Which obligations does this witness violate?  Evaluated on the
        violation expressions directly — switch values are not trusted, since
        model completion may set an unconstrained switch arbitrarily."""
        return [lbl for lbl, v in self.violations.items()
                if z3.is_true(model.eval(v, model_completion=True))]


def decide(s: z3.Solver, inst: Installed, extract,
           timeout_ms: int = 0, split: bool = False,
           timeout_verdict: str = "UNKNOWN") -> dict:
    """Run the divergence query and shape the verdict fragment.

    split=False — one monolithic check(), exactly the pre-refactor gate; on
    DIVERGE the witness is additionally attributed to the obligations it
    violates (`violated`).
    split=True — one check(b_k) per obligation; per-label verdicts in
    `obligations`, overall DIVERGE iff any obligation is violable.
    """
    if timeout_ms:
        s.set("timeout", timeout_ms)

    if not split:
        res = s.check()
        if res == z3.unsat:
            return {"verdict": "EQUIV"}
        if res == z3.sat:
            model = s.model()
            return {"verdict": "DIVERGE", "model": extract(model),
                    "violated": inst.violated_in(model)}
        return {"verdict": timeout_verdict}

    per: dict[str, str] = {}
    violated: list[str] = []
    model_out = None
    incomplete = False
    for lbl, b in inst.switches.items():
        res = s.check(b)
        if res == z3.sat:
            per[lbl] = "DIVERGE"
            violated.append(lbl)
            if model_out is None:
                model_out = extract(s.model())
        elif res == z3.unsat:
            per[lbl] = "EQUIV"
        else:
            per[lbl] = timeout_verdict
            incomplete = True
    verdict = "DIVERGE" if violated else \
        (timeout_verdict if incomplete else "EQUIV")
    out: dict = {"verdict": verdict, "obligations": per}
    if violated:
        out["violated"] = violated
        out["model"] = model_out
    return out
