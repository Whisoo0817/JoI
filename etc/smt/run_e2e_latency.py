"""E2E latency evidence: the two-path claim, measured.

    runtime path  (device dies)     table lookup + hash check     → µs
    offline path  (nightly)         contingency compile, per-row
                                    certification: bounded miter vs induction
    edit path     (NL request)      rules-classify / sLLM-classify + typed
                                    patch + unbounded certification

Live-measures the fast stages (lookup, classify, patch) and collates the
already-recorded solver times (results/certify.json, results/induction.json)
rather than re-running hours of z3.

    python3 -m etc.smt.run_e2e_latency [--llm]
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time

from sim.catalog import load_catalog

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from adapt.contingency import compile_table                  # noqa: E402
from adapt.editir import classify                            # noqa: E402
from adapt.inventory import base_office                      # noqa: E402
from adapt.patch import apply_and_check                      # noqa: E402
from adapt.structure import extract                          # noqa: E402
from adapt.template import load_skeleton, load_template      # noqa: E402

_RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def _med(xs):
    return statistics.median(xs) if xs else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true",
                    help="also time one sLLM classification round-trip")
    args = ap.parse_args(argv)

    catalog = load_catalog()
    inv = base_office()
    out: dict = {}

    # ── runtime path ─────────────────────────────────────────────────────────
    t = load_template("intrusion_alert")
    table = compile_table(t, inv)
    n = 100_000
    t0 = time.perf_counter()
    for _ in range(n):
        row = table.lookup("cam1", table.base_hash)
    lookup_us = (time.perf_counter() - t0) / n * 1e6
    out["runtime_lookup_us"] = round(lookup_us, 2)
    out["offline_compile_table_ms"] = round(table.compiled_ms, 1)
    print(f"[runtime path]  table lookup + stale check: {lookup_us:.2f} µs "
          f"(row -> pre-verified artifact, {row.artifact_bytes}B)")
    print(f"[offline path]  contingency compile (14 devices, slicing+static): "
          f"{table.compiled_ms:.0f} ms/template")

    # ── certification stages (recorded solver times) ─────────────────────────
    cert = json.load(open(os.path.join(_RESULTS, "certify.json")))
    indu = json.load(open(os.path.join(_RESULTS, "induction.json")))
    bounded = [r["elapsed_s"] for r in cert.values()
               if isinstance(r.get("elapsed_s"), (int, float))]
    inductive = [r["elapsed_s"] for r in indu.values()
                 if isinstance(r.get("elapsed_s"), (int, float))]
    out["cert_bounded_s"] = {"median": _med(bounded), "max": max(bounded)}
    out["cert_inductive_s"] = {"median": _med(inductive), "max": max(inductive)}
    print(f"[certification] bounded miter (w=32): median {_med(bounded):.1f}s "
          f"max {max(bounded):.1f}s  |  tick induction: median "
          f"{_med(inductive):.2f}s max {max(inductive):.2f}s per row")

    # ── edit path ────────────────────────────────────────────────────────────
    t = load_template("thermo_comfort")
    src = load_skeleton(t)
    st = extract(src, "thermo")
    nl = "여름 최고 온도 25.5도를 26도로 바꿔줘"
    t0 = time.perf_counter()
    for _ in range(200):
        d = classify(nl, st, template=t, catalog=catalog)
    cls_ms = (time.perf_counter() - t0) / 200 * 1000
    t0 = time.perf_counter()
    for _ in range(200):
        res = apply_and_check(st, d.edits)
    patch_ms = (time.perf_counter() - t0) / 200 * 1000
    t0 = time.perf_counter()
    st2 = extract(src, "thermo")
    extract_ms = (time.perf_counter() - t0) * 1000
    out["edit_rules_classify_ms"] = round(cls_ms, 2)
    out["edit_patch_splice_ms"] = round(patch_ms, 2)
    out["edit_extract_ms"] = round(extract_ms, 1)
    print(f"[edit path]     extract {extract_ms:.0f} ms + rules-classify "
          f"{cls_ms:.2f} ms + typed patch+splice {patch_ms:.2f} ms "
          f"(+ certification above)")

    if args.llm:
        from adapt.editir import classify_with_llm
        nl_free = "여름엔 좀 시원하게, 26도 기준으로 맞춰줘"
        t0 = time.perf_counter()
        d = classify_with_llm(nl_free, st, template=t, catalog=catalog)
        llm_s = time.perf_counter() - t0
        out["edit_llm_classify_s"] = round(llm_s, 2)
        print(f"                free-form via sLLM: {llm_s:.1f} s "
              f"(-> {d.kind}, then the same deterministic path)")

    os.makedirs(_RESULTS, exist_ok=True)
    with open(os.path.join(_RESULTS, "e2e_latency.json"), "w",
              encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\ndetail → {os.path.join(_RESULTS, 'e2e_latency.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
