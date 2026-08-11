#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
E1 scorer: OMISSION / DISTORTION of Timeline IR vs gold ir_gt.

ARM-AGNOSTIC BY CONSTRUCTION
----------------------------
score() receives (pred_ir, gold_ir, cmd) and **never reads `cmd`**. It is accepted
only for interface compatibility. This matters: arm B's command carries inline
" | " clause markers, so any scorer that looked at `cmd` could leak arm identity
into the metric. Nothing here branches on arm, prompt, output length, or turn count.

METRIC MODEL
------------
flatten() turns {"timeline":[...]} into a flat, depth-first, document-order list of
steps (descending into if.then, if.else, cycle.body). A gold FACT is one
(op, slot, normalized value) triple per gold step occurrence -- a multiset, so two
identical delays are two facts. Gold steps are matched one-to-one against pred steps
OF THE SAME OP by a maximum-weight assignment; each gold fact then lands in exactly
one of three buckets against its matched pred step:

    matched    -> pred step has the slot with an equal normalized value
    distortion -> pred step HAS the slot but the value differs
    omission   -> pred step lacks the slot entirely (or no pred step of that op)

so   omission + distortion + fact_recall == 1.0   holds by construction (asserted).

Stdlib only. Deterministic (no randomness anywhere).
"""

from __future__ import annotations

import json
import math
import re
import unicodedata

__all__ = ["flatten", "score", "parse_ir_text"]

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

# Scalar slots captured by flatten(), per the Timeline IR grammar (8 step types).
# `args` is not itself a slot -- its keys are flattened to "args.<K>".
SCALAR_SLOTS = (
    "anchor",   # start_at
    "cron",     # start_at
    "cond",     # wait / if
    "edge",     # wait
    "for",      # wait  (sustained-cond duration)
    "duration", # delay
    "period",   # cycle
    "until",    # cycle  (often null -- null is a real, informative value)
    "count",    # cycle
    "var",      # read / call
    "src",      # read
    "target",   # call
)

# Child containers, listed in document order (an `if` reads then-branch first).
CHILD_KEYS = ("then", "else", "body")

# Canonical duration units. Aliases are folded so that a purely cosmetic unit
# spelling ("10 minutes") is not scored as an information distortion.
_UNIT_CANON = {
    "hour": "HOUR", "hours": "HOUR", "hr": "HOUR", "hrs": "HOUR", "h": "HOUR",
    "min": "MIN", "mins": "MIN", "minute": "MIN", "minutes": "MIN", "m": "MIN",
    "sec": "SEC", "secs": "SEC", "second": "SEC", "seconds": "SEC", "s": "SEC",
    "msec": "MSEC", "msecs": "MSEC", "ms": "MSEC",
    "millisecond": "MSEC", "milliseconds": "MSEC",
}

_WS_RE = re.compile(r"\s+")
_DUR_RE = re.compile(r"^([+-]?\d+(?:\.\d+)?)\s*([A-Za-z]+)$")
_DIGITS_RE = re.compile(r"\d+")
# Numeric literal scan. The lookbehind stops "1-5" (a cron dow range) from being
# read as {1, -5} and stops the "0" in "300.0" from being picked up separately.
_NUM_RE = re.compile(r"(?<![\d.])\d+(?:\.\d+)?")
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")

# Quote characters unified before string comparison (cosmetic only).
_QUOTE_MAP = {ord(c): '"' for c in "'‘’“”´`"}


# --------------------------------------------------------------------------- #
# Normalization
# --------------------------------------------------------------------------- #

def _fmt_num(x: float) -> str:
    """4.0 -> '4', 0.5 -> '0.5'  (stable, locale-free)."""
    if isinstance(x, float) and x.is_integer() and abs(x) < 1e15:
        return str(int(x))
    return repr(x) if isinstance(x, float) else str(x)


def _as_number(v):
    """Return float(v) if v is a real number or a numeric string, else None.

    Booleans are explicitly excluded (bool is an int subclass in Python, and
    True must not silently compare equal to 1.0).
    """
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return None if (isinstance(v, float) and math.isnan(v)) else float(v)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            f = float(s)
        except ValueError:
            return None
        return None if math.isnan(f) else f
    return None


def _norm_string(s: str) -> str:
    """casefold + collapse whitespace + unify quote glyphs (cosmetic only)."""
    s = unicodedata.normalize("NFKC", s)
    s = s.translate(_QUOTE_MAP)
    s = _WS_RE.sub(" ", s).strip()
    return s.casefold()


def _norm_cron(v):
    """5-field cron -> fields joined by single spaces, numeric tokens de-padded.

    "0 08 * * 1-5" and "0 8 * * 1-5" are the SAME schedule; zero-padding is a
    spelling choice, not information. Every digit run inside every field is sent
    through int(), so "*/05" -> "*/5" and "06,07" -> "6,7" fold too, while the
    field structure (ranges, lists, steps, dow names) is left untouched -- a real
    edit like 8 -> 9, or a dropped day filter, still reads as a distortion.
    """
    if not isinstance(v, str):
        return _norm_scalar(v)
    fields = [_DIGITS_RE.sub(lambda m: str(int(m.group(0))), f) for f in v.split()]
    return " ".join(fields).casefold()


def _norm_expr(v):
    """Condition expression normalization: whitespace OUTSIDE string literals is
    cosmetic, whitespace INSIDE them is information.

    'T.Temperature >= 26' and 'T.Temperature>=26' are the same condition, so the
    spacing a 2B model happens to use around operators must not register as a
    distortion. Quoted literals are protected: 'X == "good morning"' still
    differs from 'X == "goodmorning"'.
    """
    if not isinstance(v, str):
        return _norm_scalar(v)
    s = unicodedata.normalize("NFKC", v).translate(_QUOTE_MAP)
    parts = s.split('"')
    for i, seg in enumerate(parts):
        # even index = outside a string literal, odd index = inside one
        parts[i] = _WS_RE.sub("", seg) if i % 2 == 0 else _WS_RE.sub(" ", seg)
    return '"'.join(parts).casefold()


def _norm_duration(v):
    """'10 MIN' / '10MIN' / '10 min' / '10.0 minutes' -> '10 MIN'.

    Units are NOT converted between each other: '60 SEC' != '1 MIN'. Folding
    those together would hide a genuine value distortion.
    """
    if isinstance(v, str):
        m = _DUR_RE.match(v.strip())
        if m:
            unit = _UNIT_CANON.get(m.group(2).casefold())
            if unit:
                return "%s %s" % (_fmt_num(float(m.group(1))), unit)
    return _norm_scalar(v)


def _norm_scalar(v):
    """Generic value normalization used for every non-cron, non-duration slot."""
    if v is None:
        return None
    if isinstance(v, bool):
        # unify JSON true / "true" / "True"
        return "true" if v else "false"
    n = _as_number(v)
    if n is not None:
        return n
    if isinstance(v, str):
        return _norm_string(v)
    if isinstance(v, (list, dict)):
        try:
            return _norm_string(json.dumps(v, sort_keys=True, ensure_ascii=False))
        except (TypeError, ValueError):
            return _norm_string(str(v))
    return _norm_string(str(v))


def _norm_slot(slot: str, v):
    if slot == "cron":
        return _norm_cron(v)
    if slot in ("duration", "period", "for"):
        return _norm_duration(v)
    if slot in ("cond", "until"):
        return _norm_expr(v)
    return _norm_scalar(v)


# --------------------------------------------------------------------------- #
# flatten
# --------------------------------------------------------------------------- #

def _flatten_into(steps, depth, path, out):
    if not isinstance(steps, list):
        return
    for st in steps:
        if not isinstance(st, dict):
            # Junk entry: recorded so it still breaks op_seq_match / op counts.
            out.append({"op": "<invalid>", "slots": {}, "depth": depth, "_path": path})
            continue
        op = st.get("op")
        op = _norm_string(op) if isinstance(op, str) else ("<noop>" if op is None else _norm_scalar(op))
        slots = {}
        for slot in SCALAR_SLOTS:
            if slot in st:
                slots[slot] = _norm_slot(slot, st[slot])
        args = st.get("args")
        if isinstance(args, dict):
            # Arg KEYS are casefolded, exactly as op names already are. Otherwise
            # {"mode": "cool"} vs {"Mode": "cool"} reads as a total OMISSION of a
            # value the model in fact copied correctly -- key-case drift is a
            # spelling failure, not an information loss, and it would land on the
            # very number E1 reports.
            for k, v in args.items():
                slots["args.%s" % _norm_string(k if isinstance(k, str) else str(k))] = _norm_scalar(v)
        out.append({"op": op, "slots": slots, "depth": depth, "_path": path})
        for ck in CHILD_KEYS:
            if ck in st and isinstance(st[ck], list):
                _flatten_into(st[ck], depth + 1, path + ("%s.%s" % (op, ck),), out)


def flatten(ir):
    """Depth-first, document-order flattening of {"timeline":[...]}.

    Returns a list of {"op": str, "slots": {slot: normalized value}, "depth": int}.
    Returns [] for anything that is not a dict carrying a list "timeline".
    """
    if not isinstance(ir, dict):
        return []
    tl = ir.get("timeline")
    if not isinstance(tl, list):
        return []
    out = []
    _flatten_into(tl, 0, (), out)
    for e in out:  # `_path` is internal bookkeeping; keep the public shape exact.
        e.pop("_path", None)
    return out


def _flatten_ext(ir):
    """flatten() but keeping the branch path -- used only by the supplementary
    path-aware variant, never by the headline metric."""
    if not isinstance(ir, dict):
        return []
    tl = ir.get("timeline")
    if not isinstance(tl, list):
        return []
    out = []
    _flatten_into(tl, 0, (), out)
    return out


# --------------------------------------------------------------------------- #
# Assignment: gold steps <-> pred steps of the same op
# --------------------------------------------------------------------------- #

def _pair_stats(g, p):
    """(match, present) for one gold/pred step pair.

    present counts gold slots that EXIST in the pred step (matched or not);
    distortions for the pair are therefore present - match.
    """
    ps = p["slots"]
    match = present = 0
    for k, v in g["slots"].items():
        if k in ps:
            present += 1
            if ps[k] == v:
                match += 1
    return match, present


def _hungarian(cost, nr, nc):
    """Exact MIN-cost one-to-one assignment, rectangular, requires nr <= nc.

    Shortest-augmenting-path (Jonker-Volgenant) form of the Hungarian algorithm,
    O(nr^2 * nc), integer arithmetic, no randomness, no iteration over sets.
    Returns a list of length nr: the column chosen for each row.
    """
    INF = float("inf")
    u = [0] * (nr + 1)
    v = [0] * (nc + 1)
    p = [0] * (nc + 1)      # p[j] = 1-based row matched to column j (0 = free)
    way = [0] * (nc + 1)
    for i in range(1, nr + 1):
        p[0] = i
        j0 = 0
        minv = [INF] * (nc + 1)
        used = [False] * (nc + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            row = cost[i0 - 1]
            delta = INF
            j1 = 0
            ui = u[i0]
            for j in range(1, nc + 1):
                if used[j]:
                    continue
                cur = row[j - 1] - ui - v[j]
                if cur < minv[j]:
                    minv[j] = cur
                    way[j] = j0
                if minv[j] < delta:
                    delta = minv[j]
                    j1 = j
            for j in range(nc + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
    out = [None] * nr
    for j in range(1, nc + 1):
        if p[j]:
            out[p[j] - 1] = j - 1
    return out


def _assign(golds, preds):
    """Maximum-weight one-to-one assignment between gold and pred steps.

    Objective is lexicographic, encoded as one integer with provably separated
    weight bands:
        1. maximize matched slots               (the metric we report)
        2. then maximize slots merely PRESENT   (prefer the pred step that at
           least emitted the slot -> that gold fact reads as distortion, not
           omission, which is the honest reading)
        3. then minimize |gold_index - pred_index|  (deterministic tie-break on
           document position; only ever breaks ties between assignments that are
           already equal on 1 and 2, so it cannot move fact_recall)

    Solved EXACTLY at every size by the Hungarian algorithm. This must not be
    size-conditional: an approximate fallback for "large" op groups would make
    the score depend on HOW MANY steps an arm emitted rather than on what it got
    right -- a 15-step runaway would be graded by a different, weaker matcher
    than a 14-step one. Returns a list, one entry per gold step: pred index or
    None (None only when preds run out, i.e. len(preds) < len(golds)).
    """
    m, n = len(golds), len(preds)
    if m == 0 or n == 0:
        return [None] * m

    maxslots = max((len(g["slots"]) for g in golds), default=0) or 1
    pos_span = m + n + 1
    w_pos = 1
    w_pres = m * pos_span + 1
    w_match = w_pres * (m * maxslots + 1)

    sc = [[0] * n for _ in range(m)]
    for i in range(m):
        for j in range(n):
            mt, pr = _pair_stats(golds[i], preds[j])
            sc[i][j] = mt * w_match + pr * w_pres + (pos_span - abs(i - j)) * w_pos

    # Every sc[i][j] > 0, so an optimal solution always fills min(m, n) pairs;
    # gold steps go unassigned only when there are literally not enough preds.
    if m <= n:
        return _hungarian([[-sc[i][j] for j in range(n)] for i in range(m)], m, n)

    cols = _hungarian([[-sc[i][j] for i in range(m)] for j in range(n)], n, m)
    out = [None] * m
    for j, i in enumerate(cols):
        if i is not None:
            out[i] = j
    return out


def _bucket(golds, preds, key):
    """Group steps by `key(step)`, assign within each group, and bucket every
    gold fact into matched / distorted / omitted.

    Returns (n_matched, n_distorted, n_omitted, n_pred_facts_consumed).
    """
    gi_by, pi_by = {}, {}
    for idx, g in enumerate(golds):
        gi_by.setdefault(key(g), []).append(idx)
    for idx, p in enumerate(preds):
        pi_by.setdefault(key(p), []).append(idx)

    n_match = n_dist = n_omit = 0
    consumed = 0
    for k, gidx in gi_by.items():
        pidx = pi_by.get(k, [])
        G = [golds[i] for i in gidx]
        P = [preds[i] for i in pidx]
        asg = _assign(G, P)
        for a, g in zip(asg, G):
            if a is None:
                n_omit += len(g["slots"])
                continue
            ps = P[a]["slots"]
            for slot, val in g["slots"].items():
                if slot not in ps:
                    n_omit += 1
                elif ps[slot] == val:
                    n_match += 1
                    consumed += 1
                else:
                    n_dist += 1
    return n_match, n_dist, n_omit, consumed


# --------------------------------------------------------------------------- #
# Numeric-literal copy recall
# --------------------------------------------------------------------------- #

def _num_literals(ir):
    """Canonical set of numeric literals appearing anywhere in a serialized IR.

    Token-based rather than raw substring search: a raw `"5" in pred_text` test
    would call gold 5 "present" because pred happened to contain 45 or 15. Tokens
    are canonicalized through float, so 300, 300.0 and "300" are one literal.
    """
    if ir is None:
        return set()
    try:
        txt = json.dumps(ir, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):
        txt = str(ir)
    return {float(t) for t in _NUM_RE.findall(txt)}


# --------------------------------------------------------------------------- #
# Tolerant JSON extraction
# --------------------------------------------------------------------------- #

def _strip_fences(text: str) -> str:
    t = text.strip()
    if "```" in t:
        # Prefer the content of the first fenced block.
        parts = t.split("```")
        if len(parts) >= 3:
            body = parts[1]
            nl = body.find("\n")
            if nl != -1 and body[:nl].strip().lower() in ("json", "json5", "js", ""):
                body = body[nl + 1:]
            if "{" in body:
                return body
    return t


def _balanced_spans(s: str):
    """Yield (start, end, closers) for top-level balanced {...} regions, honoring
    JSON string literals and backslash escapes.

    `closers` is "" for a complete object. A trailing UNTERMINATED object is
    yielded last with end == -1 and `closers` holding the exact delimiter string
    ("}]}" etc., innermost first) that would close it -- consumed only by the
    opt-in truncation repair.
    """
    stack = []
    start = -1
    in_str = False
    esc = False
    for i, ch in enumerate(s):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            if not stack and ch == "{":
                start = i
            if stack or ch == "{":
                stack.append("}" if ch == "{" else "]")
        elif ch in "}]":
            if stack and stack[-1] == ch:
                stack.pop()
                if not stack and start >= 0:
                    yield (start, i + 1, "")
                    start = -1
    if stack and start >= 0:
        yield (start, -1, "".join(reversed(stack)))


def _try_load(chunk: str):
    for cand in (chunk, _TRAILING_COMMA_RE.sub(r"\1", chunk)):
        try:
            obj = json.loads(cand, strict=False)
        except (ValueError, TypeError):
            continue
        if isinstance(obj, dict):
            return obj
    return None


def _repair_load(chunk: str, closers: str):
    """Best-effort close of a truncated JSON object. Opt-in only (see below)."""
    # Close a dangling string literal too, then drop the trailing partial token
    # ("...,\"op\": " etc.) by walking back to successive , { [ boundaries.
    for prefix in (chunk, chunk + '"'):
        obj = _try_load(prefix + closers)
        if obj is not None:
            return obj
    cut = len(chunk)
    for _ in range(40):
        cut = max(chunk.rfind(",", 0, cut), chunk.rfind("{", 0, cut),
                  chunk.rfind("[", 0, cut))
        if cut <= 0:
            break
        head = chunk[:cut] if chunk[cut] == "," else chunk[:cut + 1]
        for tail in (closers, closers[1:] if closers else ""):
            obj = _try_load(head + tail)
            if obj is not None:
                return obj
    return None


def parse_ir_text(text, allow_truncation_repair: bool = False):
    """Extract the first JSON object from raw model output.

    Handles code fences, leading prose, trailing commentary and trailing commas
    via a string-aware balanced-brace scan + json.loads(..., strict=False).
    Returns a dict, or None if nothing parses.

    `allow_truncation_repair` (default False) closes an unterminated object by
    appending the missing braces. It is OFF by default ON PURPOSE: the arms emit
    different output lengths, so silently repairing truncation would hand an
    advantage to whichever arm hits the token ceiling. Run the experiment with a
    generous max_tokens instead; the flag exists only for sensitivity checks.
    """
    if not isinstance(text, str) or not text.strip():
        return None
    body = _strip_fences(text)
    for s, e, closers in _balanced_spans(body):
        if e > 0:
            obj = _try_load(body[s:e])
            if obj is not None:
                return obj
        elif allow_truncation_repair:
            obj = _repair_load(body[s:], closers)
            if obj is not None:
                return obj
    # Last resort: the whole payload (e.g. leading "{" lost to fence mangling).
    return _try_load(body)


# --------------------------------------------------------------------------- #
# score
# --------------------------------------------------------------------------- #

_KEYS = (
    "valid_json", "n_gold_ops", "n_pred_ops", "op_recall", "op_seq_match",
    "fact_recall", "omission", "distortion", "num_copy_recall",
    "n_gold_facts", "n_pred_facts", "n_matched_facts", "n_distorted_facts",
    "n_omitted_facts", "op_precision", "spurious_fact_rate",
    "fact_recall_pathaware",
)


def _empty_result(gold_flat, n_gold_facts, n_gold_ops):
    return {
        "valid_json": False,
        "n_gold_ops": n_gold_ops,
        "n_pred_ops": 0,
        "op_recall": 0.0,
        "op_seq_match": 0.0,
        "fact_recall": 0.0,
        "omission": 1.0,
        "distortion": 0.0,
        "num_copy_recall": 0.0,
        "n_gold_facts": n_gold_facts,
        "n_pred_facts": 0,
        "n_matched_facts": 0,
        "n_distorted_facts": 0,
        "n_omitted_facts": n_gold_facts,
        "op_precision": 0.0,
        "spurious_fact_rate": 0.0,
        "fact_recall_pathaware": 0.0,
    }


def score(pred_ir, gold_ir, cmd: str = "") -> dict:
    """Score a predicted Timeline IR against gold. `cmd` is deliberately unused.

    See module docstring for the metric model. Every returned dict satisfies
    omission + distortion + fact_recall == 1.0 (asserted before return).
    """
    del cmd  # arm-agnostic: the scorer must never see the input formatting

    if isinstance(pred_ir, str):          # tolerate a raw model string
        pred_ir = parse_ir_text(pred_ir)

    # Gold guard. A raw ir_gt STRING is accepted (harnesses pass one on retry),
    # but an ungradable gold RAISES rather than scoring. Silently treating a bad
    # gold as "0 facts" would return fact_recall == 1.0 for every row of every
    # arm -- a harness bug that looks exactly like a valid experimental result.
    if isinstance(gold_ir, str):
        gold_ir = parse_ir_text(gold_ir)
    if not (isinstance(gold_ir, dict) and isinstance(gold_ir.get("timeline"), list)):
        raise ValueError(
            "gold_ir is not a Timeline IR ({'timeline': [...]}); got %r"
            % (type(gold_ir).__name__,)
        )

    gold_flat = flatten(gold_ir)
    gold_ext = _flatten_ext(gold_ir)
    n_gold_facts = sum(len(g["slots"]) for g in gold_flat)
    n_gold_ops = len(gold_flat)

    valid = isinstance(pred_ir, dict) and isinstance(pred_ir.get("timeline"), list)
    if not valid:
        res = _empty_result(gold_flat, n_gold_facts, n_gold_ops)
        assert abs(res["omission"] + res["distortion"] + res["fact_recall"] - 1.0) < 1e-9
        return res

    pred_flat = flatten(pred_ir)
    pred_ext = _flatten_ext(pred_ir)
    n_pred_facts = sum(len(p["slots"]) for p in pred_flat)
    n_pred_ops = len(pred_flat)

    # --- op-type metrics -------------------------------------------------- #
    gold_ops = [g["op"] for g in gold_flat]
    pred_ops = [p["op"] for p in pred_flat]
    gcnt, pcnt = {}, {}
    for o in gold_ops:
        gcnt[o] = gcnt.get(o, 0) + 1
    for o in pred_ops:
        pcnt[o] = pcnt.get(o, 0) + 1
    overlap = sum(min(c, pcnt.get(o, 0)) for o, c in gcnt.items())
    op_recall = (overlap / n_gold_ops) if n_gold_ops else 1.0
    op_precision = (overlap / n_pred_ops) if n_pred_ops else (1.0 if not n_gold_ops else 0.0)
    op_seq_match = 1.0 if gold_ops == pred_ops else 0.0

    # --- fact buckets (headline) ------------------------------------------ #
    n_match, n_dist, n_omit, consumed = _bucket(
        gold_flat, pred_flat, key=lambda s: s["op"]
    )
    if n_gold_facts:
        fact_recall = n_match / n_gold_facts
        omission = n_omit / n_gold_facts
        distortion = n_dist / n_gold_facts
    else:
        fact_recall, omission, distortion = 1.0, 0.0, 0.0

    # --- supplementary strict variant ------------------------------------- #
    # Same machinery, but a gold step may only match a pred step sitting in the
    # SAME branch path (if.then vs if.else vs cycle.body vs top level). Catches
    # the one thing the headline metric is blind to: a then/else swap, which
    # flattens to an identical fact multiset. Reported, never headline.
    pm, pd, po, _ = _bucket(
        gold_ext, pred_ext, key=lambda s: (s["op"], s["_path"])
    )
    fact_recall_pa = (pm / n_gold_facts) if n_gold_facts else 1.0

    # --- numeric copy recall ---------------------------------------------- #
    gnums = _num_literals(gold_ir)
    pnums = _num_literals(pred_ir)
    num_copy_recall = (len(gnums & pnums) / len(gnums)) if gnums else 1.0

    res = {
        "valid_json": True,
        "n_gold_ops": n_gold_ops,
        "n_pred_ops": n_pred_ops,
        "op_recall": op_recall,
        "op_seq_match": op_seq_match,
        "fact_recall": fact_recall,
        "omission": omission,
        "distortion": distortion,
        "num_copy_recall": num_copy_recall,
        "n_gold_facts": n_gold_facts,
        "n_pred_facts": n_pred_facts,
        "n_matched_facts": n_match,
        "n_distorted_facts": n_dist,
        "n_omitted_facts": n_omit,
        "op_precision": op_precision,
        "spurious_fact_rate": ((n_pred_facts - consumed) / n_pred_facts) if n_pred_facts else 0.0,
        "fact_recall_pathaware": fact_recall_pa,
    }
    assert n_match + n_dist + n_omit == n_gold_facts, (n_match, n_dist, n_omit, n_gold_facts)
    assert abs(res["omission"] + res["distortion"] + res["fact_recall"] - 1.0) < 1e-9
    return res


# --------------------------------------------------------------------------- #
# Self-test suite
# --------------------------------------------------------------------------- #

def _sa(anchor="now", **kw):
    d = {"op": "start_at", "anchor": anchor}
    d.update(kw)
    return d


def _call(target, args=None, **kw):
    d = {"op": "call", "target": target, "args": {} if args is None else args}
    d.update(kw)
    return d


def _tl(*steps):
    return {"timeline": list(steps)}


def _run_selftest():
    cases = []

    # 1 perfect match
    g = _tl(_sa(), _call("Switch.On"))
    cases.append(("perfect match", g, g,
                  dict(valid_json=True, n_gold_facts=2, n_matched_facts=2,
                       n_distorted_facts=0, n_omitted_facts=0, op_seq_match=1.0,
                       num_copy_recall=1.0)))

    # 2 one op dropped (the delay disappears entirely)
    g = _tl(_sa(), {"op": "delay", "duration": "10 MIN"}, _call("Switch.Off"))
    p = _tl(_sa(), _call("Switch.Off"))
    cases.append(("op dropped (delay)", g, p,
                  dict(valid_json=True, n_gold_facts=3, n_matched_facts=2,
                       n_distorted_facts=0, n_omitted_facts=1, op_seq_match=0.0,
                       num_copy_recall=0.0)))

    # 3 duration changed 10 MIN -> 5 MIN  (distortion, not omission)
    g = _tl(_sa(), {"op": "delay", "duration": "10 MIN"}, _call("Switch.Off"))
    p = _tl(_sa(), {"op": "delay", "duration": "5 MIN"}, _call("Switch.Off"))
    cases.append(("duration 10 MIN -> 5 MIN", g, p,
                  dict(valid_json=True, n_gold_facts=3, n_matched_facts=2,
                       n_distorted_facts=1, n_omitted_facts=0, op_seq_match=1.0,
                       num_copy_recall=0.0)))

    # 4 nested if/then flattened away
    g = _tl(_sa(), {"op": "if", "cond": "Motion.Detected == true",
                    "then": [_call("Switch.On")], "else": []})
    p = _tl(_sa(), _call("Switch.On"))
    cases.append(("nested if flattened away", g, p,
                  dict(valid_json=True, n_gold_facts=3, n_matched_facts=2,
                       n_distorted_facts=0, n_omitted_facts=1, op_seq_match=0.0)))

    # 5 extra spurious op (recall untouched, precision drops)
    g = _tl(_sa(), _call("Switch.On"))
    p = _tl(_sa(), _call("Switch.On"), _call("Speaker.Speak", {"Text": "hi"}))
    cases.append(("extra spurious op", g, p,
                  dict(valid_json=True, n_gold_facts=2, n_matched_facts=2,
                       n_distorted_facts=0, n_omitted_facts=0, op_seq_match=0.0,
                       op_recall=1.0)))

    # 6 cron minute altered
    g = _tl(_sa("cron", cron="45 16 * * *"), _call("Switch.Off"))
    p = _tl(_sa("cron", cron="5 16 * * *"), _call("Switch.Off"))
    cases.append(("cron minute altered", g, p,
                  dict(valid_json=True, n_gold_facts=3, n_matched_facts=2,
                       n_distorted_facts=1, n_omitted_facts=0, op_seq_match=1.0,
                       num_copy_recall=0.5)))

    # 7 malformed JSON -> pred None
    g = _tl(_sa(), _call("Switch.On"))
    cases.append(("malformed json (None)", g, None,
                  dict(valid_json=False, n_gold_facts=2, n_matched_facts=0,
                       n_distorted_facts=0, n_omitted_facts=2, op_seq_match=0.0,
                       omission=1.0, distortion=0.0, fact_recall=0.0,
                       num_copy_recall=0.0)))

    # 8 JSON wrapped in code fences + prose
    g = _tl(_sa(), _call("Switch.On"))
    raw = ('Sure! Here is the Timeline IR for your command.\n\n'
           '```json\n' + json.dumps(g) + '\n```\n\nLet me know if you need changes.')
    cases.append(("fenced json + prose", g, ("RAW", raw),
                  dict(valid_json=True, n_gold_facts=2, n_matched_facts=2,
                       n_distorted_facts=0, n_omitted_facts=0, op_seq_match=1.0)))

    # 9 args key missing
    g = _tl(_sa(), _call("Speaker.Speak", {"Text": "welcome"}))
    p = _tl(_sa(), _call("Speaker.Speak", {}))
    cases.append(("args key missing", g, p,
                  dict(valid_json=True, n_gold_facts=3, n_matched_facts=2,
                       n_distorted_facts=0, n_omitted_facts=1, op_seq_match=1.0)))

    # 10 deeper nesting inside cycle.body (cycle > if > call)
    g = _tl(_sa(),
            {"op": "cycle", "until": None, "period": "5 MIN",
             "body": [{"op": "if", "cond": "Charger.ChargingState == \"fullyCharged\"",
                       "then": [_call("Switch.Off")], "else": []}]})
    p = _tl(_sa(),
            {"op": "cycle", "until": None, "period": "5 MIN",
             "body": [{"op": "if", "cond": "Charger.ChargingState == \"fullyCharged\"",
                       "then": [_call("Switch.Off")], "else": []}]})
    cases.append(("deep nesting in cycle.body", g, p,
                  dict(valid_json=True, n_gold_facts=5, n_matched_facts=5,
                       n_distorted_facts=0, n_omitted_facts=0, op_seq_match=1.0,
                       n_gold_ops=4)))

    # 11 cosmetic format variants must NOT count as distortion
    g = _tl(_sa(), {"op": "delay", "duration": "10 MIN"},
            _call("Oven.AddMoreTime", {"Time": 300.0}))
    p = _tl(_sa(), {"op": "delay", "duration": "10min"},
            _call("Oven.AddMoreTime", {"Time": "300"}))
    cases.append(("cosmetic duration/number variants", g, p,
                  dict(valid_json=True, n_gold_facts=4, n_matched_facts=4,
                       n_distorted_facts=0, n_omitted_facts=0, op_seq_match=1.0,
                       num_copy_recall=1.0)))

    # 12 cycle.until:null present in gold but absent in pred -> omission
    g = _tl(_sa(), {"op": "cycle", "until": None, "period": "1 MIN",
                    "body": [_call("Switch.Toggle")]})
    p = _tl(_sa(), {"op": "cycle", "period": "1 MIN",
                    "body": [_call("Switch.Toggle")]})
    cases.append(("cycle.until null dropped", g, p,
                  dict(valid_json=True, n_gold_facts=4, n_matched_facts=3,
                       n_distorted_facts=0, n_omitted_facts=1, op_seq_match=1.0)))

    # 13 empty gold timeline (degenerate denominator)
    cases.append(("empty gold timeline", _tl(), _tl(),
                  dict(valid_json=True, n_gold_facts=0, n_matched_facts=0,
                       n_distorted_facts=0, n_omitted_facts=0, fact_recall=1.0,
                       omission=0.0, distortion=0.0, op_seq_match=1.0)))

    # 14 wrong op TYPE substituted (wait -> if): facts of both ops are lost
    g = _tl(_sa(), {"op": "wait", "cond": "Door.DoorState == \"open\"", "edge": "none"},
            _call("Switch.On"))
    p = _tl(_sa(), {"op": "if", "cond": "Door.DoorState == \"open\"",
                    "then": [_call("Switch.On")], "else": []})
    cases.append(("op type swapped wait->if", g, p,
                  dict(valid_json=True, n_gold_facts=4, n_matched_facts=2,
                       n_distorted_facts=0, n_omitted_facts=2, op_seq_match=0.0)))

    # 15 then/else SWAP -- documented blind spot of the headline metric
    g = _tl(_sa(), {"op": "if", "cond": "Clock.Hour >= 21",
                    "then": [_call("Switch.Off")], "else": [_call("Switch.On")]})
    p = _tl(_sa(), {"op": "if", "cond": "Clock.Hour >= 21",
                    "then": [_call("Switch.On")], "else": [_call("Switch.Off")]})
    cases.append(("then/else swap (blind spot)", g, p,
                  dict(valid_json=True, n_gold_facts=4, n_matched_facts=4,
                       fact_recall=1.0, fact_recall_pathaware=0.5)))

    # 16 truncated JSON is NOT silently repaired by default
    g = _tl(_sa(), _call("Switch.On"))
    trunc = '{"timeline": [{"op": "start_at", "anchor": "now"}, {"op": "call", "targ'
    cases.append(("truncated output (no repair)", g, ("RAW", trunc),
                  dict(valid_json=False, n_gold_facts=2, n_matched_facts=0,
                       n_omitted_facts=2, omission=1.0)))

    # 17 duplicated gold facts are a multiset (two delays, pred keeps one)
    g = _tl(_sa(), {"op": "delay", "duration": "5 SEC"},
            _call("Siren.SetSirenMode", {"Mode": "emergency"}),
            {"op": "delay", "duration": "5 SEC"}, _call("Switch.Off"))
    p = _tl(_sa(), {"op": "delay", "duration": "5 SEC"},
            _call("Siren.SetSirenMode", {"Mode": "emergency"}), _call("Switch.Off"))
    cases.append(("duplicate delay, one kept", g, p,
                  dict(valid_json=True, n_gold_facts=6, n_matched_facts=5,
                       n_distorted_facts=0, n_omitted_facts=1, op_seq_match=0.0)))

    # --- run --------------------------------------------------------------- #
    hdr = "%-34s %-9s %-24s %s" % ("CASE", "RESULT", "CHECKED", "DETAIL")
    print(hdr)
    print("-" * len(hdr))
    n_pass = n_fail = 0
    for name, gold, pred, exp in cases:
        if isinstance(pred, tuple) and pred and pred[0] == "RAW":
            pred = parse_ir_text(pred[1])
        res = score(pred, gold, cmd="IGNORED BY DESIGN | with | arm-B markers")

        # invariant, on every single case
        inv = res["omission"] + res["distortion"] + res["fact_recall"]
        ok_inv = abs(inv - 1.0) < 1e-9
        assert ok_inv, "%s: invariant broken (%r)" % (name, inv)

        bad = []
        for k, want in exp.items():
            got = res[k]
            same = (abs(got - want) < 1e-9) if isinstance(want, float) else (got == want)
            if not same:
                bad.append("%s exp=%s got=%s" % (k, want, got))
        if bad:
            n_fail += 1
            print("%-34s %-9s %-24s %s" % (name[:34], "FAIL", "%d checks" % len(exp), "; ".join(bad)))
        else:
            n_pass += 1
            detail = ("m=%d d=%d o=%d /%d  fr=%.3f om=%.3f di=%.3f num=%.2f"
                      % (res["n_matched_facts"], res["n_distorted_facts"],
                         res["n_omitted_facts"], res["n_gold_facts"],
                         res["fact_recall"], res["omission"], res["distortion"],
                         res["num_copy_recall"]))
            print("%-34s %-9s %-24s %s" % (name[:34], "PASS", "%d checks" % len(exp), detail))
    print("-" * len(hdr))
    print("%d passed, %d failed  (invariant omission+distortion+fact_recall==1.0 asserted on all %d)"
          % (n_pass, n_fail, len(cases)))

    # --- flatten() shape contract ------------------------------------------ #
    f = flatten(_tl(_sa(), {"op": "cycle", "until": None, "period": "5 MIN",
                            "body": [{"op": "if", "cond": "A.B == 1",
                                      "then": [_call("Switch.Off")], "else": []}]}))
    assert [e["op"] for e in f] == ["start_at", "cycle", "if", "call"], f
    # start_at and cycle are top-level (0); the if sits in cycle.body (1);
    # the call sits in if.then (2).
    assert [e["depth"] for e in f] == [0, 0, 1, 2], f
    assert set(f[0].keys()) == {"op", "slots", "depth"}, f[0].keys()
    assert f[1]["slots"] == {"period": "5 MIN", "until": None}, f[1]["slots"]
    assert flatten(None) == [] and flatten({"error": "x"}) == [] and flatten(42) == []
    assert parse_ir_text("no json here at all") is None
    assert parse_ir_text("") is None
    assert parse_ir_text('prefix {"a":1,} suffix') == {"a": 1}          # trailing comma
    assert parse_ir_text('{"timeline": [{"op": "call"' ) is None        # truncation, no repair
    assert parse_ir_text('{"timeline": [{"op": "call"', allow_truncation_repair=True) is not None
    print("flatten()/parse_ir_text() contract assertions: PASS")

    # --- gold guard: never silently score an ungradable gold as perfect ------ #
    good = _tl(_sa(), _call("Switch.On"))
    assert score(good, json.dumps(good), "") ["fact_recall"] == 1.0   # raw-string gold ok
    for bad_gold in (None, "not json", {"error": "x"}, {"timeline": "nope"}, 42):
        try:
            score(good, bad_gold, "")
        except ValueError:
            pass
        else:
            raise AssertionError("ungradable gold %r did not raise" % (bad_gold,))
    print("gold guard (raw-string gold accepted, ungradable gold raises): PASS")

    # --- real-data smoke test (read-only; skipped if dataset absent) -------- #
    try:
        import csv
        csv.field_size_limit(10 ** 9)
        path = "/home/ikess/joi-llm/joi_new/dataset.csv"
        with open(path, encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        n = 0
        for r in rows:
            gold = json.loads(r["ir_gt"], strict=False)
            s = score(gold, gold, r.get("command_kor", ""))
            assert s["fact_recall"] == 1.0 and s["op_seq_match"] == 1.0, r["index"]
            assert s["num_copy_recall"] == 1.0, r["index"]
            n += 1
        print("real-data identity check on %d dataset rows: PASS (self-score == 1.0)" % n)
    except FileNotFoundError:
        print("real-data identity check: SKIPPED (dataset not found)")

    return n_fail


if __name__ == "__main__":
    import sys
    sys.exit(1 if _run_selftest() else 0)
