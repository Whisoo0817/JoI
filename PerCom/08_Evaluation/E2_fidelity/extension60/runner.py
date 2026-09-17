"""Frozen E2 extension executor; see RUNNER_NOTES.md for the protocol and CLI."""
from __future__ import annotations

import argparse
import copy
import functools
import gzip
import hashlib
import importlib.metadata
import inspect
import json
import multiprocessing
import os
from pathlib import Path
import queue
import signal
import subprocess
import sys
import time
import traceback
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor

HERE = Path(__file__).resolve().parent
E2 = HERE.parent
ROOT = E2.parents[2]
SETTINGS = dict(binding_decision=True, binding_assign=True, budget_s=120,
                max_states=400_000, max_transitions=2_000_000,
                verification_mode="auto", horizon_ms=None,
                reference_short_circuit=False,
                supplement_policy="only-after-REF-EQUIV-CHECKED; original-run_binding_v1-fold")


def canonical(value):
    # Preserve mapping order: inventory/binding iteration order can be semantic.
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    with (gzip.open(path, "rt") if str(path).endswith(".gz") else open(path)) as source:
        return json.load(source)


def load_inputs(args):
    pairs, histories, supplement = [], {}, {}
    for path in args.pairs:
        pairs.extend(read_json(path)["pairs"])
    if len({p["pair_id"] for p in pairs}) != len(pairs):
        raise ValueError("duplicate pair IDs across input files")
    for paths, target in ((args.histories, histories), (args.supplement, supplement)):
        for path in paths:
            for base, entries in read_json(path)["histories"].items():
                entries = entries if isinstance(entries, list) else entries["histories"]
                if base in target and target[base] != entries:
                    raise ValueError(f"conflicting histories for {base}; combine explicitly before freezing")
                target[base] = entries
    for pair in pairs:
        base = pair["base_case"]
        if not histories.get(base):
            raise ValueError(f"missing/nonempty original histories for {base}")
        if not (ROOT / pair["catalog"]).is_file():
            raise ValueError(f"missing catalog: {pair['catalog']}")
        for group in (histories[base], supplement.get(base, [])):
            names = [h["name"] for h in group]
            if len(names) != len(set(names)):
                raise ValueError(f"duplicate history names: {base}")
            for h in group:
                if "events" not in h or "horizon" not in h:
                    raise ValueError(f"malformed history: {base}/{h['name']}")
    return pairs, histories, supplement


def runtime_files():
    files = {Path(__file__).resolve(), E2 / "run_e2.py", E2 / "run_binding_v1.py"}
    # Include native parsing/lowering dependencies, not only the Explorer entrypoint.
    for folder in (ROOT / "explorer", ROOT / "timeline_ir", ROOT / "grammar", ROOT / "lowering",
                   E2 / "reference", E2.parent / "E1_adequacy"):
        files.update(folder.rglob("*.py"))
    files.update((ROOT / "files").glob("*service*.json"))
    files.update((E2.parent / "E1_adequacy").rglob("fixture_catalog*.json"))
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(files) if p.is_file()}


def runtime_manifest():
    versions = {}
    for name in ("antlr4-python3-runtime", "z3-solver"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return dict(schema=1, settings=SETTINGS, files=runtime_files(),
                python=sys.version, dependencies=versions)


def init_runtime():
    os.environ["E2_BINDING_DECISION"] = "1"
    os.environ["E2_BINDING_ASSIGN"] = "1"
    os.environ["E2_REF_DIR"] = str(E2 / "reference")
    sys.path[:0] = [str(E2), str(ROOT), str(E2 / "reference")]
    import run_e2
    from explorer.verification.timed import _timed_product
    defaults = inspect.signature(_timed_product).parameters
    assert run_e2.BINDING_DECISION and run_e2.BINDING_ASSIGN
    assert run_e2.BUDGET_S == 120
    assert defaults["max_states"].default == 400_000
    assert defaults["max_transitions"].default == 2_000_000
    return run_e2


def install_ir_cache():
    """Cache complete public run_ir calls; no approximation or history sampling."""
    import run
    original = run.run_ir

    @functools.lru_cache(maxsize=8192)
    def cached(serialized):
        args, kwargs = json.loads(serialized)
        return original(*args, **kwargs)

    def wrapper(*args, **kwargs):
        # Defensive copying prevents accidental contamination by any consumer.
        return copy.deepcopy(cached(canonical([args, kwargs])))

    run.run_ir = wrapper
    return cached, original


def error_row(pair, error):
    return {k: pair.get(k) for k in ("pair_id", "kind", "family", "base_case", "automation")} | {
        "agreement": "HARNESS-ERROR", "reason": f"{type(error).__name__}: {error}",
        "trace": traceback.format_exc(limit=6)[-1500:]}


def install_reference_short_circuit(original, audit):
    """Stop an assignment after its first concrete counterexample; retain B5 search."""
    uncapped = original._reference_once

    def once(pair, histories, assignment=None, stop_at_diverge=False):
        result = uncapped(pair, histories, assignment, stop_at_diverge=True)
        examined = sum(result.get("counts", {}).values())
        replayed = 0
        first = result.get("first_divergence")
        if first and "difference" not in first:
            # The inherited short-circuit path keeps only the history identifier.
            # Re-run that exact history to retain the ordinary diagnostic evidence.
            witness = next(h for h in histories if h["name"] == first["history"])
            diagnostic = uncapped(pair, [witness], assignment, stop_at_diverge=False)
            if diagnostic["outcome"] != "REF-DIVERGE":
                raise RuntimeError("non-deterministic reference counterexample replay")
            result["first_divergence"] = diagnostic["first_divergence"]
            replayed = 1
        result["n_histories_available"] = len(histories)
        result["n_histories_examined"] = examined
        result["n_diagnostic_replays"] = replayed
        result["short_circuit_after_counterexample"] = examined < len(histories)
        audit.append(dict(assignment=None if assignment is None else list(assignment),
                          outcome=result["outcome"], n_histories_available=len(histories),
                          n_histories_examined=examined, n_diagnostic_replays=replayed))
        return result

    original._reference_once = once
    return uncapped


def work_group(pairs, histories, supplement, sink, stage, freeze_sha, short_circuit=False):
    original = init_runtime()
    cache, uncached_ir = install_ir_cache()
    audit = []
    original_once = install_reference_short_circuit(original, audit) if short_circuit else None
    try:
        for pair in pairs:
            started = time.monotonic()
            before = cache.cache_info()
            audit.clear()
            try:
                row = original.run_pair(pair, histories)
                if short_circuit:
                    row["reference_assignment_checks"] = list(audit)
                if row.get("reference", {}).get("outcome") == "REF-EQUIV-CHECKED" and supplement:
                    supp_started = time.monotonic()
                    audit.clear()
                    try:
                        extra = original.reference_side(pair, supplement)
                    except Exception as error:
                        extra = {"outcome": "REF-HARNESS-ERROR", "reason": f"{type(error).__name__}: {error}"}
                    extra["seconds"] = round(time.monotonic() - supp_started, 3)
                    if short_circuit:
                        extra["assignment_checks"] = list(audit)
                    row["reference_supplement"] = extra
                    row["reference_frozen_histories"] = row["reference"]
                    if extra["outcome"] == "REF-DIVERGE":
                        row["reference"] = dict(row["reference"], outcome="REF-DIVERGE",
                            first_divergence=extra["first_divergence"], divergence_source="supplement")
                    row["agreement"] = original.agreement(row["explorer"], row["reference"])
                elif supplement:
                    row["supplement_not_run_reason"] = "original protocol: original-history reference not REF-EQUIV-CHECKED"
            except Exception as error:
                row = error_row(pair, error)
            finally:
                signal.alarm(0)
            after = cache.cache_info()
            row["extension_execution"] = dict(stage=stage, runtime_freeze_sha256=freeze_sha,
                original_histories=len(histories), supplementary_histories_available=len(supplement),
                reference_short_circuit=short_circuit,
                ir_cache_hits=after.hits-before.hits, ir_cache_misses=after.misses-before.misses,
                total_wall_seconds=round(time.monotonic()-started, 3))
            sink.put(row)
    finally:
        # A process can service multiple groups: do not stack cache wrappers.
        import run
        run.run_ir = uncached_ir
        if original_once is not None:
            original._reference_once = original_once
    return [p["pair_id"] for p in pairs]


def resume_rows(out):
    if not out.exists():
        return {}
    raw = out.read_bytes()
    rows = {}
    for line in raw.splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row["pair_id"] in rows:
            raise ValueError(f"duplicate completed row: {row['pair_id']}")
        rows[row["pair_id"]] = row
    if raw and not raw.endswith(b"\n"):
        # An intact final JSON value needs only its record separator repaired.
        with out.open("ab") as sink:
            sink.write(b"\n")
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pairs", action="append", default=[], required=True)
    ap.add_argument("--histories", action="append", default=[], required=True)
    ap.add_argument("--supplement", action="append", default=[])
    ap.add_argument("--out", type=Path)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--freeze-manifest", type=Path)
    ap.add_argument("--freeze-only", action="store_true")
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--reference-short-circuit", action="store_true",
                    help="stop each reference assignment after a concrete counterexample; log actual coverage")
    ap.add_argument("--only", default="", help="pair-ID prefix; selection is locked in output metadata")
    args = ap.parse_args()
    SETTINGS["reference_short_circuit"] = args.reference_short_circuit
    if args.workers < 1:
        ap.error("--workers must be positive")
    pairs, histories, supplement = load_inputs(args)
    current = runtime_manifest()
    if args.freeze_only:
        if not args.freeze_manifest:
            ap.error("--freeze-only requires --freeze-manifest")
        args.freeze_manifest.parent.mkdir(parents=True, exist_ok=True)
        with args.freeze_manifest.open("x") as sink:
            json.dump(current, sink, indent=2)
        print(f"Frozen {len(current['files'])} sources/assets; no experiment executed.", flush=True)
        return
    if args.freeze_manifest:
        frozen = read_json(args.freeze_manifest)
        if frozen != current:
            changed = sorted(k for k in set(frozen.get("files", {})) | set(current["files"])
                             if frozen.get("files", {}).get(k) != current["files"].get(k))
            raise ValueError(f"runtime differs from freeze: {changed[:20]} (also check settings/environment)")
        freeze_sha = sha(args.freeze_manifest)
    elif args.preflight:
        freeze_sha = "PREFLIGHT-UNFROZEN"
    else:
        ap.error("experiment requires existing --freeze-manifest; use --freeze-only before execution")
    if not args.out:
        ap.error("--out is required for execution")
    if args.out.resolve().is_relative_to((E2 / "runs").resolve()):
        ap.error("extension executor cannot write inside historical E2/runs")
    stage = "preflight" if args.preflight else "extension-experiment"
    selected = [p for p in pairs if p["pair_id"].startswith(args.only)]
    if not selected:
        ap.error("empty pair selection")
    inputs = {str(Path(p).resolve()): sha(p) for p in args.pairs + args.histories + args.supplement}
    catalogs = {str((ROOT / p["catalog"]).resolve()): sha(ROOT / p["catalog"]) for p in selected}
    lock = dict(stage=stage, runtime_freeze_sha256=freeze_sha, inputs_sha256=inputs,
                catalogs_sha256=catalogs, pair_ids=[p["pair_id"] for p in selected], settings=SETTINGS)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    meta_path = args.out.with_suffix(".meta.json")
    if meta_path.exists():
        if read_json(meta_path)["lock"] != lock:
            raise ValueError("resume metadata differs: inputs, freeze, stage and selection must be immutable")
    elif args.out.exists() and args.out.stat().st_size:
        raise ValueError("refusing existing results without metadata")
    else:
        git_head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                                  capture_output=True, text=True, check=True).stdout.strip()
        with meta_path.open("x") as sink:
            json.dump(dict(lock=lock, repo_head=git_head, workers=args.workers,
                started_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                runtime=current), sink, indent=2)
    done = resume_rows(args.out)
    if set(done) - set(lock["pair_ids"]):
        raise ValueError("results include pairs outside frozen output selection")
    groups = defaultdict(list)
    for pair in selected:
        if pair["pair_id"] not in done:
            groups[pair["base_case"]].append(pair)
    print(f"{sum(map(len, groups.values()))} remaining pairs; {len(groups)} base groups; {args.workers} workers; {stage}", flush=True)
    if not groups:
        return
    init_runtime()
    # Manager queue streams each finished pair immediately; resume never waits for a whole group.
    with multiprocessing.Manager() as manager, args.out.open("a") as sink:
        output = manager.Queue()
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            pending = {pool.submit(work_group, ps, histories[base], supplement.get(base, []),
                                   output, stage, freeze_sha, args.reference_short_circuit): ps for base, ps in groups.items()}

            def append(row):
                if row["pair_id"] in done:
                    raise ValueError(f"worker emitted duplicate: {row['pair_id']}")
                sink.write(json.dumps(row, ensure_ascii=False) + "\n")
                sink.flush()
                os.fsync(sink.fileno())
                done[row["pair_id"]] = row
                print(len(done), row["pair_id"], row.get("agreement"),
                      row.get("explorer", {}).get("verdict"), row.get("reference", {}).get("outcome"),
                      row.get("extension_execution", {}).get("total_wall_seconds"), flush=True)

            while pending:
                try:
                    append(output.get(timeout=0.2))
                except queue.Empty:
                    pass
                for future in list(pending):
                    if not future.done():
                        continue
                    # Worker completion follows synchronous Manager.put: drain all completed records first.
                    while True:
                        try:
                            append(output.get_nowait())
                        except queue.Empty:
                            break
                    ps = pending.pop(future)
                    try:
                        future.result()
                    except Exception as error:
                        for pair in ps:
                            if pair["pair_id"] not in done:
                                append(error_row(pair, error))
    if runtime_manifest() != current:
        raise RuntimeError("runtime changed during execution; results are preserved but freeze audit failed")
    summary = dict(n_rows=len(done), agreement=dict(Counter(r.get("agreement") for r in done.values())),
                   explorer=dict(Counter(r.get("explorer", {}).get("verdict", "MISSING") for r in done.values())),
                   reference=dict(Counter(r.get("reference", {}).get("outcome", "MISSING") for r in done.values())),
                   output_sha256=sha(args.out), runtime_freeze_sha256=freeze_sha, stage=stage)
    args.out.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
