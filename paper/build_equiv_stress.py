#!/usr/bin/env python3
"""Build a TRACE-EXACT equivalence-variant dataset for the instability experiment.

For each verifier-clean correct seed we generate behaviorally-identical rewrites
(different surface idiom, SAME action trace). We KEEP a variant only if its trace
signature is identical to the seed under our simulator -- i.e. our verifier treats
it as equivalent (consistency guarantee; avoids the switch_on-vs-brightness trap).

Rewrite types (tagged structural vs shallow):
  structural (judge must reason; flips expected):
    - prevcurr     : `triggered` flag idiom -> `prev/curr` edge detector
    - branch_swap  : if(C){A}else{B} -> if(not(C)){B}else{A}
    - demorgan     : if(A and B) -> if(not(not A or not B))
  shallow (control; a stable oracle should never flip):
    - var_rename   : alpha-rename a `:=`-declared local var everywhere (purest)
    - double_neg   : if(C) -> if(not(not(C)))   (trivial logical identity)
    - operand_swap : `A and B` -> `B and A`   (top-level of first if-cond)
    - arith_commute: `x + n` -> `n + x`
    - selector_reorder : (#A #B) -> (#B #A)

Output: groups [{seed, command, base_joi, variants:[{joi,type,depth}]}].
Instability = within a group (all trace-identical), does the judge's verdict differ?
"""
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "paper"))
from paper.run_mutation_test import load_meta, load_catalog, _verify, _trace_signature

STRUCTURAL = {"prevcurr", "branch_swap", "demorgan"}
SHALLOW = {"operand_swap", "arith_commute", "selector_reorder", "var_rename", "double_neg"}
MAX_VARIANTS_PER_TYPE = 1     # one variant per (seed,type) keeps groups clean
SEED_CAP = None               # use all clean seeds


# ── balanced scanners ───────────────────────────────────────────────────────
def _match(s, i, open_c, close_c):
    """s[i]==open_c -> return index of matching close_c."""
    depth = 0
    for j in range(i, len(s)):
        if s[j] == open_c:
            depth += 1
        elif s[j] == close_c:
            depth -= 1
            if depth == 0:
                return j
    return -1


def _first_if(s):
    """Return (cond, then_blk, else_blk_or_None, span) for the first `if (...) {...}`."""
    m = re.search(r'\bif\s*\(', s)
    if not m:
        return None
    lp = m.end() - 1
    rp = _match(s, lp, "(", ")")
    if rp < 0:
        return None
    cond = s[lp + 1:rp]
    lb = s.find("{", rp)
    if lb < 0:
        return None
    rb = _match(s, lb, "{", "}")
    if rb < 0:
        return None
    then_blk = s[lb + 1:rb]
    else_blk = None
    rest = s[rb + 1:]
    me = re.match(r'\s*else\s*\{', rest)
    end = rb + 1
    if me:
        elb = rb + 1 + (me.end() - 1)
        erb = _match(s, elb, "{", "}")
        if erb >= 0:
            else_blk = s[elb + 1:erb]
            end = erb + 1
    return cond, then_blk, else_blk, (m.start(), end)


# ── transforms (return new script or None) ─────────────────────────────────
def t_prevcurr(s):
    mc = re.search(r'if\s*\((.*?)\)\s*\{\s*\n\s*if\s*\(triggered\s*==\s*false\)\s*\{', s, re.DOTALL)
    mb = re.search(r'if\s*\(triggered\s*==\s*false\)\s*\{(.*?)triggered\s*=\s*true', s, re.DOTALL)
    if not (mc and mb):
        return None
    cond, body = mc.group(1).strip(), mb.group(1).strip()
    return (f'prev := false\ncurr = {cond}\nif (curr == true and prev == false) {{\n'
            f'{body}\n}}\nprev = curr')


def t_branch_swap(s):
    r = _first_if(s)
    if not r:
        return None
    cond, then_blk, else_blk, (a, b) = r
    if else_blk is None:
        return None
    new = f"if (not ({cond.strip()})) {{{else_blk}}} else {{{then_blk}}}"
    return s[:a] + new + s[b:]


def t_demorgan(s):
    r = _first_if(s)
    if not r:
        return None
    cond, then_blk, else_blk, (a, b) = r
    if " and " not in cond:
        return None
    # split on the FIRST top-level " and "
    parts = _split_top(cond, " and ")
    if len(parts) < 2:
        return None
    left, right = parts[0].strip(), " and ".join(parts[1:]).strip()
    newcond = f"not (not ({left}) or not ({right}))"
    tail = f" else {{{else_blk}}}" if else_blk is not None else ""
    new = f"if ({newcond}) {{{then_blk}}}{tail}"
    return s[:a] + new + s[b:]


def t_operand_swap(s):
    r = _first_if(s)
    if not r:
        return None
    cond, then_blk, else_blk, (a, b) = r
    parts = _split_top(cond, " and ")
    if len(parts) != 2:
        return None
    newcond = f"{parts[1].strip()} and {parts[0].strip()}"
    tail = f" else {{{else_blk}}}" if else_blk is not None else ""
    new = f"if ({newcond}) {{{then_blk}}}{tail}"
    return s[:a] + new + s[b:]


def t_arith_commute(s):
    # x + N -> N + x  (first occurrence of `<token> + <int>`)
    m = re.search(r'([\w.#()\s]+?)\s\+\s(\d+(?:\.\d+)?)', s)
    if not m:
        return None
    left, num = m.group(1).strip(), m.group(2)
    return s[:m.start()] + f"{num} + {left}" + s[m.end():]


def t_selector_reorder(s):
    # reorder tags in the first (#A #B ...) with >=2 tags
    m = re.search(r'\(#(\w+(?:\s+#\w+)+)\)', s)
    if not m:
        return None
    tags = [t.lstrip("#") for t in m.group(1).split()]
    if len(tags) < 2:
        return None
    reordered = [tags[-1]] + tags[:-1]   # rotate last tag to front
    newsel = "(#" + " #".join(reordered) + ")"
    return s[:m.start()] + newsel + s[m.end():]


def t_var_rename(s):
    # alpha-rename: rename the first `:=`-declared local variable everywhere.
    # Purest behavior-preserving rewrite -- a stable oracle must never flip on it.
    m = re.search(r'\b([a-z_][a-zA-Z0-9_]*)\s*:=', s)
    if not m:
        return None
    old = m.group(1)
    new = old + "_v"
    if re.search(r'\b' + re.escape(new) + r'\b', s):
        return None  # name collision -> skip
    return re.sub(r'\b' + re.escape(old) + r'\b', new, s)


def t_double_neg(s):
    # double negation of the first if-cond: C -> not (not (C)). Truth-preserving.
    r = _first_if(s)
    if not r:
        return None
    cond, then_blk, else_blk, (a, b) = r
    newcond = f"not (not ({cond.strip()}))"
    tail = f" else {{{else_blk}}}" if else_blk is not None else ""
    new = f"if ({newcond}) {{{then_blk}}}{tail}"
    return s[:a] + new + s[b:]


def _split_top(cond, sep):
    """Split cond on `sep` only at paren-depth 0."""
    out, depth, last = [], 0, 0
    i = 0
    while i < len(cond):
        c = cond[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif depth == 0 and cond[i:i + len(sep)] == sep:
            out.append(cond[last:i]); last = i + len(sep); i += len(sep); continue
        i += 1
    out.append(cond[last:])
    return out


TRANSFORMS = {
    "prevcurr": t_prevcurr, "branch_swap": t_branch_swap, "demorgan": t_demorgan,
    "operand_swap": t_operand_swap, "arith_commute": t_arith_commute,
    "selector_reorder": t_selector_reorder,
    "var_rename": t_var_rename, "double_neg": t_double_neg,
}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump-dir", default="experiments/e2e_382/20260528_150445__d886015/intermediate/off")
    ap.add_argument("--out", default="/tmp/equiv_stress.json")
    a = ap.parse_args()
    meta = load_meta(); cat = load_catalog()
    cmds = {f"{r['category_v2']}_{r['index']}": (r.get('command_eng') or '').strip()
            for r in csv.DictReader(open(os.path.join(ROOT, "dataset.csv"), encoding="utf-8"))}

    groups = []
    type_counts = Counter()
    for fn in sorted(os.listdir(a.dump_dir)):
        if not fn.endswith(".json") or fn.startswith("_"):
            continue
        name = fn[:-5]; m = meta.get(name); cmd = cmds.get(name)
        if not m or not isinstance(m.get("ir_gt"), dict) or not cmd:
            continue
        try:
            jb = json.load(open(os.path.join(a.dump_dir, fn), encoding="utf-8")).get("joi_block")
        except Exception:
            continue
        if not isinstance(jb, dict) or not (jb.get("script") or "").strip():
            continue
        ir, devs = m["ir_gt"], m["devs"]
        try:
            if _verify(jb, ir, devs, cat)[0]:
                continue
            seed_sig = _trace_signature(jb, ir, cat)
        except Exception:
            continue
        variants = []
        for tname, tf in TRANSFORMS.items():
            try:
                ns = tf(jb["script"])
            except Exception:
                ns = None
            if not ns or ns == jb["script"]:
                continue
            v = dict(jb); v["script"] = ns
            try:
                if _trace_signature(v, ir, cat) != seed_sig:
                    continue  # not trace-exact in our system -> drop (consistency)
            except Exception:
                continue
            variants.append({"joi": v, "type": tname,
                             "depth": "structural" if tname in STRUCTURAL else "shallow"})
            type_counts[tname] += 1
        if variants:
            groups.append({"seed": name, "command": cmd, "base_joi": jb,
                           "variants": variants})

    json.dump(groups, open(a.out, "w"), ensure_ascii=False, indent=1)
    nv = sum(len(g["variants"]) for g in groups)
    print(f"equivalence groups: {len(groups)} | total verified trace-exact variants: {nv}")
    print("by rewrite type:", dict(type_counts))
    bd = Counter()
    for g in groups:
        for v in g["variants"]:
            bd[v["depth"]] += 1
    print("by depth:", dict(bd))
    print(f"-> {a.out}")


if __name__ == "__main__":
    main()
