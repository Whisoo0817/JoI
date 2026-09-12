"""Generate JoI candidates for the motivation pilot.

Conditions (binding plan = [Precision Selectors] is given in every condition):
  NL    command only + JoI language reference
  SPEC  command + explicit behavior contract + JoI language reference
  IR    command + confirmed Timeline IR + the production VETS lowering prompt
        (joi_common.md + joi_<bucket>.md), unchanged

Models:
  qwen9b        cyankiwi/Qwen3.5-9B-AWQ-4bit on local vLLM, thinking off,
                temperature 0.7 / top_p 0.8 / top_k 20 (Qwen non-thinking recommendation)
  qwen9b_think  same model, thinking on (CoT), temperature 0.6 / top_p 0.95 / top_k 20
  gpt54mini     gpt-5.4-mini-2026-03-17 via OpenAI API, reasoning_effort=medium (key: OPENAI_API_KEY, joi/openai.txt or ~/openai.txt)

python generate.py --model qwen9b [--samples 3] [--conditions NL SPEC IR] [--tasks T01 ...]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from timeline_ir.loader import PROMPTS, SERVICE_DATA  # noqa: E402
from timeline_ir.pipeline_helpers import extract_service_details  # noqa: E402
from timeline_ir.feasibility import lowering_bucket  # noqa: E402
from tasks import TASKS  # noqa: E402

REFERENCE = (HERE / "prompts" / "joi_reference.md").read_text()
MODELS = {
    "qwen9b": dict(kind="vllm", model="cyankiwi/Qwen3.5-9B-AWQ-4bit", base_url="http://localhost:8002/v1",
                   enable_thinking=False, temperature=0.7, top_p=0.8, top_k=20, max_tokens=2000, workers=8),
    "qwen9b_think": dict(kind="vllm", model="cyankiwi/Qwen3.5-9B-AWQ-4bit", base_url="http://localhost:8002/v1",
                         enable_thinking=True, temperature=0.6, top_p=0.95, top_k=20, max_tokens=23000, workers=8),
    "gpt54mini": dict(kind="openai", model="gpt-5.4-mini-2026-03-17", reasoning_effort="medium", max_completion_tokens=16000, workers=6),
}


def precision_block(task) -> str:
    return "\n".join(f"{k}: {v}" for k, v in task["selectors"].items())


def service_block(task) -> str:
    return json.dumps(extract_service_details(task["services"], SERVICE_DATA), indent=2, ensure_ascii=False)


def build_messages(task, condition: str) -> list[dict]:
    if condition == "IR":
        bucket = lowering_bucket(task["ir"])
        system = PROMPTS["joi_common"] + "\n\n---\n\n" + PROMPTS[f"joi_{bucket}"]
        user = (f"[Command]\n{task['command']}\n\n"
                f"[Timeline IR]\n{json.dumps(task['ir'], ensure_ascii=False)}\n\n"
                f"[Precision Selectors]\n{precision_block(task)}\n\n"
                f"[Service Details]\n{service_block(task)}")
    else:
        system = REFERENCE
        spec = f"[Behavior Specification]\n{task['spec']}\n\n" if condition == "SPEC" else ""
        user = (f"[Command]\n{task['command']}\n\n{spec}"
                f"[Precision Selectors]\n{precision_block(task)}\n\n"
                f"[Service Details]\n{service_block(task)}")
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def openai_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    for path in (ROOT / "openai.txt", Path.home() / "openai.txt"):
        if not key and path.exists():
            key = path.read_text().strip()
    if not key:
        sys.exit("No OpenAI key: set OPENAI_API_KEY or create joi/openai.txt (gitignored).")
    return key


def call_model(cfg, messages, seed):
    from openai import OpenAI
    t0 = time.perf_counter()
    if cfg["kind"] == "vllm":
        client = OpenAI(api_key="EMPTY", base_url=cfg["base_url"])
        resp = client.chat.completions.create(
            model=cfg["model"], messages=messages, temperature=cfg["temperature"], top_p=cfg["top_p"],
            max_tokens=cfg["max_tokens"], seed=seed,
            extra_body={"top_k": cfg["top_k"], "chat_template_kwargs": {"enable_thinking": cfg["enable_thinking"]}})
    else:
        client = OpenAI(api_key=openai_key())
        resp = client.chat.completions.create(
            model=cfg["model"], messages=messages, reasoning_effort=cfg["reasoning_effort"],
            max_completion_tokens=cfg["max_completion_tokens"])
    choice = resp.choices[0]
    usage = resp.usage.model_dump() if resp.usage else {}
    reasoning = getattr(choice.message, "reasoning_content", None) or getattr(choice.message, "reasoning", None)
    return {"raw": choice.message.content or "", "reasoning": reasoning, "finish_reason": choice.finish_reason,
            "usage": usage, "seconds": round(time.perf_counter() - t0, 2),
            "response_model": getattr(resp, "model", cfg["model"])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, choices=sorted(MODELS))
    ap.add_argument("--samples", type=int, default=3)
    ap.add_argument("--conditions", nargs="+", default=["NL", "SPEC", "IR"])
    ap.add_argument("--tasks", nargs="*")
    ap.add_argument("--out", default=str(HERE / "runs" / "generations"))
    args = ap.parse_args()
    cfg = MODELS[args.model]
    tasks = [t for t in TASKS if not args.tasks or t["id"] in args.tasks]
    out_dir = Path(args.out) / args.model
    jobs = []
    for task in tasks:
        for cond in args.conditions:
            for s in range(1, args.samples + 1):
                path = out_dir / cond / f"{task['id']}_s{s}.json"
                if path.exists():
                    continue
                jobs.append((task, cond, s, path))
    print(f"{len(jobs)} generations to run for {args.model}")

    def work(job):
        task, cond, s, path = job
        messages = build_messages(task, cond)
        rec = {"task": task["id"], "condition": cond, "sample": s, "model_key": args.model,
               "config": {k: v for k, v in cfg.items() if k != "workers"},
               "prompt_sha256": hashlib.sha256(json.dumps(messages).encode()).hexdigest(),
               "messages": messages}
        try:
            rec.update(call_model(cfg, messages, seed=s))
        except Exception as e:
            rec.update(raw=None, error=f"{type(e).__name__}: {e}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rec, ensure_ascii=False, indent=1))
        return f"{task['id']} {cond} s{s} {rec.get('seconds', '-')}s {rec.get('finish_reason', rec.get('error', ''))}"

    with ThreadPoolExecutor(cfg["workers"]) as ex:
        for fut in as_completed([ex.submit(work, j) for j in jobs]):
            print(fut.result(), flush=True)


if __name__ == "__main__":
    main()
