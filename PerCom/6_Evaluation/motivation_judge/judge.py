#!/usr/bin/env python3
"""Fig2/Table1 — ask an LLM judge whether a program implements the command; base and rewrite
are judged in separate calls, and the base is judged again (identity repeats) with the same
prompt so verdict variation without any rewrite is measured with the same rule.

Usage:
  python judge.py --judge qwen     # local vLLM on :8002 (Qwen3.5-9B-fp8), thinking off, temp 0
  python judge.py --judge gpt      # gpt-5.4-mini via OpenAI (key: ~/openai.txt or OPENAI_API_KEY)
Responses are cached under runs/<judge>/responses/<sha>_<rep>.json; rerunning resumes.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

JUDGES = {
    "qwen": {"backend": "vllm", "base_url": "http://localhost:8002/v1", "model": None,
             "temperature": 0.0, "seed": 0, "max_tokens": 1500, "answer_tokens": 300, "thinking": False},
    "gpt": {"backend": "openai", "model": "gpt-5.4-mini-2026-03-17", "reasoning_effort": "low",
            "seed": 42, "max_tokens": 4096},
    "claude": {"backend": "anthropic", "model": "claude-sonnet-5", "effort": "low", "max_tokens": 4096},
}
IDENTITY_REPEATS = 2   # base is judged 1 + IDENTITY_REPEATS times; rep 0 is the base verdict

# Budget forcing (same idea as joi/self_feedback/repair_core.py): a run that spends the whole
# reasoning budget is continued once from where it stopped, with the model told to commit, so a
# truncated call yields a verdict instead of an unparsed row. Reported output tokens are the sum
# of both calls, and `forced` records that it happened.
FORCE_TAIL = ('\n\nI have used my reasoning budget. I will now commit to a verdict and write the '
              'final JSON answer.\n\n{"correct":')

JOI_REF = """A JoI program is a small home-automation script: {"cron", "period", "script"}.
- The runtime runs the whole `script` once; if `period` (milliseconds) is nonzero, it waits `period`
  after the script finishes and runs it again, forever, until a `break`. `period` 0 means run once.
  `cron` (e.g. "0 19 * * *") starts the program at that wall-clock time.
- `x := v` declares a persistent variable: the initializer runs only on the first run; later runs
  skip that line and keep the previous value. `x = v` is a plain assignment that runs every time.
- Device read:   (#Tag).service_attribute      e.g. (#Kitchen_Light).light_brightness
- Device action: (#Tag).service_method(args)   e.g. (#Kitchen_Light).switch_on()
- `all(#Type)` addresses every device of that type; `any(#Type)` may appear only inside a condition.
- Comparing a value read from several devices: `all(#X).attr ==| v` and `any(#X).attr == v` both
  mean "at least one of the devices satisfies it"; the same holds for !=| <| >| <=| >=|.
  `all(#X).attr == v` (no bar) means every device satisfies it.
- `if (cond) { ... } else { ... }`, `and`, `or`, `not (...)`.
- `wait until(cond)` blocks until the condition holds, watching inputs continuously.
- `delay(N UNIT)` waits a fixed time; UNIT is MSEC, SEC, MIN or HOUR.
- `break` stops the periodic re-runs.
Judge by behavior: the device actions the program produces, on which devices, with which arguments,
in which order and at which times, under every relevant input situation. Timing differences of
less than 500 ms are not errors. "Turn on" may be switch_on() or moveToBrightness(B>0);
"turn off" may be switch_off() or moveToBrightness(0). Omitting a default argument (Rate=0) is not an error."""


def prompt_for(command, block):
    return ("# ROLE\nYou are reviewing an automatically generated home-automation program before it is deployed. "
            "Decide whether the JoI program correctly implements the user's command.\n"
            "CORRECT iff, under every relevant situation over time, the program performs exactly the device "
            "actions the command asks for: right triggers, right conditions, right timing, no missing or extra actions.\n\n"
            "# JoI LANGUAGE REFERENCE\n" + JOI_REF + "\n\n"
            "# JUDGE THIS ONE\nUSER COMMAND: " + command + "\n"
            "PROGRAM: " + json.dumps(block, ensure_ascii=False) + "\n\n"
            "# TASK\nReason step by step about the program's behavior over time (triggers, conditions, branches, "
            "timing, repeated runs). Then output ONLY a JSON object on the last line:\n"
            '{"correct": true|false, "problem": "<what is wrong, or none>"}\n')


def parse_verdict(text):
    s = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    m = re.findall(r'"correct"\s*:\s*(true|false)', s, re.I)
    return (m[-1].lower() == "true") if m else None


_CLIENTS = {}
_LOCK = threading.Lock()
# OpenAI keys are tried in order; when one runs out of credit the next one takes over.
KEY_FILES = [os.path.expanduser("~/openai.txt"), os.path.expanduser("~/openai2.txt")]
ANTHROPIC_KEY_FILE = os.path.expanduser("~/claude_api.txt")
_KEY_IDX = 0
OUT_OF_CREDIT = ("insufficient_quota", "exceeded your current quota", "billing_hard_limit_reached",
                 "account_deactivated")


def _openai_client(idx):
    from openai import OpenAI
    key = os.environ.get("OPENAI_API_KEY", "").strip() if idx == 0 else ""
    if not key:
        if idx >= len(KEY_FILES) or not os.path.exists(KEY_FILES[idx]):
            raise RuntimeError(f"no OpenAI key left (tried {idx + 1})")
        key = open(KEY_FILES[idx]).read().strip()
    return OpenAI(api_key=key)


def _rotate_key(bad_idx):
    """Move to the next key file; returns the new index, or raises when none is left."""
    global _KEY_IDX
    with _LOCK:
        if _KEY_IDX == bad_idx:
            _KEY_IDX = bad_idx + 1
            _CLIENTS.pop("gpt", None)
            src = KEY_FILES[_KEY_IDX] if _KEY_IDX < len(KEY_FILES) else "(none)"
            print(f"  [key] key {bad_idx} is out of credit -> switching to {src}", flush=True)
        return _KEY_IDX


def call(judge, prompt):
    cfg = JUDGES[judge]
    from openai import OpenAI
    with _LOCK:
        if judge not in _CLIENTS:
            if cfg["backend"] == "vllm":
                c = OpenAI(api_key="EMPTY", base_url=cfg["base_url"])
                cfg["model"] = cfg["model"] or c.models.list().data[0].id
            elif cfg["backend"] == "anthropic":
                import anthropic
                key = os.environ.get("ANTHROPIC_API_KEY", "").strip() or open(ANTHROPIC_KEY_FILE).read().strip()
                c = anthropic.Anthropic(api_key=key)
            else:
                c = _openai_client(_KEY_IDX)
            _CLIENTS[judge] = c
        c, key_idx = _CLIENTS[judge], _KEY_IDX
    t0 = time.time()
    msgs = [{"role": "user", "content": prompt}]
    if cfg["backend"] == "vllm":
        kw = dict(model=cfg["model"], messages=msgs, temperature=cfg["temperature"],
                  seed=cfg["seed"], max_tokens=cfg["max_tokens"],
                  extra_body={"chat_template_kwargs": {"enable_thinking": cfg["thinking"]}})
        r = c.chat.completions.create(**kw)
        m = r.choices[0].message
        content = m.content or ""
        out = {"content": content, "finish": r.choices[0].finish_reason, "key_idx": 0, "forced": False,
               "usage": r.usage.model_dump() if r.usage else {}, "seconds": time.time() - t0, "model": r.model}
        if r.choices[0].finish_reason == "length" and content:
            partial = content + FORCE_TAIL
            kw2 = dict(kw, messages=msgs + [{"role": "assistant", "content": partial}],
                       max_tokens=cfg["answer_tokens"],
                       extra_body={"chat_template_kwargs": {"enable_thinking": cfg["thinking"]},
                                   "continue_final_message": True, "add_generation_prompt": False})
            r2 = c.chat.completions.create(**kw2)
            tail = r2.choices[0].message.content or ""
            u1, u2 = out["usage"], (r2.usage.model_dump() if r2.usage else {})
            out.update(content=partial + tail, finish=r2.choices[0].finish_reason, forced=True,
                       usage={"prompt_tokens": u1.get("prompt_tokens", 0),
                              # actual generated tokens: budget spent + continuation
                              "completion_tokens": u1.get("completion_tokens", 0) + u2.get("completion_tokens", 0),
                              "completion_tokens_budget": u1.get("completion_tokens", 0),
                              "completion_tokens_answer": u2.get("completion_tokens", 0)},
                       usage_continuation=u2, seconds=time.time() - t0)
        return out
    elif cfg["backend"] == "anthropic":
        import anthropic
        for attempt in range(6):
            try:
                r = c.messages.create(model=cfg["model"], max_tokens=cfg["max_tokens"],
                                      thinking={"type": "adaptive"},
                                      output_config={"effort": cfg["effort"]},
                                      messages=msgs)
                break
            except (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.APITimeoutError):
                if attempt == 5:
                    raise
                time.sleep(2 * (attempt + 1))
            except anthropic.APIStatusError as e:
                if e.status_code >= 500 and attempt < 5:
                    time.sleep(2 * (attempt + 1)); continue
                raise
        text = "".join(b.text for b in r.content if b.type == "text")
        u = r.usage
        return {"content": text, "finish": r.stop_reason, "key_idx": 0,
                "usage": {"prompt_tokens": u.input_tokens, "completion_tokens": u.output_tokens,
                          "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0)},
                "seconds": time.time() - t0, "model": r.model}
    else:
        for attempt in range(6):
            try:
                r = c.chat.completions.create(model=cfg["model"], messages=msgs, seed=cfg["seed"],
                                              max_completion_tokens=cfg["max_tokens"],
                                              reasoning_effort=cfg["reasoning_effort"])
                break
            except Exception as e:
                text = str(e)
                if any(k in text for k in OUT_OF_CREDIT):
                    key_idx = _rotate_key(key_idx)
                    c = _CLIENTS.setdefault(judge, _openai_client(key_idx))
                    continue
                if attempt == 5 or not any(k in text for k in ("rate_limit", "Timeout", "timeout", "502", "503", "529")):
                    raise
                time.sleep(2 * (attempt + 1))
    m = r.choices[0].message
    return {"content": m.content or "", "finish": r.choices[0].finish_reason, "key_idx": key_idx,
            "usage": r.usage.model_dump() if r.usage else {}, "seconds": time.time() - t0, "model": r.model}


def sha(block):
    return hashlib.sha256(json.dumps(block, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", choices=list(JUDGES), required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0, help="only the first N seeds (smoke test)")
    a = ap.parse_args()
    pairs = json.load(open(os.path.join(HERE, "rewrites", "verified_pairs.json")))["pairs"]
    out_dir = os.path.join(HERE, "runs", a.judge)
    resp_dir = os.path.join(out_dir, "responses")
    os.makedirs(resp_dir, exist_ok=True)

    # every distinct program to judge: (program sha, rep) -> (command, block, role)
    jobs = {}
    seeds = sorted({p["id"] for p in pairs})
    if a.limit:
        seeds = seeds[:a.limit]
    for p in pairs:
        if p["id"] not in seeds:
            continue
        for rep in range(1 + IDENTITY_REPEATS):
            jobs[(sha(p["base"]), rep)] = (p["command"], p["base"])
        jobs[(sha(p["variant"]), 0)] = (p["command"], p["variant"])
    todo = [(k, v) for k, v in jobs.items() if not os.path.exists(os.path.join(resp_dir, f"{k[0]}_{k[1]}.json"))]
    print(f"{a.judge}: {len(jobs)} calls, {len(todo)} to do", flush=True)

    def work(item):
        (h, rep), (command, block) = item
        prompt = prompt_for(command, block)
        try:
            r = call(a.judge, prompt)
            r["verdict"] = parse_verdict(r["content"])
            r["status"] = "ok" if r["verdict"] is not None else "unparsed"
        except Exception as e:
            r = {"status": "error", "error": f"{type(e).__name__}: {e}", "verdict": None}
        r.update(sha=h, rep=rep, prompt_sha=hashlib.sha256(prompt.encode()).hexdigest()[:16])
        json.dump(r, open(os.path.join(resp_dir, f"{h}_{rep}.json"), "w"), ensure_ascii=False, indent=1)
        return r["status"]

    done = 0
    t0 = time.time()
    with ThreadPoolExecutor(a.workers) as ex:
        for st in ex.map(work, todo):
            done += 1
            if done % 25 == 0 or done == len(todo):
                print(f"  {done}/{len(todo)} ({time.time() - t0:.0f}s) last={st}", flush=True)

    # assemble verdict rows
    rows = []
    for p in pairs:
        if p["id"] not in seeds:
            continue
        def load(h, rep):
            f = os.path.join(resp_dir, f"{h}_{rep}.json")
            return json.load(open(f)) if os.path.exists(f) else {"verdict": None, "status": "missing"}
        b = [load(sha(p["base"]), r) for r in range(1 + IDENTITY_REPEATS)]
        v = load(sha(p["variant"]), 0)
        rows.append({"id": p["id"], "type": p["type"], "band": p["band"],
                     "base": [x["verdict"] for x in b], "base_status": [x["status"] for x in b],
                     "variant": v["verdict"], "variant_status": v["status"]})
    meta = {"judge": a.judge, "config": JUDGES[a.judge], "identity_repeats": IDENTITY_REPEATS,
            "prompt_reference_sha": hashlib.sha256(JOI_REF.encode()).hexdigest()[:16],
            "pairs": len(rows), "seeds": len(seeds), "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    json.dump({"meta": meta, "rows": rows}, open(os.path.join(out_dir, "verdicts.json"), "w"), ensure_ascii=False, indent=1)
    print(json.dumps(meta, ensure_ascii=False))


if __name__ == "__main__":
    main()
