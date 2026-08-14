"""Phase 2: constraint extraction against the live vLLM server, with guided
decoding, measured on the Phase 1 gate cases.

Pipeline under test:
  command → [LLM: constraint groups, environment-blind, guided JSON]
          → [per-hint lexicon lookup over effects.json ∩ connected devices]
          → recovered category set  vs  expected category set

This exercises the REAL new architecture (per-hint matching), unlike the
Phase 1 gate which substring-matched the whole command.

Usage: /home/ikess/joi-llm/venv/bin/python extract_runner.py [-v]
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
from config import get_client, get_model_id  # noqa: E402

from gate_check import CASES, STOP, norm  # noqa: E402

SVCS = json.load(open(os.path.join(HERE, "effects.json")))["services"]
PROMPT = open(os.path.join(HERE, "constraint_extract_prompt.md")).read()

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
    return json.loads(resp.choices[0].message.content)


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


def resolve_groups(groups, connected_cats):
    """Union of per-group category candidates (device hint first, else effect)."""
    cats = set()
    for g in groups:
        got = match_hint(g.get("device_hint") or "", connected_cats)
        if not got:
            # no device mention → capability-only: cast a wider net; the join
            # engine narrows later via role/preference
            got = match_hint(g.get("effect_hint") or "", connected_cats, top_n=3)
        elif g.get("effect_hint") and g.get("device_hint"):
            # both sides present: effect side may pin the service family too
            got += match_hint(g["effect_hint"], connected_cats, top_n=1)
        cats.update(got)
    return cats


if __name__ == "__main__":
    import run as R  # 게이트 측정용 디바이스 페이로드 (하네스에서만 읽는다)
    CONNECTED = {c for d in R.CONNECTED_DEVICES.values() for c in d["category"]}
    verbose = "-v" in sys.argv
    tot = found = full = 0
    for cmd, exp in CASES:
        try:
            parsed = extract(cmd)
        except Exception as e:  # noqa: BLE001
            print(f"💥 {cmd} → extraction error: {e}")
            tot += len(exp)
            continue
        got = resolve_groups(parsed["groups"], CONNECTED)
        tot += len(exp)
        found += len(exp & got)
        ok = exp <= got
        full += ok
        mark = "✅" if ok else "❌"
        if verbose or not ok:
            print(f"{mark} {cmd}")
            for g in parsed["groups"]:
                print(f"     {g['role']:<9} dev={g['device_hint']!r} "
                      f"hard={g['device_hard']} eff={g['effect_hint']!r} "
                      f"q={g['quantifier']} args={g['args_text']!r}")
            print(f"     복원: {sorted(got)}  기대: {sorted(exp)}")
    print(f"\n카테고리 recall: {found}/{tot} ({found/tot:.0%}) | "
          f"케이스 완전충족: {full}/{len(CASES)}")
