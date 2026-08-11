#!/usr/bin/env python3
"""E1 driver: batch vs marked vs interleave Timeline-IR generation with a 2B model.

Arms
  batch       one call, whole Korean command            -> full timeline
  marked      one call, clauses joined with " | "       -> full timeline
  interleave  one call per clause, each turn re-emits the FULL updated timeline

Everything is sequential (server runs --max-num-seqs 1), temperature 0, seed 0.

Usage
  /home/ikess/joi-llm/venv_llama/bin/python run_e1.py --limit 20
  /home/ikess/joi-llm/venv_llama/bin/python run_e1.py --selftest
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from common_e1 import (  # noqa: E402
    ALL_ARMS,
    METRIC_COLS,
    NAN,
    aggregate,
    as_float,
    as_ir_dict,
    first_key,
    format_comparisons,
    format_extra_table,
    format_table,
    is_num,
    load_json_loose,
    op_seq,
    paired_bootstrap_ci,
    percentile,
    sign_counts,
    timeline_of,
    valid_of,
)

DEFAULT_ITEMS = os.path.join(HERE, "items.json")
DEFAULT_OUT = os.path.join(HERE, "results.json")
DEFAULT_DATASET = "/home/ikess/joi-llm/joi_new/dataset.csv"
DEFAULT_SERVER = "http://localhost:8002/v1/chat/completions"
DEFAULT_MODEL = "cyankiwi/Qwen3.5-2B-AWQ-4bit"


# ==========================================================================
# HTTP (stdlib only, sequential, 180 s timeout, 2 retries)
# ==========================================================================
class LLMClient:
    def __init__(self, url=DEFAULT_SERVER, model=DEFAULT_MODEL, timeout=180.0,
                 retries=2, max_tokens=1024, verbose=False):
        self.url = url
        self.model = model
        self.timeout = timeout
        self.retries = retries
        self.max_tokens = max_tokens
        self.verbose = verbose
        self.n_calls = 0
        self.n_reasoning_fallback = 0
        self.n_http_errors = 0

    def payload(self, messages):
        return {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": self.max_tokens,
            "seed": 0,
            # Without this the 2B never closes </think> and the whole answer
            # lands in message.reasoning instead of message.content.
            "chat_template_kwargs": {"enable_thinking": False},
        }

    def _post_once(self, messages):
        body = json.dumps(self.payload(messages)).encode("utf-8")
        req = urllib.request.Request(
            self.url,
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
        return json.loads(raw, strict=False)

    def chat(self, messages):
        """One completion. Returns a dict describing the call (never raises)."""
        t0 = time.time()
        last_err = None
        attempts = 0
        for attempt in range(self.retries + 1):
            attempts = attempt + 1
            try:
                data = self._post_once(messages)
                text, used_reasoning, finish = extract_message_text(data)
                self.n_calls += 1
                if used_reasoning:
                    self.n_reasoning_fallback += 1
                return {
                    "text": text,
                    "used_reasoning": used_reasoning,
                    "finish_reason": finish,
                    "attempts": attempts,
                    "error": None,
                    "latency_sec": round(time.time() - t0, 3),
                }
            except urllib.error.HTTPError as e:
                try:
                    detail = e.read().decode("utf-8", "replace")[:500]
                except Exception:
                    detail = ""
                last_err = "HTTP %s: %s" % (e.code, detail)
            except Exception as e:  # URLError, socket.timeout, JSON errors, ...
                last_err = "%s: %s" % (type(e).__name__, e)
            if self.verbose:
                sys.stderr.write("    [retry %d] %s\n" % (attempt + 1, last_err))
            if attempt < self.retries:
                time.sleep(2.0)  # fixed backoff -> deterministic
        self.n_calls += 1
        self.n_http_errors += 1
        return {
            "text": "",
            "used_reasoning": False,
            "finish_reason": None,
            "attempts": attempts,
            "error": last_err,
            "latency_sec": round(time.time() - t0, 3),
        }


def _content_to_text(content):
    """OpenAI content can be str, None, or a list of parts."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, str):
                parts.append(p)
            elif isinstance(p, dict):
                parts.append(str(p.get("text") or p.get("content") or ""))
        return "".join(parts)
    if isinstance(content, dict):
        return str(content.get("text") or "")
    return str(content)


def extract_message_text(data):
    """-> (text, used_reasoning_fallback, finish_reason).

    Reads choices[0].message.content; when that is empty falls back to
    message.reasoning / reasoning_content (the 2B dumps everything there when
    thinking is not properly disabled) and flags the fallback.
    """
    choices = (data or {}).get("choices") or []
    if not choices:
        return "", False, None
    ch = choices[0] or {}
    finish = ch.get("finish_reason")
    msg = ch.get("message") or {}
    text = _content_to_text(msg.get("content")).strip()
    if text:
        return text, False, finish
    for k in ("reasoning", "reasoning_content"):
        alt = _content_to_text(msg.get(k)).strip()
        if alt:
            return alt, True, finish
    # very old-style completion field
    alt = _content_to_text(ch.get("text")).strip()
    return alt, False, finish


# ==========================================================================
# items
# ==========================================================================
def normalise_item(raw, i, segment_kor=None):
    """Normalise one item dict coming from items.json / build_items()."""
    cmd = first_key(raw, ["cmd", "command_kor", "command", "kor", "text"], "")
    clauses = first_key(raw, ["clauses", "segments", "clause_list", "parts"])
    if not isinstance(clauses, list) or not clauses:
        clauses = None
    if clauses is None and segment_kor is not None and cmd:
        try:
            clauses = list(segment_kor(cmd))
        except Exception:
            clauses = None
    if not clauses:
        clauses = [cmd] if cmd else []
    clauses = [str(c).strip() for c in clauses if str(c).strip()]

    gt_raw = first_key(raw, ["ir_gt", "gt_ir", "gt", "ir", "target_ir"])
    gt = as_ir_dict(gt_raw)

    # NOTE: devices is passed to prompts.build_*_messages VERBATIM. items.json keeps
    # it as a JSON *string* and prompts.py .strip()s it, so never coerce it here.
    devices = first_key(raw, ["devices", "connected_devices", "device_list", "services"])

    idx = first_key(raw, ["idx", "index", "id"], i)
    item = dict(raw) if isinstance(raw, dict) else {}
    item.update(
        {
            "idx": idx,
            "cmd": cmd,
            "clauses": clauses,
            "n_clauses": len(clauses),
            "ir_gt": gt if gt is not None else gt_raw,
            "ir_gt_raw": gt_raw if not isinstance(gt_raw, (dict, list)) else None,
            "devices": devices,
            "category_v2": first_key(raw, ["category_v2", "category"]),
        }
    )
    item["gt_ops"] = op_seq(item["ir_gt"])
    return item


def load_items(path, build_items=None, segment_kor=None, dataset=DEFAULT_DATASET):
    """Load items.json; if absent, try to build them via seg.build_items()."""
    raw_items = None
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            raw_items = first_key(data, ["items", "data", "rows"]) or []
        elif isinstance(data, list):
            raw_items = data
        else:
            raise SystemExit("items file %s has unexpected shape %s" % (path, type(data)))
    elif build_items is not None:
        last = None
        for args in ((dataset,), (), (dataset, None)):
            try:
                raw_items = build_items(*args)
                break
            except TypeError as e:
                last = e
                continue
        if raw_items is None:
            raise SystemExit(
                "items file %s missing and build_items() could not be called: %s" % (path, last)
            )
        if isinstance(raw_items, dict):
            raw_items = first_key(raw_items, ["items", "data", "rows"]) or []
    else:
        raise SystemExit("items file not found: %s" % path)

    return [normalise_item(r, i, segment_kor) for i, r in enumerate(raw_items)]


# ==========================================================================
# parsing / scoring wrappers (defensive: other modules are written in parallel)
# ==========================================================================
def safe_parse(parse_ir_text, text):
    """-> (ir_dict_or_None, error_str_or_None). Accepts dict / list / (ir, err) tuple."""
    if not text:
        return None, "empty response"
    try:
        out = parse_ir_text(text)
    except Exception as e:
        return None, "parse_ir_text raised %s: %s" % (type(e).__name__, e)
    if isinstance(out, tuple):
        out = out[0] if out else None
    ir = as_ir_dict(out)
    if ir is None:
        return None, "unparseable"
    if "error" in ir and "timeline" not in ir:
        return ir, "model returned error: %s" % str(ir.get("error"))[:120]
    if not isinstance(ir.get("timeline"), list):
        return ir, "no timeline list in parsed IR"
    return ir, None


def safe_score(score, pred_ir, item):
    """score(pred, gt, cmd) with a raw-gt retry; never raises."""
    gt = item.get("ir_gt")
    cmd = item.get("cmd", "")
    errs = []
    for gt_arg in (gt, item.get("ir_gt_raw")):
        if gt_arg is None:
            continue
        try:
            out = score(pred_ir, gt_arg, cmd)
        except Exception as e:
            errs.append("%s: %s" % (type(e).__name__, e))
            continue
        if isinstance(out, dict):
            return out, None
        errs.append("score() returned %s, expected dict" % type(out).__name__)
    return {}, " | ".join(errs) if errs else "score() produced nothing"


# ==========================================================================
# arms
# ==========================================================================
_DEV_PREF = {}  # fn-name -> index of the devices representation that worked


def _devices_variants(item):
    """prompts.py takes `devices` verbatim; items.json stores it as a JSON string.
    Offer the raw value first, then the other representation as a fallback so a
    signature mismatch degrades instead of killing the run."""
    d = item.get("devices")
    out = [d]
    if isinstance(d, str):
        try:
            out.append(load_json_loose(d))
        except Exception:
            pass
    elif isinstance(d, (dict, list)):
        out.append(json.dumps(d, ensure_ascii=False, indent=2))
    elif d is None:
        out = ["{}", {}]
    return out


def build_msgs(fn, head_args, item):
    """Call a prompts builder with `devices` as its LAST argument."""
    variants = _devices_variants(item)
    order = list(range(len(variants)))
    pref = _DEV_PREF.get(fn.__name__)
    if pref is not None and pref < len(order):
        order = [pref] + [i for i in order if i != pref]
    last_err = None
    for i in order:
        try:
            msgs = fn(*(list(head_args) + [variants[i]]))
            _DEV_PREF[fn.__name__] = i
            return msgs
        except (TypeError, AttributeError) as e:
            last_err = e
    raise last_err if last_err else RuntimeError("no devices representation worked")


def _blank_arm_record(arm):
    return {
        "arm": arm,
        "calls": [],
        "pred_ir": None,
        "pred_ops": [],
        "metrics": {},
        "latency_sec": 0.0,
        "num_calls": 0,
        "parse_failures": 0,
        "reasoning_fallbacks": 0,
        "http_errors": 0,
        "errors": [],
    }


def _record_call(rec, call, tag, parsed_ok, parse_err):
    rec["calls"].append(
        {
            "tag": tag,
            "raw": call.get("text", ""),
            "used_reasoning": bool(call.get("used_reasoning")),
            "finish_reason": call.get("finish_reason"),
            "attempts": call.get("attempts"),
            "latency_sec": call.get("latency_sec"),
            "http_error": call.get("error"),
            "parsed_ok": bool(parsed_ok),
            "parse_error": parse_err,
        }
    )
    rec["num_calls"] += 1
    rec["latency_sec"] = round(rec["latency_sec"] + float(call.get("latency_sec") or 0.0), 3)
    if call.get("used_reasoning"):
        rec["reasoning_fallbacks"] += 1
    if call.get("error"):
        rec["http_errors"] += 1
        rec["errors"].append("%s: %s" % (tag, call["error"]))
    if not parsed_ok:
        rec["parse_failures"] += 1
        if parse_err and not call.get("error"):
            rec["errors"].append("%s: %s" % (tag, parse_err))


def run_batch(item, client, P, parse_ir_text):
    rec = _blank_arm_record("batch")
    msgs = build_msgs(P["build_batch_messages"], [item["cmd"]], item)
    call = client.chat(msgs)
    ir, err = safe_parse(parse_ir_text, call["text"])
    _record_call(rec, call, "batch", ir is not None and err is None, err)
    rec["pred_ir"] = ir if (ir is not None and err is None) else (ir or {"timeline": []})
    return rec


def run_marked(item, client, P, parse_ir_text, joiner=" | ",
               clause_key="clauses", arm="marked"):
    rec = _blank_arm_record(arm)
    clauses = item.get(clause_key) or item.get("clauses")
    marked = joiner.join(clauses) if clauses else item["cmd"]
    rec["marked_input"] = marked
    msgs = build_msgs(P["build_marked_messages"], [marked], item)
    call = client.chat(msgs)
    ir, err = safe_parse(parse_ir_text, call["text"])
    _record_call(rec, call, arm, ir is not None and err is None, err)
    rec["pred_ir"] = ir if (ir is not None and err is None) else (ir or {"timeline": []})
    return rec


def run_interleave(item, client, P, parse_ir_text, clause_key="clauses", arm="interleave"):
    rec = _blank_arm_record(arm)
    ir_so_far = []          # list of timeline steps; starts empty per spec
    states = []
    clauses = item.get(clause_key) or item.get("clauses") or [item["cmd"]]
    for i, clause in enumerate(clauses):
        done = clauses[:i]
        msgs = build_msgs(P["build_step_messages"], [done, clause, ir_so_far], item)
        call = client.chat(msgs)
        ir, err = safe_parse(parse_ir_text, call["text"])
        ok = ir is not None and err is None
        if ok:
            ir_so_far = timeline_of(ir)   # model re-emits the FULL timeline each turn
        # on failure: keep the previous ir_so_far (spec) and count the failure
        _record_call(rec, call, "turn%d" % (i + 1), ok, err)
        states.append({"turn": i + 1, "clause": clause, "n_steps": len(ir_so_far)})
    rec["turn_states"] = states
    rec["pred_ir"] = {"timeline": ir_so_far}
    return rec


def _parse_json_obj(parse_ir_text, text):
    """Tolerant JSON-object extraction with NO timeline requirement."""
    if not text:
        return None, "empty response"
    try:
        out = parse_ir_text(text)
    except Exception as e:
        out = None
        _ = e
    if isinstance(out, tuple):
        out = out[0] if out else None
    if isinstance(out, dict):
        return out, None
    # fall back to a balanced-brace scan of the raw text
    s = text.strip()
    if s.startswith("```"):
        s = s.split("```")[1] if len(s.split("```")) > 1 else s
        s = s[4:] if s.lower().startswith("json") else s
    i = s.find("{")
    if i < 0:
        return None, "no JSON object"
    depth, in_str, esc = 0, False, False
    for j in range(i, len(s)):
        ch = s[j]
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
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(s[i:j + 1], strict=False), None
                except Exception as e:
                    return None, "json.loads failed: %s" % e
    return None, "unbalanced JSON object"


def run_interleave_append(item, client, P, parse_ir_text,
                          clause_key="clauses", arm="interleave_append"):
    """Incremental, but each turn emits ONLY the new steps (constant-length output)."""
    from append_arm import build_append_messages, apply_append

    rec = _blank_arm_record(arm)
    state, states = [], []
    clauses = item.get(clause_key) or item.get("clauses") or [item["cmd"]]
    devices = _devices_variants(item)[0]
    for i, clause in enumerate(clauses):
        msgs = build_append_messages(clauses[:i], clause, state, devices)
        call = client.chat(msgs)
        # NOTE: this arm emits {"into":..., "append":[...]}, NOT a timeline object,
        # so safe_parse's "must contain a timeline list" contract does not apply.
        obj, err = _parse_json_obj(parse_ir_text, call["text"])
        ok = obj is not None and err is None
        if ok:
            state, aerr = apply_append(state, obj)
            if aerr:
                ok, err = False, aerr
        _record_call(rec, call, "turn%d" % (i + 1), ok, err)
        states.append({"turn": i + 1, "clause": clause, "n_steps": len(state)})
    rec["turn_states"] = states
    rec["pred_ir"] = {"timeline": state}
    return rec


def run_interleave_append_merged(item, client, P, parse_ir_text):
    return run_interleave_append(item, client, P, parse_ir_text,
                                 clause_key="clauses_merged",
                                 arm="interleave_append_merged")


def run_marked_merged(item, client, P, parse_ir_text):
    return run_marked(item, client, P, parse_ir_text,
                      clause_key="clauses_merged", arm="marked_merged")


def run_interleave_merged(item, client, P, parse_ir_text):
    return run_interleave(item, client, P, parse_ir_text,
                          clause_key="clauses_merged", arm="interleave_merged")


ARM_RUNNERS = {"batch": run_batch, "marked": run_marked, "interleave": run_interleave,
               "marked_merged": run_marked_merged,
               "interleave_merged": run_interleave_merged,
               "interleave_append": run_interleave_append,
               "interleave_append_merged": run_interleave_append_merged}


# ==========================================================================
# output
# ==========================================================================
def write_results(path, payload):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def progress_line(n_done, n_total, item, results_for_item, elapsed):
    bits = []
    for arm in ALL_ARMS:
        rec = results_for_item.get(arm)
        if rec is None:
            continue
        fr = as_float((rec.get("metrics") or {}).get("fact_recall"))
        flag = ""
        if rec.get("parse_failures"):
            flag += "!"
        if rec.get("http_errors"):
            flag += "x"
        bits.append("%s=%s%s" % (arm[:4], ("%.2f" % fr) if is_num(fr) else " n/a", flag))
    return "[%4d/%4d] idx=%-5s cl=%d %s  %5.1fs  %s" % (
        n_done,
        n_total,
        str(item.get("idx")),
        item.get("n_clauses", 0),
        " ".join(bits),
        elapsed,
        (item.get("cmd") or "")[:40].replace("\n", " "),
    )


# ==========================================================================
# main
# ==========================================================================
def main(argv=None):
    ap = argparse.ArgumentParser(description="E1: batch vs marked vs interleave IR generation")
    ap.add_argument("--items", default=DEFAULT_ITEMS)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--limit", type=int, default=0, help="0 = all items")
    ap.add_argument("--arms", default="batch,marked,interleave")
    ap.add_argument("--server", default=DEFAULT_SERVER)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--dataset", default=DEFAULT_DATASET,
                    help="used only when --items does not exist (seg.build_items)")
    ap.add_argument("--max-tokens", type=int, default=1024)
    ap.add_argument("--timeout", type=float, default=180.0)
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--bootstrap", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--start", type=int, default=0, help="skip the first N items")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--selftest", action="store_true", help="run offline unit tests and exit")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    # lazy imports: sibling modules are written in parallel by other agents
    from seg import segment_kor, build_items          # noqa: F401
    from score import score, parse_ir_text
    import prompts as prompts_mod

    P = {
        "build_batch_messages": prompts_mod.build_batch_messages,
        "build_marked_messages": prompts_mod.build_marked_messages,
        "build_step_messages": prompts_mod.build_step_messages,
    }

    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    unknown = [a for a in arms if a not in ARM_RUNNERS]
    if unknown:
        raise SystemExit("unknown arm(s): %s (known: %s)" % (unknown, list(ARM_RUNNERS)))

    items = load_items(args.items, build_items=build_items, segment_kor=segment_kor,
                       dataset=args.dataset)
    if args.start:
        items = items[args.start:]
    if args.limit and args.limit > 0:
        items = items[: args.limit]

    client = LLMClient(url=args.server, model=args.model, timeout=args.timeout,
                       retries=args.retries, max_tokens=args.max_tokens, verbose=args.verbose)

    payload = {
        "meta": {
            "server": args.server,
            "model": args.model,
            "arms": arms,
            "items_file": os.path.abspath(args.items),
            "n_items_planned": len(items),
            "limit": args.limit,
            "start": args.start,
            "max_tokens": args.max_tokens,
            "temperature": 0,
            "seed": 0,
            "enable_thinking": False,
            "bootstrap_resamples": args.bootstrap,
            "bootstrap_seed": args.seed,
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "finished_at": None,
            "python": sys.version.split()[0],
        },
        "items": [],
        "aggregate": None,
    }

    print("E1  arms=%s  items=%d  server=%s" % (",".join(arms), len(items), args.server), flush=True)
    t_start = time.time()
    interrupted = False
    try:
        for n, item in enumerate(items, 1):
            t0 = time.time()
            out_item = {
                "idx": item.get("idx"),
                "cmd": item.get("cmd"),
                "clauses": item.get("clauses"),
                "n_clauses": item.get("n_clauses"),
                "category_v2": item.get("category_v2"),
                "devices": item.get("devices"),
                "ir_gt": item.get("ir_gt"),
                "gt_ops": item.get("gt_ops"),
                "arms": {},
            }
            for arm in arms:
                try:
                    rec = ARM_RUNNERS[arm](item, client, P, parse_ir_text)
                except Exception as e:
                    rec = _blank_arm_record(arm)
                    rec["pred_ir"] = {"timeline": []}
                    rec["errors"].append("arm crashed: %s: %s" % (type(e).__name__, e))
                    rec["traceback"] = traceback.format_exc()[-2000:]
                pred = as_ir_dict(rec.get("pred_ir")) or {"timeline": []}
                rec["pred_ir"] = pred
                rec["pred_ops"] = op_seq(pred)
                metrics, serr = safe_score(score, pred, item)
                rec["metrics"] = metrics
                if serr:
                    rec["errors"].append("score: %s" % serr)
                # valid = we ended up with a usable non-empty timeline. Failed
                # turns are still visible via parse_failures / final_parse_ok.
                rec["valid"] = 1.0 if timeline_of(pred) else 0.0
                rec["final_parse_ok"] = bool(rec["calls"] and rec["calls"][-1].get("parsed_ok"))
                out_item["arms"][arm] = rec
            payload["items"].append(out_item)
            write_results(args.out, payload)  # flush after every item
            print(progress_line(n, len(items), item, out_item["arms"], time.time() - t0), flush=True)
    except KeyboardInterrupt:
        interrupted = True
        print("\n[interrupted] keeping %d completed items" % len(payload["items"]), flush=True)

    payload["meta"]["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    payload["meta"]["wall_clock_sec"] = round(time.time() - t_start, 1)
    payload["meta"]["interrupted"] = interrupted
    payload["meta"]["n_items_done"] = len(payload["items"])
    payload["meta"]["total_llm_calls"] = client.n_calls
    payload["meta"]["total_reasoning_fallbacks"] = client.n_reasoning_fallback
    payload["meta"]["total_http_errors"] = client.n_http_errors

    agg = aggregate(payload["items"], arms=arms, n_resamples=args.bootstrap, seed=args.seed)
    payload["aggregate"] = agg
    write_results(args.out, payload)

    print()
    print(format_table(agg))
    print()
    extra = format_extra_table(agg)
    if extra:
        print(extra)
        print()
    print(format_comparisons(agg))
    print()
    print("reasoning-field fallbacks: %d / %d calls    http errors: %d"
          % (client.n_reasoning_fallback, client.n_calls, client.n_http_errors))
    print("wrote %s" % os.path.abspath(args.out))
    return 0


# ==========================================================================
# offline self-test (no server, no sibling modules)
# ==========================================================================
def _approx(a, b, tol=1e-9):
    return abs(a - b) <= tol


def selftest():
    fails = []

    def check(name, cond, extra=""):
        if cond:
            print("  ok   %s" % name)
        else:
            print("  FAIL %s %s" % (name, extra))
            fails.append(name)

    print("[selftest] percentile")
    v = [0.0, 1.0, 2.0, 3.0, 4.0]
    check("p0", _approx(percentile(v, 0.0), 0.0))
    check("p100", _approx(percentile(v, 1.0), 4.0))
    check("p50", _approx(percentile(v, 0.5), 2.0))
    check("p25 interpolates", _approx(percentile(v, 0.25), 1.0))
    check("p10 interpolates", _approx(percentile(v, 0.1), 0.4))
    check("empty -> nan", not is_num(percentile([], 0.5)))
    check("single", _approx(percentile([7.0], 0.3), 7.0))

    print("[selftest] paired_bootstrap_ci")
    const = paired_bootstrap_ci([0.25] * 40, n_resamples=200, seed=0)
    check("constant deltas -> point CI",
          _approx(const["mean"], 0.25) and _approx(const["lo"], 0.25) and _approx(const["hi"], 0.25),
          str(const))
    d = [0.1, -0.2, 0.3, 0.0, 0.5, -0.1, 0.2, 0.4, -0.3, 0.15]
    a1 = paired_bootstrap_ci(d, n_resamples=2000, seed=0)
    a2 = paired_bootstrap_ci(d, n_resamples=2000, seed=0)
    a3 = paired_bootstrap_ci(d, n_resamples=2000, seed=1)
    check("mean matches", _approx(a1["mean"], sum(d) / len(d)))
    check("deterministic for same seed", a1 == a2, "%s vs %s" % (a1, a2))
    check("different seed moves CI", (a1["lo"], a1["hi"]) != (a3["lo"], a3["hi"]))
    check("lo <= mean <= hi", a1["lo"] <= a1["mean"] <= a1["hi"], str(a1))
    check("CI inside data range", min(d) <= a1["lo"] and a1["hi"] <= max(d), str(a1))
    big = paired_bootstrap_ci([1.0] * 30 + [0.0] * 30, n_resamples=2000, seed=0)
    check("half/half mean 0.5", _approx(big["mean"], 0.5))
    check("half/half CI straddles", big["lo"] < 0.5 < big["hi"], str(big))
    check("empty -> nan", not is_num(paired_bootstrap_ci([], n_resamples=10)["mean"]))
    check("nan filtered", _approx(paired_bootstrap_ci([1.0, NAN, 1.0], n_resamples=50)["mean"], 1.0))

    print("[selftest] sign_counts")
    sc = sign_counts([0.1, -0.1, 0.0, 0.0, 0.2])
    check("sign counts", sc == {"better": 2, "worse": 1, "equal": 2}, str(sc))

    print("[selftest] timeline / op_seq")
    ir = {
        "timeline": [
            {"op": "start_at", "anchor": "now"},
            {"op": "if", "cond": "A.B == true",
             "then": [{"op": "call", "target": "Light.On", "args": {}}],
             "else": [{"op": "delay", "duration": "5 MIN"}]},
            {"op": "cycle", "until": None, "period": "1 MIN",
             "body": [{"op": "call", "target": "Fan.Off", "args": {}}, {"op": "break"}]},
        ]
    }
    ops = op_seq(ir)
    check("op count", len(ops) == 7, str(ops))
    check("nested call labelled", any("Light.On" in o and "then>" in o for o in ops), str(ops))
    check("cycle body labelled", any("Fan.Off" in o and "body>" in o for o in ops), str(ops))
    check("list IR accepted", op_seq(ir["timeline"]) == ops)
    check("string IR accepted", op_seq(json.dumps(ir)) == ops)
    check("garbage IR -> []", op_seq("not json") == [] and op_seq(None) == [])
    check("timeline_of dict", len(timeline_of(ir)) == 3)
    check("timeline_of missing", timeline_of({"error": "x"}) == [])

    print("[selftest] extract_message_text")
    r1 = {"choices": [{"message": {"content": '{"timeline":[]}'}, "finish_reason": "stop"}]}
    t, fb, fin = extract_message_text(r1)
    check("content path", t == '{"timeline":[]}' and fb is False and fin == "stop")
    r2 = {"choices": [{"message": {"content": "", "reasoning": "  fallback text  "}}]}
    t, fb, _ = extract_message_text(r2)
    check("reasoning fallback", t == "fallback text" and fb is True)
    r3 = {"choices": [{"message": {"content": None, "reasoning_content": "rc"}}]}
    t, fb, _ = extract_message_text(r3)
    check("reasoning_content fallback", t == "rc" and fb is True)
    r4 = {"choices": [{"message": {"content": [{"type": "text", "text": "a"}, {"text": "b"}]}}]}
    t, fb, _ = extract_message_text(r4)
    check("list content", t == "ab" and fb is False)
    check("no choices", extract_message_text({"choices": []}) == ("", False, None))
    check("garbage response", extract_message_text(None) == ("", False, None))

    print("[selftest] safe_parse")
    good = lambda s: json.loads(s)                     # noqa: E731
    check("parse ok", safe_parse(good, '{"timeline":[{"op":"break"}]}')[1] is None)
    check("parse empty text", safe_parse(good, "")[0] is None)
    boom = lambda s: (_ for _ in ()).throw(ValueError("nope"))   # noqa: E731
    ir_, e_ = safe_parse(boom, "xx")
    check("parser exception caught", ir_ is None and "ValueError" in e_)
    check("None from parser", safe_parse(lambda s: None, "xx")[0] is None)
    ir_, e_ = safe_parse(lambda s: {"error": "unsupported"}, "xx")
    check("model error object flagged", e_ is not None and "unsupported" in e_)
    ir_, e_ = safe_parse(lambda s: ({"timeline": []}, None), "xx")
    check("tuple return", e_ is None and ir_ == {"timeline": []})
    ir_, e_ = safe_parse(lambda s: [{"op": "break"}], "xx")
    check("bare list return", e_ is None and ir_["timeline"] == [{"op": "break"}])

    print("[selftest] safe_score")
    item = {"cmd": "c", "ir_gt": {"timeline": []}, "ir_gt_raw": None}
    m, e = safe_score(lambda p, g, c: {"fact_recall": 1.0}, {"timeline": []}, item)
    check("score ok", m == {"fact_recall": 1.0} and e is None)
    m, e = safe_score(lambda p, g, c: 1 / 0, {"timeline": []}, item)
    check("score crash caught", m == {} and "ZeroDivisionError" in e)
    m, e = safe_score(lambda p, g, c: "nope", {"timeline": []}, item)
    check("score non-dict caught", m == {} and "expected dict" in e)

    print("[selftest] normalise_item")
    it = normalise_item(
        {"index": 7, "command_kor": "불 켜고 5분 뒤 꺼줘",
         "ir_gt": '{"timeline": [{"op": "start_at", "anchor": "now"}]}',
         "connected_devices": '{"L": {"category": ["Light"]}}'},
        0, segment_kor=lambda s: ["불 켜고", "5분 뒤 꺼줘"])
    check("idx alias", it["idx"] == 7)
    check("cmd alias", it["cmd"].startswith("불"))
    check("clauses via segment_kor", it["clauses"] == ["불 켜고", "5분 뒤 꺼줘"] and it["n_clauses"] == 2)
    check("ir_gt parsed", isinstance(it["ir_gt"], dict) and it["gt_ops"] == ["start_at(now)"])
    check("devices kept verbatim", it["devices"] == '{"L": {"category": ["Light"]}}')
    it2 = normalise_item({"cmd": "x", "clauses": ["a", "b"], "ir_gt": {"timeline": []}}, 3)
    check("explicit clauses kept", it2["clauses"] == ["a", "b"] and it2["idx"] == 3)
    it3 = normalise_item({"cmd": "solo", "ir_gt": {"timeline": []}}, 4)
    check("no segmenter -> single clause", it3["clauses"] == ["solo"])

    print("[selftest] build_msgs / devices variants")
    _DEV_PREF.clear()
    str_item = {"devices": '{"L": 1}'}
    dict_item = {"devices": {"L": 1}}

    def wants_str(cmd, devices):
        return [{"role": "user", "content": cmd + devices.strip()}]

    def wants_dict(cmd, devices):
        return [{"role": "user", "content": cmd + str(sorted(devices.keys()))}]

    check("string devices -> string builder",
          build_msgs(wants_str, ["c"], str_item)[0]["content"] == 'c{"L": 1}')
    check("string devices -> dict builder falls back",
          build_msgs(wants_dict, ["c"], str_item)[0]["content"] == "c['L']")
    check("dict devices -> string builder falls back",
          build_msgs(wants_str, ["c"], dict_item)[0]["content"].startswith("c{"))
    check("dict devices -> dict builder",
          build_msgs(wants_dict, ["c"], dict_item)[0]["content"] == "c['L']")
    check("preference cached", _DEV_PREF.get("wants_dict") is not None)
    check("missing devices tolerated",
          build_msgs(wants_str, ["c"], {})[0]["content"] == "c{}")
    try:
        build_msgs(lambda cmd, devices: 1 / 0, ["c"], str_item)
        check("non-signature error propagates", False)
    except ZeroDivisionError:
        check("non-signature error propagates", True)
    _DEV_PREF.clear()

    print("[selftest] aggregate + table")
    def mk(fr, om, di, orc, osm, ncr, lat, calls, pf=0, rf=0, valid=1.0):
        return {
            "metrics": {"fact_recall": fr, "omission": om, "distortion": di,
                        "op_recall": orc, "op_seq_match": osm, "num_copy_recall": ncr,
                        "valid": valid},
            "latency_sec": lat, "num_calls": calls, "parse_failures": pf,
            "reasoning_fallbacks": rf, "http_errors": 0,
            "pred_ir": {"timeline": [{"op": "break"}]},
        }

    synth = []
    for i in range(6):
        b = 0.5
        m_ = 0.5 + (0.1 if i % 2 == 0 else -0.1)
        s = 0.5 + 0.2
        synth.append({
            "idx": i, "cmd": "c%d" % i, "clauses": ["a", "b"], "ir_gt": {"timeline": []},
            "arms": {
                "batch": mk(b, 0.4, 0.1, 0.6, 0.0, 1.0, 1.0, 1),
                "marked": mk(m_, 0.3, 0.1, 0.7, 1.0, 1.0, 2.0, 1),
                "interleave": mk(s, 0.2, 0.1, 0.8, 1.0, 1.0, 3.0, 2, pf=(1 if i == 0 else 0)),
            },
        })
    agg = aggregate(synth, arms=ALL_ARMS, n_resamples=500, seed=0)
    check("row n", agg["rows"]["batch"]["n"] == 6)
    check("batch fact_recall", _approx(agg["rows"]["batch"]["fact_recall"], 0.5))
    check("interleave fact_recall", _approx(agg["rows"]["interleave"]["fact_recall"], 0.7))
    check("mean_calls", _approx(agg["rows"]["interleave"]["mean_calls"], 2.0))
    check("mean_latency", _approx(agg["rows"]["marked"]["mean_latency"], 2.0))
    check("valid pct", _approx(agg["rows"]["batch"]["valid_pct"], 100.0))
    check("parse failures summed", agg["rows"]["interleave"]["parse_failures"] == 1)
    cmps = {c["arm"]: c for c in agg["comparisons"]}
    check("two comparisons", {"marked", "interleave"} <= set(cmps) and "batch" not in cmps)
    check("marked delta ~0", _approx(cmps["marked"]["metrics"]["fact_recall"]["mean_delta"], 0.0, 1e-9))
    check("marked 3/3 split",
          cmps["marked"]["metrics"]["fact_recall"]["better"] == 3
          and cmps["marked"]["metrics"]["fact_recall"]["worse"] == 3)
    fr_i = cmps["interleave"]["metrics"]["fact_recall"]
    check("interleave delta 0.2", _approx(fr_i["mean_delta"], 0.2))
    check("interleave all better", fr_i["better"] == 6 and fr_i["worse"] == 0)
    check("interleave CI degenerate at 0.2",
          _approx(fr_i["ci95"]["lo"], 0.2) and _approx(fr_i["ci95"]["hi"], 0.2), str(fr_i["ci95"]))
    check("omission delta negative",
          _approx(cmps["interleave"]["metrics"]["omission"]["mean_delta"], -0.2))
    check("comparison has n_pairs", fr_i["n_pairs"] == 6)

    # missing metrics / missing arms must not explode
    partial = [
        {"idx": 0, "arms": {"batch": {"metrics": {"fact_recall": 1.0}, "pred_ir": {"timeline": [1]}}}},
        {"idx": 1, "arms": {"marked": {"metrics": {}, "pred_ir": {"timeline": []}}}},
        {"idx": 2, "arms": {}},
    ]
    agg2 = aggregate(partial, n_resamples=10, seed=0)
    check("partial aggregate survives", agg2["rows"]["batch"]["n"] == 1, str(agg2["rows"]))
    check("missing metric -> nan", not is_num(agg2["rows"]["marked"]["fact_recall"]))
    check("unpaired comparison n=0",
          agg2["comparisons"][0]["metrics"]["fact_recall"]["n_pairs"] == 0)
    check("empty aggregate", aggregate([], n_resamples=10)["rows"] == {})

    check("extra metrics detected", agg["extra_metrics"] == ["valid"], str(agg["extra_metrics"]))
    check("extra table renders", "valid" in format_extra_table(agg))
    check("no extras -> empty string", format_extra_table(aggregate([], n_resamples=1)) == "")
    check("driver valid beats scorer flag",
          valid_of({"valid": 0.0, "metrics": {"valid_json": True}}) == 0.0)
    check("scorer flag used when driver silent",
          valid_of({"metrics": {"valid_json": True}}) == 1.0)

    tbl = format_table(agg)
    check("table has header", "fact_recall" in tbl.splitlines()[0])
    check("table has 3 arm rows", len(tbl.splitlines()) == 2 + len(agg["rows"]), tbl)
    cmp_txt = format_comparisons(agg)
    check("comparison text", "interleave vs batch" in cmp_txt and "95% CI" in cmp_txt)
    check("format survives nan", "n/a" in format_table(agg2))

    print("[selftest] progress_line")
    line = progress_line(1, 10, {"idx": 3, "n_clauses": 2, "cmd": "테스트"}, synth[0]["arms"], 1.23)
    check("progress line", "idx=3" in line and "batc=0.50" in line, line)

    print()
    if fails:
        print("SELFTEST FAILED: %d check(s): %s" % (len(fails), fails))
        return 1
    print("SELFTEST OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
