"""Minimal OpenAI-compatible chat client for the local vLLM server.

The deployment target is a local sLLM (vLLM, tmux session `vllm`). The model
is a thinking model: replies carry a reasoning preamble ended by `</think>`,
which `chat()` strips. stdlib-only (urllib), no SDK dependency.
"""

from __future__ import annotations

import json
import os
import urllib.request

BASE = os.environ.get("JOI_LLM_BASE", "http://127.0.0.1:8002/v1")
MODEL = os.environ.get("JOI_LLM_MODEL", "cyankiwi/Qwen3.5-9B-AWQ-4bit")


def chat(prompt: str, system: str = "", max_tokens: int = 4096,
         temperature: float = 0.0, timeout: int = 180,
         thinking: bool = False) -> str:
    """thinking=False by default: structured tasks (delta JSON) want the
    direct answer; leaked reasoning has already been seen to quote format
    examples that poison JSON extraction."""
    msgs = ([{"role": "system", "content": system}] if system else []) \
        + [{"role": "user", "content": prompt}]
    body = json.dumps({"model": MODEL, "messages": msgs,
                       "max_tokens": max_tokens,
                       "temperature": temperature,
                       "chat_template_kwargs": {"enable_thinking": thinking}
                       }).encode()
    req = urllib.request.Request(f"{BASE}/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.load(r)
    text = out["choices"][0]["message"].get("content") or ""
    if "</think>" in text:
        text = text.split("</think>", 1)[1]
    return text.strip()


def chat_json(prompt: str, system: str = "", **kw) -> dict:
    """chat() then parse the LAST parseable JSON object in the reply.

    Last, not first: the model sometimes leaks its reasoning without the
    closing think tag, and the reasoning quotes half-formed JSON examples —
    the actual answer is the final object. Trailing commas are tolerated."""
    import re
    text = chat(prompt, system, **kw)
    objs = []
    depth, start = 0, -1
    for i, c in enumerate(text):
        if c == "{":
            if depth == 0:
                start = i
            depth += 1
        elif c == "}" and depth:
            depth -= 1
            if depth == 0:
                objs.append(text[start:i + 1])
    for raw in reversed(objs):
        if re.search(r"<[a-z][^>]*>", raw):
            continue        # a quoted format TEMPLATE, not an answer
        for candidate in (raw, re.sub(r",\s*([}\]])", r"\1", raw)):
            try:
                return json.loads(candidate)
            except ValueError:
                continue
    raise ValueError(f"no parseable JSON in reply: {text[:150]!r}")
