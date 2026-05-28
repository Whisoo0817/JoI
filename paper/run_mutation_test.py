#!/usr/bin/env python3
"""A1 — Mutation testing of the IR-as-spec verifier (paper soundness evidence).

Natural-error recall (=1.0 on our dataset) shows the verifier flags the bugs the
LLM actually makes; it does NOT bound what the verifier would *miss*. Mutation
testing closes that gap: take JoI the verifier judges CORRECT against the GT IR,
inject a controlled, known bug, and ask whether the verifier now flags it. The
catch-rate is direct evidence for the "pass ⇒ correct" (soundness) direction.

Pipeline
--------
1. SEED HARVEST. For every Stage-B dump (joi_block) whose script the verifier
   passes clean against ir_gt (L1 empty AND L2 equivalent), keep it as a correct
   seed. A flagged block is not a valid seed (we can only mutate *correct* code).
2. MUTATE. Apply each operator to the seed script at its first applicable site,
   producing one mutant joi_block per (seed, operator).
3. EQUIVALENT-MUTANT FILTER (mutation-testing hygiene). Run the JoI simulator on
   seed and mutant under the GT-IR scenario; if their grouped traces are
   identical the mutation did not change observable behavior — it is an
   *equivalent mutant* and is excluded from the denominator (a verifier that
   stays silent on it is correct, not unsound).
4. DETECT. Run the verifier exactly as the retry harness does: l1_analyze, and
   if clean, l2_check(ir_gt, mutant). caught = (L1 nonempty) OR (not equivalent).
5. REPORT. Per-operator and overall catch-rate, the catching layer (L1/L2) and
   violation-kind distribution, and a list of the surviving (missed) mutants —
   those are the concrete soundness holes to discuss.

Usage:
    python3 paper/run_mutation_test.py
    MUT_SEED_DIR=/tmp/joi_c20aug/on ...        # seed source (default stageB full)
    BATCH_CATEGORIES=C03,C20 ...               # restrict seed categories
    MUT_LIMIT=40 ...                           # cap seeds (smoke)
    MUT_OUT=/tmp/joi_mutation ...              # dump dir for _mutation.json
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "paper"))

from paper.simulators.catalog import load_catalog
from paper.simulators.comparator import _group_and_dedup
from paper.simulators.event_synth import synthesize_scenarios
from paper.simulators.joi_simulator import run_joi_simulation
from paper.verifier.l1_static import analyze as l1_analyze
from paper.verifier.l2_runtime import check as l2_check

CSV_PATH = os.path.join(ROOT, "dataset.csv")
SEED_DIR = os.environ.get("MUT_SEED_DIR", "/tmp/joi_stageB_full_llm_v2/on")
OUT_DIR = os.environ.get("MUT_OUT", "/tmp/joi_mutation")
CAT_FILTER = {c.strip() for c in os.environ.get("BATCH_CATEGORIES", "").split(",") if c.strip()}
LIMIT = int(os.environ.get("MUT_LIMIT", "0"))
SITE_CAP = int(os.environ.get("MUT_SITE_CAP", "12"))  # max mutants per (seed, operator)


# ── Dataset join ─────────────────────────────────────────────────────────────
def load_meta():
    """name (cat_idx) -> {ir_gt(dict), connected_devices(dict)}."""
    meta = {}
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            cat = (r.get("category_v2") or "").strip()
            idx = (r.get("index") or "").strip()
            if not cat or not idx:
                continue
            name = f"{cat}_{idx}"
            try:
                ir_gt = json.loads(r.get("ir_gt", "") or "null")
            except Exception:
                ir_gt = None
            devs = r.get("connected_devices", "") or ""
            try:
                devs = json.loads(devs) if isinstance(devs, str) and devs.strip() else devs
            except Exception:
                pass
            meta[name] = {"ir_gt": ir_gt, "devs": devs, "cat": cat}
    return meta


# ── Mutation operators ───────────────────────────────────────────────────────
# A method invocation on a device selector, captured whole: `(#Tag ...).svc_meth(args)`
# (also `all(...)` / `any(...)` quantified forms). No nested parens occur in these
# scripts so `[^)]*` for the arg list is safe.
_CALL = re.compile(r'(?:all|any)?\(#[^)]*\)\.[A-Za-z_][A-Za-z0-9_]*\([^)]*\)')
_NUM = re.compile(r'-?\d+(?:\.\d+)?')
_STR = re.compile(r'"([^"]*)"')


def _is_actuation_line(line: str) -> bool:
    """A standalone emit statement: a bare call, not a `Var = read` and not a `{`/`}`."""
    s = line.strip()
    if not s or s in ("{", "}") or s.startswith("if") or s.startswith("}"):
        return False
    if "=" in s.split(".", 1)[0]:  # `Var = ...` assignment (a read), not an emit
        return False
    return bool(re.match(r'^(?:all|any)?\(#[^)]*\)\.[A-Za-z_][A-Za-z0-9_]*\(.*\)\s*$', s))


def _perturb_num(tok: str) -> str:
    if "." in tok:
        v = float(tok)
        return f"{v + 17.0:.1f}" if v + 17.0 != v else f"{v + 1.0:.1f}"
    v = int(tok)
    return str(v + 37 if v + 37 != v else v + 1)


# Every operator returns a LIST of (mutated_script, desc), one per applicable SITE
# (all-site mutation — addresses the first-site-bias critique). The harness caps
# the list per (seed, operator) to MUT_SITE_CAP to bound runtime.

# ── Output-affecting operators (the original 5; now all-site) ────────────────
def op_arg_numeric(script: str):
    """Change a numeric ARGUMENT inside each method call (-> arg_mismatch)."""
    out = []
    for m in _CALL.finditer(script):
        call = m.group(0)
        base = call.index("(", call.index(").")) + 1  # start of the arg list
        for nm in _NUM.finditer(call[base:]):
            old = nm.group(0)
            new = _perturb_num(old)
            off = base + nm.start()
            new_call = call[:off] + new + call[off + len(old):]
            out.append((script[:m.start()] + new_call + script[m.end():],
                        f"arg {old}->{new} in {call.strip()}"))
    return out


def op_enum_flip(script: str):
    """Change each quoted string argument of a `set*` call (-> arg_mismatch)."""
    out = []
    for m in _CALL.finditer(script):
        call = m.group(0)
        meth = call.split(").", 1)[1].split("(", 1)[0]
        if not re.search(r'set', meth, re.I):
            continue
        for sm in _STR.finditer(call, call.index(").")):
            old = sm.group(1)
            new = (old + "_x") if old else "mut"
            new_call = call[:sm.start(1)] + new + call[sm.end(1):]
            out.append((script[:m.start()] + new_call + script[m.end():],
                        f'enum "{old}"->"{new}"'))
    return out


def op_call_drop(script: str):
    """Delete EACH standalone actuation statement (-> missing_call/trace_empty)."""
    lines = script.replace("\\n", "\n").split("\n")
    out = []
    for i, ln in enumerate(lines):
        if _is_actuation_line(ln):
            out.append(("\n".join(lines[:i] + lines[i + 1:]), f"dropped `{ln.strip()}`"))
    return out


def op_call_add(script: str):
    """Inject a DISTINCT extra actuation after each actuation: clone it and perturb
    its value so it is a genuinely different emit (-> extra_call/arg_mismatch)."""
    lines = script.replace("\\n", "\n").split("\n")
    out = []
    for i, ln in enumerate(lines):
        if not _is_actuation_line(ln):
            continue
        muts = op_arg_numeric(ln) or op_enum_flip(ln)
        if not muts:
            continue
        new_line = muts[0][0]
        indent = ln[: len(ln) - len(ln.lstrip())]
        nl = lines[:i + 1] + [indent + new_line.strip()] + lines[i + 1:]
        out.append(("\n".join(nl), f"added `{new_line.strip()}`"))
    return out


def op_tick_scale(script: str):
    """Scale each polling-counter threshold or delay by 10x (-> timing_drift)."""
    out = []
    for m in re.finditer(r'\b(hold_ticks|ticks|count|counter|n)\s*(>=|>|<=|<)\s*(\d+)', script):
        old = m.group(3); new = str(int(old) * 10)
        out.append((script[:m.start(3)] + new + script[m.end(3):],
                    f"{m.group(1)}{m.group(2)} {old}->{new}"))
    for m in re.finditer(r'\bdelay\(\s*(\d+)', script):
        old = m.group(1); new = str(int(old) * 10)
        out.append((script[:m.start(1)] + new + script[m.end(1):], f"delay {old}->{new}"))
    return out


# ── Control-flow operators (the codex-demanded harder class; all-site) ───────
# These flip MEANING/logic rather than outputs, so they stress the verifier where
# trace-equivalence is least obviously sufficient — and they are exactly what the
# multi-scenario (else-branch / boundary) coverage suite is built to catch.
_CMP_FLIP = {">=": ">", ">": ">=", "<=": "<", "<": "<="}


def op_guard_polarity(script: str):
    """Invert a guard's boolean sense: `== true`<->`== false` (incl. `==|`), and
    `== <str/num>` -> `!= <str/num>`. A correct lowering then fires on the wrong
    side of the condition (-> divergence visible only with both-branch coverage)."""
    out = []
    for m in re.finditer(r'(==\|?|!=\|?)(\s*)(true|false)\b', script):
        flip = "false" if m.group(3) == "true" else "true"
        repl = m.group(1) + m.group(2) + flip
        out.append((script[:m.start()] + repl + script[m.end():],
                    f"polarity {m.group(3)}->{flip}"))
    for m in re.finditer(r'==(\s*)(?=("|-?\d))', script):  # == before a string/number
        repl = "!=" + m.group(1)
        out.append((script[:m.start()] + repl + script[m.end():], "== -> != (sense flip)"))
    return out


def op_comparator(script: str):
    """Off-by-one boundary mutation: `>=`<->`>`, `<=`<->`<` (each comparison site)."""
    out = []
    for m in re.finditer(r'(>=|<=|>|<)', script):
        op_ = m.group(1)
        new = _CMP_FLIP[op_]
        out.append((script[:m.start()] + new + script[m.end():], f"{op_} -> {new}"))
    return out


def op_quantifier(script: str):
    """Swap selector quantifier `all(`<->`any(` (wrong fan-out semantics)."""
    out = []
    for m in re.finditer(r'\b(all|any)\(', script):
        q = m.group(1); new = "any" if q == "all" else "all"
        out.append((script[:m.start(1)] + new + script[m.end(1):], f"{q}(->{new}("))
    return out


def op_tag_swap(script: str):
    """Replace a selector tag with a DIFFERENT tag present elsewhere in the script
    (plausible wrong-device bug). Deterministic alternative per site."""
    tags = sorted(set(re.findall(r'#([A-Za-z][A-Za-z0-9_]*)', script)))
    if len(tags) < 2:
        return []
    out = []
    for m in re.finditer(r'#([A-Za-z][A-Za-z0-9_]*)', script):
        tag = m.group(1)
        alt = next((t for t in tags if t != tag), None)
        if alt is None:
            continue
        out.append((script[:m.start()] + "#" + alt + script[m.end():], f"#{tag}->#{alt}"))
    return out


def op_assign_init(script: str):
    """Demote a persistent-init `:=` to a per-tick `=` (state-carry bug)."""
    out = []
    for m in re.finditer(r':=', script):
        out.append((script[:m.start()] + "=" + script[m.end():], ":= -> ="))
    return out


# ── Expression / arithmetic operators (codex Round 6 — arithmetic fault class) ──
# IR has high-level expression operators (abs/min/max, `+ - * /`); JoI has none,
# so lowering UNROLLS them into explicit if-else + register arithmetic (e.g.
# `min(x+10,100)` -> `tmp=x+10; if(tmp>100){tmp=100}`). Two real bug shapes seen
# in the dataset: (1) the clamp guard's comparison DIRECTION is inverted
# (min-clamp written as max-clamp; e.g. C14: `max(x-10,0)` lowered with
# `if(0<tmp){tmp=0}`), and (2) the arithmetic sign is wrong (`x+10` -> `x-10`).
# These mutate the UNROLLED form, so the relevant operators are direction-flip and
# arithmetic-op-flip — NOT a textual `min`<->`max` swap (which never appears in JoI).
_CMP_DIRECTION = {">": "<", "<": ">", ">=": "<=", "<=": ">="}
_ARITH_FLIP = {"+": "-", "-": "+", "*": "/", "/": "*"}


def op_cmp_direction(script: str):
    """Reverse a comparison's DIRECTION (`<`<->`>`, `<=`<->`>=`) at each site. This
    turns a correct min-clamp guard into a max-clamp (and vice versa) — the
    inverted-clamp arithmetic bug. Distinct from op_comparator (off-by-one
    `>=`<->`>`) and op_guard_polarity (`==`<->`!=`)."""
    out = []
    for m in re.finditer(r'(>=|<=|>|<)', script):
        op_ = m.group(1); new = _CMP_DIRECTION[op_]
        out.append((script[:m.start()] + new + script[m.end():], f"direction {op_} -> {new}"))
    return out


def op_arith_op(script: str):
    """Flip a binary arithmetic operator (`+`<->`-`, `*`<->`/`) at each NUMERIC site.
    Catches wrong-sign register arithmetic in unrolled abs/min/max/clamp
    (e.g. `x+10`->`x-10`). Operands must be numeric/identifier (NOT string literals,
    to avoid `"a"+"b"` -> `"a"-"b"` type errors); lookbehind/ahead require operand
    chars on both sides to skip unary minus."""
    out = []
    for m in re.finditer(r'(?<=[\w\)\]])(\s*)([+\-*/])(\s*)(?=[\w\(\$#])', script):
        # Skip if either adjacent operand is a string literal (quote within one char
        # of the operator's whitespace-trimmed neighbours) — arithmetic on strings is
        # a type error, not a meaningful mutation.
        lo = script.rfind('"', 0, m.start(2));
        op_ = m.group(2); new = _ARITH_FLIP[op_]
        s, e = m.start(2), m.end(2)
        # cheap string-context guard: a quote immediately bounding the operand token
        left_ctx = script[max(0, s - 2):s]
        right_ctx = script[e:e + 2]
        if '"' in left_ctx or '"' in right_ctx:
            continue
        out.append((script[:s] + new + script[e:], f"arith {op_} -> {new}"))
    return out


OPERATORS = {
    # output-affecting (original)
    "arg_numeric": op_arg_numeric,
    "enum_flip": op_enum_flip,
    "call_drop": op_call_drop,
    "call_add": op_call_add,
    "tick_scale": op_tick_scale,
    # control-flow / logic (new — codex hardening; all within L2's observation model)
    "guard_polarity": op_guard_polarity,
    "comparator": op_comparator,
    "assign_init": op_assign_init,
    # expression / arithmetic (codex Round 6 — closes the arithmetic fault class)
    "cmp_direction": op_cmp_direction,
    "arith_op": op_arith_op,
}

# DELIBERATELY EXCLUDED from the L2 mutation suite: `op_quantifier` (all<->any) and
# `op_tag_swap` (#Loc -> #OtherLoc). L2's trace observation model is
# (method, args, timestamp) — device-INSTANCE identity and selector FAN-OUT are
# abstracted away (the trace key excludes even the service). WHICH physical devices
# a selector resolves to is verified by the precision / mapping_device_match stage,
# NOT by IR<->JoI trace-equivalence (IR targets are `Service.Method`, not instances).
# So these two mutations are out of L2's scope by design: on our data every such
# mutant is observationally equivalent (e.g. C03: 85/85 tag_swap, 8/8 quantifier all
# equivalent). Reported here as a scoping/threat note rather than as a catch-rate.
_OUT_OF_SCOPE_OPERATORS = {"quantifier": op_quantifier, "tag_swap": op_tag_swap}


# ── Trace equivalence (equivalent-mutant filter) ─────────────────────────────
def _trace_signature(joi_block, ir_gt, cat):
    """Observable execution signature of the JoI sim under the GT-IR scenario:
    per group the representative timestamp AND the (method,args) set. TIMING IS
    PART OF THE SIGNATURE — a mutation that only shifts when a call fires (e.g.
    tick_scale) is a genuine behavioral change, not an equivalent mutant. None if
    the script can't be simulated (broken) or there is no scenario."""
    try:
        scns = synthesize_scenarios(ir_gt)
        if not scns:
            return None
        t = run_joi_simulation(joi_block, scns[0], cat)
        g = _group_and_dedup(t.records)
        return [(min(r.timestamp_ms for r in grp["records"]),
                 sorted((r.method, r.args) for r in grp["records"])) for grp in g]
    except Exception:
        return None


def _verify(joi_block, ir_gt, devs, cat):
    """Return (caught: bool, layer: str, kinds: list[str]) — retry-harness logic."""
    l1 = l1_analyze(joi_block, connected_devices=devs if isinstance(devs, dict) else None, catalog=cat)
    if l1:
        return True, "L1", [v.kind for v in l1]
    rep = l2_check(ir_gt, joi_block, catalog=cat)
    if not rep.equivalent:
        return True, "L2", [v.kind for v in rep.violations]
    return False, "", []


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    cat = load_catalog()
    meta = load_meta()

    files = sorted(f for f in os.listdir(SEED_DIR) if f.endswith(".json") and not f.startswith("_"))
    if CAT_FILTER:
        files = [f for f in files if f[:-5].rsplit("_", 1)[0] in CAT_FILTER]
    if LIMIT:
        files = files[:LIMIT]
    print(f"[mutation] seed_dir={SEED_DIR}  candidate dumps={len(files)}  out={OUT_DIR}")

    valid_seeds = 0
    skipped_flagged = 0
    skipped_nogt = 0
    # per-operator tally
    gen = Counter()        # mutants generated (operator applicable)
    equiv = Counter()      # equivalent mutants (excluded)
    genuine = Counter()    # non-equivalent (real bug) mutants
    caught = Counter()     # genuine mutants flagged
    layer = defaultdict(Counter)   # op -> {L1,L2}
    kinds = defaultdict(Counter)   # op -> kind counts
    survivors = []         # missed genuine mutants

    for fn in files:
        name = fn[:-5]
        m = meta.get(name)
        if not m or not isinstance(m["ir_gt"], dict):
            skipped_nogt += 1
            continue
        ir_gt, devs = m["ir_gt"], m["devs"]
        try:
            d = json.load(open(os.path.join(SEED_DIR, fn), encoding="utf-8"))
        except Exception:
            continue
        jb = d.get("joi_block")
        if not isinstance(jb, dict) or not (jb.get("script") or "").strip():
            continue

        # Seed must be CORRECT (verifier passes it clean vs ir_gt). A seed whose
        # own simulation throws is not a usable (correct) seed — skip it.
        try:
            seed_caught, _, _ = _verify(jb, ir_gt, devs, cat)
        except Exception:
            skipped_flagged += 1
            continue
        if seed_caught:
            skipped_flagged += 1
            continue
        valid_seeds += 1
        try:
            seed_sig = _trace_signature(jb, ir_gt, cat)
        except Exception:
            seed_sig = None

        for op_name, op in OPERATORS.items():
            seen_scripts = set()
            for new_script, desc in op(jb.get("script", ""))[:SITE_CAP]:
                if new_script == jb.get("script") or new_script in seen_scripts:
                    continue
                seen_scripts.add(new_script)
                gen[op_name] += 1
                mut = dict(jb)
                mut["script"] = new_script

                try:
                    mut_sig = _trace_signature(mut, ir_gt, cat)
                except Exception:
                    mut_sig = None
                # Equivalent mutant: parseable, simulated, identical observable trace.
                if mut_sig is not None and seed_sig is not None and mut_sig == seed_sig:
                    equiv[op_name] += 1
                    continue
                genuine[op_name] += 1

                # A mutant whose simulation throws (e.g. a type-invalid expression) is
                # fail-closed: the deploy-time verifier would reject it, so count it
                # caught under an explicit "error" layer rather than crashing the batch.
                try:
                    hit, lyr, ks = _verify(mut, ir_gt, devs, cat)
                except Exception:
                    hit, lyr, ks = True, "error", ["sim_error"]
                if hit:
                    caught[op_name] += 1
                    layer[op_name][lyr] += 1
                    for k in ks:
                        kinds[op_name][k] += 1
                else:
                    survivors.append({"name": name, "op": op_name, "mutation": desc,
                                       "script": new_script})

    # ── Report ──
    print("\n" + "=" * 72)
    print(f"Seeds: {valid_seeds} valid (correct) | skipped {skipped_flagged} flagged, "
          f"{skipped_nogt} no-gt")
    print("=" * 72)
    print(f"{'operator':<12} {'gen':>4} {'equiv':>6} {'genuine':>8} {'caught':>7} {'catch%':>7}   layer / kinds")
    tot_gen = tot_genuine = tot_caught = 0
    for op_name in OPERATORS:
        g, e, gu, c = gen[op_name], equiv[op_name], genuine[op_name], caught[op_name]
        tot_gen += g; tot_genuine += gu; tot_caught += c
        pct_s = f"{100 * c / gu:>6.1f}%" if gu else "     —"  # n/a when no genuine mutant
        lyr = dict(layer[op_name])
        kd = dict(kinds[op_name].most_common(4))
        print(f"{op_name:<14} {g:>4} {e:>6} {gu:>8} {c:>7} {pct_s:>7}   {lyr} {kd}")
    pct = 100 * tot_caught / tot_genuine if tot_genuine else 0.0
    print("-" * 72)
    print(f"{'TOTAL':<12} {tot_gen:>4} {sum(equiv.values()):>6} {tot_genuine:>8} "
          f"{tot_caught:>7} {pct:>6.1f}%")

    if survivors:
        print(f"\nSURVIVORS (missed genuine mutants = soundness holes): {len(survivors)}")
        for s in survivors[:40]:
            print(f"  [{s['op']:<11}] {s['name']:<10} {s['mutation']}")
        if len(survivors) > 40:
            print(f"  ... +{len(survivors) - 40} more (see {OUT_DIR}/_mutation.json)")
    else:
        print("\nSURVIVORS: none — every genuine mutant was caught.")

    out = {
        "seed_dir": SEED_DIR,
        "valid_seeds": valid_seeds,
        "skipped_flagged": skipped_flagged,
        "per_operator": {op: {"gen": gen[op], "equiv": equiv[op], "genuine": genuine[op],
                              "caught": caught[op], "layer": dict(layer[op]),
                              "kinds": dict(kinds[op])} for op in OPERATORS},
        "total": {"gen": tot_gen, "equiv": sum(equiv.values()), "genuine": tot_genuine,
                  "caught": tot_caught, "catch_rate": pct},
        "survivors": survivors,
    }
    path = os.path.join(OUT_DIR, "_mutation.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n[mutation] -> {path}")


if __name__ == "__main__":
    main()
