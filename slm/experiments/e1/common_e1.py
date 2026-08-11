#!/usr/bin/env python3
"""Shared helpers for E1 (driver + report).

Kept dependency-free (stdlib only) so that BOTH run_e1.py and report.py can run
standalone, and so that --selftest never needs seg.py / score.py / prompts.py.
"""

from __future__ import annotations

import json
import math
import random

# Metric columns printed in the aggregate table, in order.
METRIC_COLS = [
    "fact_recall",
    "omission",
    "distortion",
    "op_recall",
    "op_seq_match",
    "num_copy_recall",
]

BASELINE_ARM = "batch"
ALL_ARMS = ["batch", "marked", "marked_merged", "interleave", "interleave_merged",
            "interleave_append", "interleave_append_merged"]

NAN = float("nan")


# --------------------------------------------------------------------------
# generic coercion helpers
# --------------------------------------------------------------------------
def as_float(v):
    """Coerce a metric value to float; return NaN when it is not numeric."""
    if v is None:
        return NAN
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        f = float(v)
        return f if not math.isnan(f) else NAN
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return NAN
    return NAN


def is_num(v):
    return isinstance(v, float) and not math.isnan(v)


def mean(xs):
    xs = [x for x in xs if is_num(as_float(x))]
    if not xs:
        return NAN
    return sum(as_float(x) for x in xs) / len(xs)


def first_key(d, keys, default=None):
    """Return d[k] for the first key present with a non-None value."""
    if not isinstance(d, dict):
        return default
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def load_json_loose(s):
    """json.loads with strict=False (dataset IR is pretty-printed / may hold raw ctrl chars)."""
    return json.loads(s, strict=False)


def as_ir_dict(x):
    """Normalise anything IR-shaped into {"timeline": [...]}-style dict (or None)."""
    if x is None:
        return None
    if isinstance(x, str):
        try:
            x = load_json_loose(x)
        except Exception:
            return None
    if isinstance(x, dict):
        return x
    if isinstance(x, list):
        return {"timeline": x}
    return None


def timeline_of(ir):
    """Extract the timeline step list from an IR-ish object. [] when absent."""
    d = as_ir_dict(ir)
    if not isinstance(d, dict):
        return []
    tl = d.get("timeline")
    if isinstance(tl, list):
        return tl
    return []


# --------------------------------------------------------------------------
# op-sequence flattening (used for the qualitative report)
# --------------------------------------------------------------------------
def op_labels(timeline, prefix="", _depth=0):
    """Flatten a timeline into a readable op-label sequence, descending into
    if.then / if.else / cycle.body."""
    out = []
    if _depth > 6 or not isinstance(timeline, list):
        return out
    for step in timeline:
        if not isinstance(step, dict):
            out.append(prefix + "?")
            continue
        op = str(step.get("op", "?"))
        label = prefix + op
        if op == "call" and step.get("target"):
            label += "(%s)" % step.get("target")
        elif op == "delay" and step.get("duration") is not None:
            label += "(%s)" % step.get("duration")
        elif op == "read" and step.get("src"):
            label += "(%s)" % step.get("src")
        elif op == "start_at":
            label += "(%s)" % step.get("anchor", "?")
        elif op == "wait" and step.get("cond") is not None:
            label += "(%s)" % step.get("cond")
        elif op == "cycle":
            label += "(period=%s)" % step.get("period")
        elif op == "if" and step.get("cond") is not None:
            label += "(%s)" % step.get("cond")
        out.append(label)
        if op == "if":
            out.extend(op_labels(step.get("then"), prefix + "  then>", _depth + 1))
            out.extend(op_labels(step.get("else"), prefix + "  else>", _depth + 1))
        elif op == "cycle":
            out.extend(op_labels(step.get("body"), prefix + "  body>", _depth + 1))
    return out


def op_seq(ir):
    return op_labels(timeline_of(ir))


# --------------------------------------------------------------------------
# statistics
# --------------------------------------------------------------------------
def percentile(sorted_vals, q):
    """Linear-interpolation percentile. q in [0,1]. sorted_vals must be sorted."""
    n = len(sorted_vals)
    if n == 0:
        return NAN
    if n == 1:
        return float(sorted_vals[0])
    if q <= 0:
        return float(sorted_vals[0])
    if q >= 1:
        return float(sorted_vals[-1])
    pos = q * (n - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return float(sorted_vals[lo])
    frac = pos - lo
    return float(sorted_vals[lo]) * (1.0 - frac) + float(sorted_vals[hi]) * frac


def paired_bootstrap_ci(deltas, n_resamples=10000, seed=0, alpha=0.05):
    """Percentile bootstrap CI for the MEAN of paired per-item deltas.

    Resampling is over items (pairs), which is what makes it "paired": each draw
    takes the whole (arm, baseline) pair, so per-item correlation is preserved.
    Deterministic for a fixed seed.
    """
    deltas = [as_float(d) for d in deltas]
    deltas = [d for d in deltas if is_num(d)]
    n = len(deltas)
    if n == 0:
        return {"n": 0, "mean": NAN, "lo": NAN, "hi": NAN, "n_resamples": 0}
    m = sum(deltas) / n
    if n == 1 or n_resamples <= 0:
        return {"n": n, "mean": m, "lo": m, "hi": m, "n_resamples": 0}
    rng = random.Random(seed)
    randrange = rng.randrange
    means = []
    for _ in range(n_resamples):
        s = 0.0
        for _ in range(n):
            s += deltas[randrange(n)]
        means.append(s / n)
    means.sort()
    return {
        "n": n,
        "mean": m,
        "lo": percentile(means, alpha / 2.0),
        "hi": percentile(means, 1.0 - alpha / 2.0),
        "n_resamples": n_resamples,
    }


def sign_counts(deltas, eps=1e-9):
    """better / worse / equal counts for paired deltas (arm minus baseline)."""
    better = worse = equal = 0
    for d in deltas:
        d = as_float(d)
        if not is_num(d):
            continue
        if d > eps:
            better += 1
        elif d < -eps:
            worse += 1
        else:
            equal += 1
    return {"better": better, "worse": worse, "equal": equal}


# --------------------------------------------------------------------------
# aggregation over the results.json "items" list
# --------------------------------------------------------------------------
def arm_records(items, arm):
    """Yield (item, arm_record) pairs for one arm."""
    for it in items or []:
        rec = (it.get("arms") or {}).get(arm)
        if isinstance(rec, dict):
            yield it, rec


def metric_of(rec, name):
    """Pull a metric out of an arm record (metrics dict first, then top level)."""
    if not isinstance(rec, dict):
        return NAN
    metrics = rec.get("metrics")
    if isinstance(metrics, dict) and name in metrics:
        return as_float(metrics.get(name))
    if name in rec:
        return as_float(rec.get(name))
    return NAN


def valid_of(rec):
    """1.0 / 0.0 validity flag: the driver's own verdict (parsed a non-empty
    timeline with no failed turn) first, then whatever flag score() reports."""
    if not isinstance(rec, dict):
        return 0.0
    v = rec.get("valid")
    if v is not None:
        return as_float(v)
    metrics = rec.get("metrics")
    if isinstance(metrics, dict):
        for k in ("valid", "is_valid", "valid_json", "parse_ok", "well_formed"):
            if k in metrics and metrics[k] is not None:
                return as_float(metrics[k])
    return 1.0 if timeline_of(rec.get("pred_ir")) else 0.0


def extra_metric_names(items, arms):
    """Numeric metric keys score() returns beyond METRIC_COLS (order-stable)."""
    names = []
    for arm in arms:
        for _it, rec in arm_records(items, arm):
            m = rec.get("metrics")
            if not isinstance(m, dict):
                continue
            for k, v in m.items():
                if k in METRIC_COLS or k in names:
                    continue
                if isinstance(v, (bool, int, float)):
                    names.append(k)
    return sorted(names)


def aggregate(items, arms=None, n_resamples=10000, seed=0, baseline=BASELINE_ARM):
    """Build the aggregate summary dict from the per-item records."""
    items = items or []
    if arms is None:
        seen = []
        for it in items:
            for a in (it.get("arms") or {}):
                if a not in seen:
                    seen.append(a)
        arms = [a for a in ALL_ARMS if a in seen] + [a for a in seen if a not in ALL_ARMS]

    rows = {}
    for arm in arms:
        recs = [rec for _it, rec in arm_records(items, arm)]
        row = {
            "arm": arm,
            "n": len(recs),
            "valid_pct": (mean([valid_of(r) for r in recs]) * 100.0) if recs else NAN,
            "mean_latency": mean([r.get("latency_sec") for r in recs]),
            "mean_calls": mean([r.get("num_calls") for r in recs]),
            "parse_failures": sum(int(r.get("parse_failures") or 0) for r in recs),
            "reasoning_fallbacks": sum(int(r.get("reasoning_fallbacks") or 0) for r in recs),
            "http_errors": sum(int(r.get("http_errors") or 0) for r in recs),
        }
        for m in METRIC_COLS:
            row[m] = mean([metric_of(r, m) for r in recs])
        rows[arm] = row

    extras = extra_metric_names(items, arms)
    for arm in arms:
        recs = [rec for _it, rec in arm_records(items, arm)]
        rows[arm]["extra"] = {m: mean([metric_of(r, m) for r in recs]) for m in extras}

    comparisons = []
    if baseline in arms:
        base = {}
        for it, rec in arm_records(items, baseline):
            base[item_key(it)] = rec
        for arm in arms:
            if arm == baseline:
                continue
            cmp_row = {"arm": arm, "baseline": baseline, "metrics": {}}
            paired_keys = []
            for m in METRIC_COLS:
                deltas = []
                keys = []
                for it, rec in arm_records(items, arm):
                    k = item_key(it)
                    b = base.get(k)
                    if b is None:
                        continue
                    a_v, b_v = metric_of(rec, m), metric_of(b, m)
                    if is_num(a_v) and is_num(b_v):
                        deltas.append(a_v - b_v)
                        keys.append(k)
                entry = {"mean_delta": mean(deltas), "n_pairs": len(deltas)}
                entry.update(sign_counts(deltas))
                if m == "fact_recall":
                    entry["ci95"] = paired_bootstrap_ci(
                        deltas, n_resamples=n_resamples, seed=seed
                    )
                    paired_keys = keys
                cmp_row["metrics"][m] = entry
            cmp_row["n_pairs"] = len(paired_keys)
            comparisons.append(cmp_row)

    return {"arms": arms, "rows": rows, "comparisons": comparisons,
            "extra_metrics": extras, "n_items": len(items)}


def item_key(it):
    k = first_key(it, ["idx", "index", "id"])
    if k is None:
        k = first_key(it, ["cmd", "command_kor", "command"], "")
    return str(k)


# --------------------------------------------------------------------------
# pretty printing
# --------------------------------------------------------------------------
def _f(v, nd=3, width=None):
    v = as_float(v)
    s = "  n/a" if not is_num(v) else ("%.*f" % (nd, v))
    return s.rjust(width) if width else s


def format_table(agg):
    cols = [
        ("arm", 11, None),
        ("n", 5, None),
        ("valid%", 7, 1),
        ("fact_recall", 12, 3),
        ("omission", 9, 3),
        ("distortion", 11, 3),
        ("op_recall", 10, 3),
        ("op_seq_match", 13, 3),
        ("num_copy_recall", 16, 3),
        ("mean_latency", 13, 2),
        ("mean_calls", 11, 2),
    ]
    key_of = {
        "valid%": "valid_pct",
        "mean_latency": "mean_latency",
        "mean_calls": "mean_calls",
    }
    head = " | ".join(name.rjust(w) if name != "arm" else name.ljust(w) for name, w, _ in cols)
    lines = [head, "-" * len(head)]
    for arm in agg.get("arms", []):
        row = agg["rows"].get(arm, {})
        cells = []
        for name, w, nd in cols:
            if name == "arm":
                cells.append(str(arm).ljust(w))
            elif name == "n":
                cells.append(str(row.get("n", 0)).rjust(w))
            else:
                cells.append(_f(row.get(key_of.get(name, name)), nd, w))
        lines.append(" | ".join(cells))
    return "\n".join(lines)


def format_extra_table(agg):
    """Secondary table for whatever extra numeric metrics score() reported."""
    extras = agg.get("extra_metrics") or []
    if not extras:
        return ""
    arms = agg.get("arms", [])
    label_w = max(22, max(len(e) for e in extras) + 1)
    w = 12
    head = "extra metric".ljust(label_w) + " | " + " | ".join(str(a).rjust(w) for a in arms)
    lines = ["(extra metrics reported by score(), means over items)", head, "-" * len(head)]
    for e in extras:
        cells = [_f(((agg["rows"].get(a) or {}).get("extra") or {}).get(e), 3, w) for a in arms]
        lines.append(e.ljust(label_w) + " | " + " | ".join(cells))
    lines.append("run-level counters: " + "  ".join(
        "%s parse_fail=%s reasoning_fb=%s http_err=%s" % (
            arm,
            (agg["rows"].get(arm) or {}).get("parse_failures"),
            (agg["rows"].get(arm) or {}).get("reasoning_fallbacks"),
            (agg["rows"].get(arm) or {}).get("http_errors"),
        ) for arm in agg.get("arms", [])))
    return "\n".join(lines)


def format_comparisons(agg):
    out = []
    for cmp_row in agg.get("comparisons", []):
        arm, base = cmp_row["arm"], cmp_row["baseline"]
        fr = cmp_row["metrics"].get("fact_recall", {})
        ci = fr.get("ci95", {}) or {}
        out.append(
            "%s vs %s  (paired, n=%d)" % (arm, base, fr.get("n_pairs", 0))
        )
        out.append(
            "  fact_recall  mean delta = %+0.4f   95%% CI [%s, %s]  (bootstrap %d x, seed 0)"
            % (
                as_float(fr.get("mean_delta")) if is_num(as_float(fr.get("mean_delta"))) else float("nan"),
                _f(ci.get("lo"), 4),
                _f(ci.get("hi"), 4),
                ci.get("n_resamples", 0),
            )
        )
        out.append(
            "               better/worse/equal = %d/%d/%d"
            % (fr.get("better", 0), fr.get("worse", 0), fr.get("equal", 0))
        )
        for m in METRIC_COLS:
            if m == "fact_recall":
                continue
            e = cmp_row["metrics"].get(m, {})
            out.append(
                "  %-15s mean delta = %s   better/worse/equal = %d/%d/%d"
                % (m, _f(e.get("mean_delta"), 4), e.get("better", 0), e.get("worse", 0), e.get("equal", 0))
            )
        out.append("")
    return "\n".join(out).rstrip()
