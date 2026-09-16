#!/usr/bin/env python3
"""Fig2/Table1 — build behavior-preserving rewrites of the E3 EQUIV-FIXPOINT programs.

Seeds: the E3 final run's EQUIV-FIXPOINT candidates (confirmed IR + binding, Explorer-certified).
For each rewrite type, the rewritten program is written as a candidate file
  explorer/candidates/fig2-rw-<type>/<case>.json
so the frozen E3 evaluator (explorer/eval/frozen_contract.py) can check, with the same
snapshot as E3, that the rewrite is still EQUIV-FIXPOINT against the confirmed IR.
Only rewrites that pass that check become Fig2 pairs (see verify_rewrites.py).

Rewrite types (band / name / what changes / what must not change):
  spelling  var_rename        one variable's name everywhere                 nothing else
  spelling  comparator_flip   `x >= 26` -> `26 <= x` (first literal compare)  truth value
  spelling  time_unit         `delay(3 MIN)` -> `delay(180 SEC)`             duration
  spelling  exists_spelling   `all(#X).a ==| v` -> `any(#X).a == v`         quantifier meaning
  logic     branch_swap       if (C) {A} else {B} -> if (not (C)) {B} else {A}
  logic     else_split        if (C) {A} else {B} -> if (C) {A}; if (not (C)) {B}   (else removed;
                                      unsound when A writes a variable C reads -- checker drops those)
  temporal  delay_split       `delay(N U)` -> `delay(1 U)` + `delay(N-1 U)`  total wait
  temporal  loop_unroll       counted periodic cycle -> straight-line body/delay/body...
  temporal  phase_flag        `phase := 0` integer lifecycle -> boolean `started` flag + shared tail
  temporal  wait_precheck     `wait until(C)` -> `if (not (C)) { wait until(C) }`   (check, then block)
"""
import json
import os
import re
import sys
from collections import Counter, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, ROOT)

E3_RUN = os.path.join(ROOT, "explorer/eval/results/e3_single_binding_382_20260915_run/case_outcomes.jsonl")
E3_CANDS = os.path.join(ROOT, "explorer/candidates/qwen3_5-9b-fp8-e3-single-binding-v4")
OUT_PREFIX = "fig2-rw-"

UNIT_MS = {"MSEC": 1, "SEC": 1000, "MIN": 60000, "HOUR": 3600000}
OP_LIT = r'(?<![=!<>|])\s(<=|>=|<|>|==|!=)\s(-?\d+(?:\.\d+)?|"[^"]*"|true|false)\b'


def _match(s, i, o, c):
    d = 0
    for j in range(i, len(s)):
        if s[j] == o:
            d += 1
        elif s[j] == c:
            d -= 1
            if d == 0:
                return j
    return -1


def _first_if(s):
    m = re.search(r'\bif\s*\(', s)
    if not m:
        return None
    lp = m.end() - 1
    rp = _match(s, lp, "(", ")")
    lb = s.find("{", rp)
    rb = _match(s, lb, "{", "}")
    if rp < 0 or lb < 0 or rb < 0:
        return None
    cond, then_blk = s[lp + 1:rp], s[lb + 1:rb]
    me = re.match(r'\s*else\s*\{', s[rb + 1:])
    if not me:
        return cond, then_blk, None, (m.start(), rb + 1)
    elb = rb + 1 + me.end() - 1
    erb = _match(s, elb, "{", "}")
    if erb < 0:
        return None
    return cond, then_blk, s[elb + 1:erb], (m.start(), erb + 1)


# ---- spelling -------------------------------------------------------------------
def t_var_rename(s):
    m = re.search(r'^\s*([a-z_]\w*)\s*:?=\s', s, re.M)
    if not m:
        return None
    old = m.group(1)
    new = old + "_v"
    if re.search(r'\b' + re.escape(new) + r'\b', s):
        return None
    return re.sub(r'\b' + re.escape(old) + r'\b', new, s)


MIRROR = {"<": ">", ">": "<", "<=": ">=", ">=": "<=", "==": "==", "!=": "!="}


def t_comparator_flip(s):
    # first `LHS op LITERAL` where op is a plain (non-quantified) comparison; LHS = the
    # operand text back to the enclosing "(" or "and"/"or"/"not (" boundary
    m = re.search(OP_LIT, s)
    if not m:
        return None
    op, lit = m.group(1), m.group(2)
    # find LHS start: scan back over one balanced operand
    i = m.start()
    j = i
    depth = 0
    while j > 0:
        ch = s[j - 1]
        if ch == ")":
            depth += 1
        elif ch == "(":
            if depth == 0:
                break
            depth -= 1
        elif depth == 0 and (ch == "\n" or s[j - 5:j] in (" and ", " not ") or s[j - 4:j] == " or "):
            break
        j -= 1
    lhs = s[j:i].strip()
    if not lhs or lhs.endswith(("and", "or", "not", "if", "until")):
        return None
    return s[:j] + f"{lit} {MIRROR[op]} {lhs}" + s[m.end():]


def t_time_unit(s):
    def rep(m):
        n, u = int(m.group(1)), m.group(2)
        if u == "HOUR":
            return f"delay({n * 60} MIN)"
        if u == "MIN":
            return f"delay({n * 60} SEC)"
        return m.group(0)
    new = re.sub(r'delay\(\s*(\d+)\s*(MIN|HOUR)\s*\)', rep, s)
    return new if new != s else None


def t_exists_spelling(s):
    rx = r'(all)?\s*\((#[^)]*)\)\.(\w+)\s*(==|!=|<=|>=|<|>)\|\s*'
    if not re.search(rx, s):
        return None
    return re.sub(rx, lambda m: f"any({m.group(2)}).{m.group(3)} {m.group(4)} ", s)


# ---- logic ----------------------------------------------------------------------
def t_branch_swap(s):
    r = _first_if(s)
    if not r or r[2] is None:
        return None
    cond, a, b, (i, j) = r
    return s[:i] + f"if (not ({cond.strip()})) {{{b}}} else {{{a}}}" + s[j:]


def t_else_split(s):
    """Drop the else by guarding the second half with the negated condition.

    This is NOT unconditionally behavior-preserving: the then-branch now runs between the two
    tests, so if it assigns a variable the condition reads, the second test sees a different
    value. 11 of the 38 rewrites this produces are DIVERGE_CONFIRMED for exactly that reason and
    the frozen evaluator drops them; only the 27 it certifies become pairs. Generating a
    candidate that the checker may reject is the intended division of labour here -- the
    transform proposes, the checker decides.
    """
    r = _first_if(s)
    if not r or r[2] is None:
        return None
    cond, a, b, (i, j) = r
    c = cond.strip()
    indent = re.search(r'[ \t]*$', s[:i]).group(0)
    return s[:i] + f"if ({c}) {{{a}}}\n{indent}if (not ({c})) {{{b}}}" + s[j:]


# ---- temporal -------------------------------------------------------------------
def t_delay_split(s):
    m = re.search(r'delay\(\s*(\d+)\s*(MSEC|SEC|MIN|HOUR)\s*\)', s)
    if not m or int(m.group(1)) < 2:
        return None
    n, u = int(m.group(1)), m.group(2)
    indent = re.search(r'[ \t]*$', s[:m.start()]).group(0)
    return s[:m.start()] + f"delay(1 {u})\n{indent}delay({n - 1} {u})" + s[m.end():]


def _ms_to_delay(ms):
    for u in ("HOUR", "MIN", "SEC", "MSEC"):
        if ms % UNIT_MS[u] == 0:
            return f"delay({ms // UNIT_MS[u]} {u})"


def t_loop_unroll(s, block):
    if block.get("cron") or not block.get("period"):
        return None
    m = re.match(r'\s*n\s*:=\s*0\s*\n\s*if\s*\(\s*n\s*>=\s*(\d+)\s*\)\s*\{\s*break\s*\}\s*\n(.*)\n\s*n\s*=\s*n\s*\+\s*1\s*$', s, re.S)
    if not m:
        return None
    k, body = int(m.group(1)), m.group(2).strip()
    if k < 2 or k > 12 or re.search(r'\bn\b|:=|\bbreak\b|wait until', body):
        return None
    d = _ms_to_delay(int(block["period"]))
    return ("\n".join([body] + [f"{d}\n{body}"] * (k - 1)), {"period": 0})


def t_wait_precheck(s):
    """Check the condition before blocking on it. `wait until(C)` returns immediately when C
    already holds, so wrapping it in `if (not (C))` cannot change when the program proceeds --
    it changes only the shape of the wait."""
    m = re.search(r'^([ \t]*)wait until\((.*)\)[ \t]*$', s, re.M)
    if not m:
        return None
    indent, cond = m.group(1), m.group(2).strip()
    if not cond or "wait until" in cond:
        return None
    body = (f"{indent}if (not ({cond})) {{\n"
            f"{indent}    wait until({cond})\n"
            f"{indent}}}")
    return s[:m.start()] + body + s[m.end():]


def t_phase_flag(s):
    m = re.match(r'\s*phase\s*:=\s*0\s*\n\s*if\s*\(\s*phase\s*==\s*0\s*\)\s*\{\s*\n(\s*wait until\(.*?\)\s*)\n\s*phase\s*=\s*1\s*\n(.*?)\n\s*\}\s*\n\s*else\s*\{\s*\n(.*?)\n\s*\}\s*$', s, re.S)
    if not m:
        return None
    wait, y1, y2 = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
    if y1 != y2 or "phase" in y1:
        return None
    return f"started := false\nif (started == false) {{\n    {wait}\n    started = true\n}}\n{y1}"


TRANSFORMS = OrderedDict([
    ("var_rename", ("spelling", t_var_rename)),
    ("comparator_flip", ("spelling", t_comparator_flip)),
    ("time_unit", ("spelling", t_time_unit)),
    ("exists_spelling", ("spelling", t_exists_spelling)),
    ("branch_swap", ("logic", t_branch_swap)),
    ("else_split", ("logic", t_else_split)),
    ("delay_split", ("temporal", t_delay_split)),
    ("loop_unroll", ("temporal", t_loop_unroll)),
    ("phase_flag", ("temporal", t_phase_flag)),
    ("wait_precheck", ("temporal", t_wait_precheck)),
])


def apply(name, block):
    fn = TRANSFORMS[name][1]
    r = fn(block["script"], block) if name == "loop_unroll" else fn(block["script"])
    if r is None:
        return None
    new = dict(block)
    if isinstance(r, tuple):
        new["script"] = r[0]
        new.update(r[1])
    else:
        new["script"] = r
    return None if new == block else new


def seeds():
    outs = {}
    for line in open(E3_RUN):
        r = json.loads(line)
        outs[r["id"]] = r["status"]
    for cid in sorted(outs):
        if outs[cid] == "EQUIV-FIXPOINT":
            yield cid, json.load(open(os.path.join(E3_CANDS, cid + ".json")))


def main():
    from explorer.runtime.joi_parser import parse_script
    stats = Counter()
    groups = []
    parse_fail = []
    for cid, cand in seeds():
        base = cand["joi_block"]
        try:
            parse_script(base["script"])
        except Exception as e:  # a seed the parser rejects cannot be a Fig2 seed
            stats["seed_parse_fail"] += 1
            continue
        g = {"id": cid, "command": cand["command_eng"], "base": base, "variants": {}}
        for name in TRANSFORMS:
            v = apply(name, base)
            if v is None:
                continue
            try:
                parse_script(v["script"])
            except Exception as e:
                parse_fail.append((cid, name, str(e)[:120]))
                continue
            g["variants"][name] = v
            stats[name] += 1
            d = os.path.join(ROOT, "explorer/candidates", OUT_PREFIX + name)
            os.makedirs(d, exist_ok=True)
            out = dict(cand)
            out["joi_block"] = v
            out["code"] = json.dumps(v, ensure_ascii=False, indent=2)
            out["candidate_tag"] = OUT_PREFIX + name
            out["rewrite"] = {"type": name, "band": TRANSFORMS[name][0], "seed_tag": cand["candidate_tag"]}
            with open(os.path.join(d, cid + ".json"), "w") as f:
                json.dump(out, f, ensure_ascii=False, indent=1)
        if g["variants"]:
            groups.append(g)
    os.makedirs(os.path.join(HERE, "rewrites"), exist_ok=True)
    with open(os.path.join(HERE, "rewrites", "rewrites.json"), "w") as f:
        json.dump({"seed_run": os.path.relpath(E3_RUN, ROOT), "seed_candidates": os.path.relpath(E3_CANDS, ROOT),
                   "types": {k: v[0] for k, v in TRANSFORMS.items()}, "groups": groups}, f, ensure_ascii=False, indent=1)
    print("seeds with >=1 rewrite:", len(groups))
    for k in TRANSFORMS:
        print(f"  {k:16s} {stats[k]}")
    print("seed parse failures:", stats["seed_parse_fail"], " rewrite parse failures:", len(parse_fail))
    for x in parse_fail[:10]:
        print("   ", x)


if __name__ == "__main__":
    main()
