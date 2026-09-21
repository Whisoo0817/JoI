"""Evaluate the agreed time/input contract, separately from historical H-ticks.

python3 -m explorer.eval.contract_eval --manifest MODEL.json --output RESULT.json
Each case declares ir, binding, devices, joi_block, input_domains, horizon_ms;
input_step_ms defaults to 100. Results are development evidence, not E1 proof.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from explorer.tests.oracles.exact_timed import exact_timed_product
from explorer.verification.gate import prepare_pair, pair_input_domains
from explorer.runtime.interp import Unsupported
from explorer.verification.product import replay_divergence, check_supported_pair
from explorer.verification.timed import timed_product


def evaluate_case(case):
    row = {"id": case["id"], "status": "INCOMPLETE"}
    try:
        pair = prepare_pair(case["ir"], case["binding"], case["devices"], case["joi_block"],
                            service_catalog=case.get('service_catalog', True))
        if case.get('verification_mode') == 'relational':
            optimized = timed_product(pair.ir_runner, pair.code_runner,
                verification_mode='relational', horizon_ms=case.get('horizon_ms'),
                input_domains=case.get('input_domains'),
                initial_gv_domains=case.get('initial_gv_domains'),
                input_step_ms=case.get('input_step_ms', 100),
                t0_ms=case.get('t0_ms', 2_419_200_000), **case.get('explorer_caps', {}))
            replays = [replay_divergence(pair.ir_runner, pair.code_runner, d)
                       for d in optimized.divergences]
            row.update(verification_method='relational-state-v1',
                explorer={**asdict(optimized), 'claim': optimized.claim},
                replays=[asdict(r) for r in replays],
                exact={'verdict': 'NOT_APPLICABLE',
                       'reason': 'finite simulation cannot certify unbounded inductive closure'})
            row['status'] = ('RELATIONAL_CERTIFIED' if optimized.claim == 'EQUIV-FIXPOINT'
                else 'DIVERGE_CONFIRMED' if any(r.confirmed for r in replays) else 'INCOMPLETE')
            if case.get('expected_verdict') is not None and optimized.claim != case['expected_verdict']:
                row.update(status='EXPECTED_MISMATCH', expected_verdict=case['expected_verdict'])
            return row
        try:
            from explorer.verification.smt import smt_specs
            if case.get('input_domains') is None and not case.get('initial_gv_domains') and smt_specs(pair.ir_runner, pair.code_runner) is not None:
                raise Unsupported('arithmetic fragment: select SMT trace verification')
            domains = pair_input_domains(pair, case.get('input_domains'))
            if case.get('input_domains') is None and not case.get('initial_gv_domains'):
                from explorer.verification.symbolic import symbolic_input_cap_fallback
                caps = case.get('explorer_caps', {})
                if symbolic_input_cap_fallback(pair.ir_runner, pair.code_runner, domains,
                        max_input_combinations=caps.get('max_input_combinations', 100_000),
                        max_transitions=caps.get('max_transitions', 2_000_000)):
                    raise Unsupported('automatic input combination cap: select symbolic value flow')
        except Unsupported:
            if case.get('input_domains') is not None:
                raise
            model = {'horizon_ms': case['horizon_ms'],
                     'input_step_ms': case.get('input_step_ms', 100),
                     't0_ms': case.get('t0_ms', 2_419_200_000),
                     'initial_gv_domains': case.get('initial_gv_domains')}
            optimized = timed_product(pair.ir_runner, pair.code_runner, **model,
                                      **case.get('explorer_caps', {}))
            if not optimized.symbolic_certificate:
                raise
            replays = [replay_divergence(pair.ir_runner, pair.code_runner, d)
                       for d in optimized.divergences]
            row.update(model={**model, 'input_domains': None},
                input_domain_basis='universal catalog symbolic inputs',
                verification_method=optimized.symbolic_certificate['schema'],
                service_model=pair.service_model.evidence(),
                exact={'verdict': 'NOT_APPLICABLE',
                       'reason': 'finite enumeration oracle does not certify symbolic domains'},
                explorer={**asdict(optimized), 'claim': optimized.claim},
                replays=[asdict(r) for r in replays])
            row['status'] = ('SYMBOLIC_CERTIFIED' if optimized.verdict == 'EQUIV' else
                'DIVERGE_CONFIRMED' if optimized.verdict == 'DIVERGE' and any(r.confirmed for r in replays)
                else 'INCOMPLETE')
            if case.get('expected_verdict') is not None and optimized.claim != case['expected_verdict']:
                row.update(status='EXPECTED_MISMATCH', expected_verdict=case['expected_verdict'])
            return row
        # Preserve D7 even though the independent oracle can enumerate more.
        axes = check_supported_pair(pair.ir_runner, pair.code_runner, input_domains=domains)
        from explorer.verification.input_coverage import initial_domains
        model = {"input_domains": domains, "horizon_ms": case["horizon_ms"],
                 "input_step_ms": case.get("input_step_ms", 100),
                 "initial_gv_domains": initial_domains(axes, case.get("initial_gv_domains")),
                 "t0_ms": case.get("t0_ms", 2_419_200_000)}
        row["model"] = model
        row['input_domain_basis'] = ('explicit supplied finite values; not a claim of full catalog coverage'
            if case.get('input_domains') is not None else 'catalog domains with certified predicate representatives/exact observable values')
        row['service_model'] = (pair.service_model.evidence() if pair.service_model else
                                {'mode': 'synthetic; no actual catalog conformance'})
        exact = exact_timed_product(pair.ir_runner, pair.code_runner, **model,
                                   **case.get("exact_caps", {}))
        optimized = timed_product(pair.ir_runner, pair.code_runner, **model,
                                  **case.get("explorer_caps", {}))
        replays = [replay_divergence(pair.ir_runner, pair.code_runner, dv)
                   for dv in optimized.divergences]
        row.update(exact=asdict(exact), explorer={**asdict(optimized), "claim": optimized.claim},
                   replays=[asdict(replay) for replay in replays])
        if exact.verdict == "INCOMPLETE" or optimized.verdict == "UNKNOWN":
            return row
        if optimized.verdict == "DIVERGE" and not any(r.confirmed for r in replays):
            row["status"] = "REPLAY_UNCONFIRMED"
        elif (exact.verdict == "DIVERGE") != (optimized.verdict == "DIVERGE"):
            row["status"] = "DISAGREEMENT"
        elif case.get("expected_verdict") is not None and optimized.claim != case["expected_verdict"]:
            row.update(status="EXPECTED_MISMATCH", expected_verdict=case["expected_verdict"])
        else:
            row["status"] = "AGREE"
    except Unsupported as error:
        row.update(status="REFUSED", reason=str(error))
        if case.get('expected_verdict') == 'REFUSED':
            row.update(status='AGREE', refused=True)
    except (ValueError, KeyError, TypeError) as error:
        row.update(status="INVALID", reason=str(error))
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    raw = Path(args.manifest).read_bytes()
    manifest = json.loads(raw)
    if manifest.get("semantics") != "contract-v1":
        parser.error("manifest must declare semantics=contract-v1; historical tick manifests are not interchangeable")
    rows = [evaluate_case({'service_catalog': manifest.get('service_catalog', True), **case})
            for case in manifest["cases"]]
    source_hash = hashlib.sha256()
    for path in sorted(Path(__file__).parents[1].rglob("*.py")):
        source_hash.update(str(path.relative_to(Path(__file__).parents[1])).encode() + b"\0" + path.read_bytes() + b"\0")
    catalog_loader = Path(__file__).parents[2] / 'timeline_ir' / 'catalog.py'
    source_hash.update(b'timeline_ir/catalog.py\0' + catalog_loader.read_bytes() + b'\0')
    result = {"semantics": "contract-v1", "manifest_sha256": hashlib.sha256(raw).hexdigest(),
              "evaluator_sha256": source_hash.hexdigest(),
              "cases": rows}
    # Refuse accidental replacement of historical results.
    with Path(args.output).open("x") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    print(json.dumps({"cases": len(rows), "statuses": {
        status: sum(row["status"] == status for row in rows)
        for status in sorted({row["status"] for row in rows})}}))


if __name__ == "__main__":
    main()
