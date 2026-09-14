"""Compiler-unroll certificate tests for fixed daily aggregation."""
import json
from pathlib import Path
import sys

from explorer.verification.gate import fold_verdict, prepare_pair
from explorer.verification.product import replay_divergence
from explorer.verification.timed import timed_product


ROOT = Path(__file__).resolve().parents[2]
E2 = ROOT / "PerCom/6_Evaluation/E2_fidelity"
DEPTH = ROOT / "PerCom/6_Evaluation/E1_adequacy/breadth/depth"


def _pairs():
    sys.path.insert(0, str(DEPTH))
    from run_depth import lower
    rows = json.loads((E2 / "pairs/e1_pairs.json").read_text())["pairs"]
    out = {}
    for pair in rows:
        if not pair["pair_id"].startswith("E1-095/"):
            continue
        ir, binding = lower(pair["ir"])
        out[pair["pair_id"]] = prepare_pair(
            ir, binding, pair["devices"], pair["joi"],
            service_catalog=str(ROOT / pair["catalog"]), selector_binding=True)
    return out


def test_e1_095_unrolled_verdicts():
    for ident, prepared in _pairs().items():
        result = timed_product(prepared.ir_runner, prepared.code_runner,
                               t0_ms=28 * 86_400_000 + 9 * 3_600_000 + 55 * 60_000)
        expected = "EQUIV" if ident.endswith("/correct") else "DIVERGE"
        assert result.verdict == expected, (ident, result.verdict, result.notes)
        assert result.symbolic_certificate["schema"] == "fixed-aggregation-unroll-v1"
        replays = [replay_divergence(prepared.ir_runner, prepared.code_runner, d)
                   for d in result.divergences]
        gate = fold_verdict(result, replays, prepared.notes)
        assert gate.verdict == expected, (ident, gate.verdict, gate.notes)


def test_dynamic_deadline_does_not_enter_unroll_pass():
    from explorer.verification.fixed_aggregation import fixed_aggregation_product
    rows = json.loads((E2 / "pairs/e1_pairs.json").read_text())["pairs"]
    pair = next(p for p in rows if p["pair_id"] == "E1-099/correct")
    sys.path.insert(0, str(DEPTH))
    from run_depth import lower
    ir, binding = lower(pair["ir"])
    prepared = prepare_pair(ir, binding, pair["devices"], pair["joi"],
        service_catalog=str(ROOT / pair["catalog"]), selector_binding=True)
    assert fixed_aggregation_product(prepared.ir_runner, prepared.code_runner,
        t0_ms=28 * 86_400_000 + pair["t_start_ms"]) is None


def test_side_effecting_else_is_not_admitted():
    from copy import deepcopy
    from explorer.runtime import joi_parser as jp
    from explorer.runtime.expr import Lit
    from explorer.verification.fixed_aggregation import fixed_aggregation_product
    prepared = _pairs()["E1-095/correct"]
    code = prepared.code_runner
    while hasattr(code, "inner"):
        code = code.inner
    mutated = deepcopy(code.stmts)
    mutated[-2].else_body = [jp.Assign("sum_ph", "=", Lit(9))]
    from explorer.runtime.pause import PauseRunner
    from explorer.verification.service_model import CatalogRunner
    bad = CatalogRunner(PauseRunner(mutated, repeat=True, period_ms=1000),
                        prepared.service_model)
    assert fixed_aggregation_product(prepared.ir_runner, bad,
        t0_ms=28 * 86_400_000 + 9 * 3_600_000 + 55 * 60_000) is None


if __name__ == "__main__":
    test_e1_095_unrolled_verdicts()
    test_dynamic_deadline_does_not_enter_unroll_pass()
    test_side_effecting_else_is_not_admitted()
    print("test_fixed_aggregation: 3 passed")
