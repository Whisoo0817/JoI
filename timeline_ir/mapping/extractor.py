"""Extract mapping constraints from a command with guided decoding.

Pipeline:
  command → [LLM: constraint groups, environment-blind, guided JSON]
          → [per-hint lexicon lookup over effects.json ∩ connected devices]
          → recovered category set
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(HERE))
from ..config import get_client, get_model_id

STOP = {"알려줘", "알려", "말해줘", "해줘", "해서", "보여줘", "보내줘",
        "켜줘", "꺼줘", "시작", "설정", "확인해줘", "줘"}


def norm(s):
    return re.sub(r"[^\w가-힣]", "", s.lower())

SVCS = json.load(open(os.path.join(HERE, "effects.json")))["services"]
PROMPT = open(os.path.join(PROJECT_ROOT, "files", "mapping",
                           "constraint_extract.md"), encoding="utf-8").read()

SCHEMA = {
    "type": "object",
    "properties": {
        "groups": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "role": {"enum": ["condition", "action", "read", "notify"]},
                    "device_hint": {"type": ["string", "null"]},
                    "device_hard": {"type": "boolean"},
                    "effect_hint": {"type": ["string", "null"]},
                    "quantifier": {"enum": ["all", "any", "one", None]},
                    "args_text": {"type": ["string", "null"]},
                },
                "required": ["role", "device_hint", "device_hard",
                             "effect_hint", "quantifier", "args_text"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["groups"],
    "additionalProperties": False,
}

# 클라이언트는 지연 초기화 — import 시점에 서버를 건드리지 않는다 (서버 없이
# 오프라인 도구가 이 모듈을 import 할 수 있어야 함). 파이프라인은 자신의
# client/base_url을 set_client()로 주입한다 (run_local_ir.py의 base_url 전파).
client = None
MODEL = None


def set_client(c, model=None):
    global client, MODEL
    client = c
    MODEL = model or get_model_id(c)


def ensure_client():
    global client, MODEL
    if client is None:
        client = get_client()
        MODEL = get_model_id(client)
    return client


def parse_response_json(raw: str) -> dict:
    """Accept a JSON object with optional model-added Markdown fencing."""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, count=1,
                      flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text, count=1)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        if start < 0:
            raise
        parsed, _ = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(parsed, dict):
        raise ValueError("constraint extraction response must be a JSON object")
    return parsed


def extract(command: str) -> dict:
    ensure_client()
    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        max_tokens=768,
        messages=[{"role": "system", "content": PROMPT},
                  {"role": "user", "content": f"[Command] {command}"}],
        extra_body={"guided_json": SCHEMA,
                    # thinking burns the token budget before any content is
                    # emitted (server runs a reasoning parser) — disable it,
                    # same as the production pipeline (pipeline_helpers.py:28)
                    "chat_template_kwargs": {"enable_thinking": False}},
    )
    return parse_response_json(resp.choices[0].message.content)


def match_hint(text: str, connected_cats, top_n: int = 2):
    """Rank connected categories for ONE hint span (not the whole command).

    `connected_cats` comes from the request's own payload — the caller's devices,
    never a fixed harness dump, so this works unchanged behind the live API.
    """
    if not text:
        return []
    scores, tn_cmd = {}, norm(text)
    stop_n = {norm(x) for x in STOP}
    for s in SVCS:
        cat = s["svc"].split(".")[0]
        if cat not in connected_cats:
            continue
        best = 0
        for trig in s.get("ko_triggers", []):
            tn = norm(trig)
            if not tn:
                continue
            if tn in tn_cmd or tn_cmd in tn:
                best = max(best, min(len(tn), len(tn_cmd)) * 2)
            else:
                toks = [t for t in re.split(r"\s+", trig)
                        if len(norm(t)) >= 2 and norm(t) not in stop_n]
                best = max(best, sum(len(norm(t)) for t in toks if norm(t) in tn_cmd))
        if best > 0 and best > scores.get(cat, 0):
            scores[cat] = best
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    return [c for c, _ in ranked[:top_n]]
