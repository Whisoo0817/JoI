"""JoI generation pipeline: Korean command → Timeline IR (joi_slm) → JoI code.

One model (engine.py, in-process vLLM, default Qwen3.5-2B-AWQ) does everything:
word states for the sLM heads, the MCQ gates, lowering and naming.

    [Stage 0] (optional) feedback edit: current_code → NL (re_translate) → feedback_edit
    [Stage 1] command → Timeline IR : joi_slm.CommandToIR
              2B word states + linear heads (clause boundary / type / mods, graph),
              embedding service mapping joined on connected categories, rule assembly.
              No LLM text generation; approval-free — the IR is used as built.
    [Stage 2] IR services × connected devices → selectors (joi/devices.py, Python)
    [Stage 3] feasibility → lowering → 게이트
              기본: LLM 없이 규칙으로 IR 을 코드로 옮기고(joi/lower_rules.py),
              게이트(joi/gate)가 IR 과 코드를 나란히 돌려 같은지 확인한다.
              같을 때(EQUIV)만 내보내고, 규칙 밖 모양·DIVERGE·REFUSED 는
              폴백 없이 거절한다. 옛 LLM lowering 은 JOI_LOWER=llm 로만 켠다
              (기준선 측정용; 이때 게이트는 판정만 기록하고 거르지 않는다).
    [Stage 4] naming: re_translate → re_translate_kor → scenario_name (same model)
              — 지금은 기본으로 건너뛴다. 켜려면 JOI_NAME=1.

Every stage's product is kept on the result (`ir`, `segments`, `precision`, ...)
so a failure can be traced to the stage that produced it.
Post-processing helpers live in pipeline_helpers.py.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time

from engine import get_engine, MODEL_ID
from loader import SERVICE_DATA, PROMPTS
from parser.validator import validate_joi

from pipeline_helpers import (
    JoiGenerationError,
    run_llm_inference,
    extract_service_details,
    _SERVICE_CATEGORY_MAP,
    _apply_service_prefix,
    _normalize_script_newlines,
    _post_process_joi_any_quantifiers,
    _reapply_precision_quantifiers,
    _strip_selector_extra_parens,
    _parse_dict_input,
)
from joi.feasibility import check_feasibility, FeasibilityError, lowering_bucket
from joi.devices import build_selectors, render_selectors, MissingDevices
from joi.lower_rules import lower_ir, CantLower
from joi.gate import gate_row

# lowering 방식: "rules"(기본) | "llm"(옛 LLM lowering, 기준선 측정용)
LOWER_MODE = os.environ.get("JOI_LOWER", "rules").strip().lower() or "rules"


# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 backend — joi_slm on the single in-process engine (engine.py):
# the same 2B model gives the word states (layer hooks), the low-confidence
# MCQ gates, and — below — lowering and naming. Built once per process.
# ─────────────────────────────────────────────────────────────────────────────
_SLM = {"pipe": None}
_SLM_LOCK = threading.Lock()


def _slm_pipe():
    """Return the process-wide CommandToIR (built on first use)."""
    from joi_slm import CommandToIR
    with _SLM_LOCK:
        if _SLM["pipe"] is None:
            gates = os.environ.get("JOI_SLM_GATES", "1") != "0"
            _SLM["pipe"] = CommandToIR(engine=get_engine(), gates=gates)
    return _SLM["pipe"]


def command_to_ir(sentence: str, connected_devices: dict) -> dict:
    """Stage 1 alone: → {"ir", "segments", "mapping", "graph"} (for tools/tests)."""
    return _slm_pipe()(sentence, connected_devices)


# ─────────────────────────────────────────────────────────────────────────────
# Lowering prompt routing
# ─────────────────────────────────────────────────────────────────────────────
# Two buckets only: the IR is either acyclic (sequence) or contains a top-level
# cycle. Within `cycle`, joi_cycle.md's own switchboard picks the idiom from
# explicit IR signals — no Python heuristic.
_BUCKET_KEYS = ("noncycle", "cycle")


def classify_ir(ir):
    """Routing key for example routing: 'cycle' if a top-level cycle op exists,
    else 'noncycle' (feasibility.lowering_bucket)."""
    return lowering_bucket(ir)


def _load_lowering_prompt(bucket: str, ir=None) -> str:
    """joi_common.md + the example block routed by the IR's structural class."""
    if bucket not in _BUCKET_KEYS:
        raise ValueError(f"unknown lowering bucket: {bucket!r}")
    common = PROMPTS.get("joi_common")
    if not common:
        raise FileNotFoundError("joi_common.md not loaded by PROMPTS")
    if ir is not None:
        try:
            from joi import examples
            return common + "\n\n---\n\n" + examples.examples_for(ir, PROMPTS)
        except ImportError:
            pass
    bucket_md = PROMPTS.get(f"joi_{bucket}")
    if not bucket_md:
        raise FileNotFoundError(f"joi_{bucket}.md not loaded by PROMPTS")
    return common + "\n\n---\n\n" + bucket_md


# ─────────────────────────────────────────────────────────────────────────────
# Pure helpers
# ─────────────────────────────────────────────────────────────────────────────
def _extract_reasoning(raw: str) -> str:
    """Pull <Reasoning>...</Reasoning> content (best-effort)."""
    m = re.search(r'<Reasoning>(.*?)</Reasoning>', raw, flags=re.DOTALL)
    return m.group(1).strip() if m else ""


# IR durations use the same mini-grammar as JoI's `delay(N UNIT)`: '<int> <HOUR|MIN|SEC|MSEC>'.
_DURATION_UNIT_MS = {"HOUR": 3_600_000, "MIN": 60_000, "SEC": 1_000, "MSEC": 1}
_DURATION_RE = re.compile(r"^(\d+)\s+(HOUR|MIN|SEC|MSEC)$")


def parse_duration_to_ms(s: str) -> int:
    if not isinstance(s, str):
        raise ValueError(f"duration must be a string, got {type(s).__name__}")
    m = _DURATION_RE.match(s.strip())
    if not m:
        raise ValueError(f"malformed duration {s!r}; expected '<int> <HOUR|MIN|SEC|MSEC>'")
    return int(m.group(1)) * _DURATION_UNIT_MS[m.group(2)]


def _wrapper_period_from_ir(ir_obj):
    """Deterministic wrapper.period from IR.cycle.period (the LLM is unreliable
    at unit arithmetic). A cycle whose body waits on a rising edge polls at 1 SEC
    regardless of period. None if the IR has no top-level cycle."""
    for s in (ir_obj or {}).get("timeline", []):
        if isinstance(s, dict) and s.get("op") == "cycle":
            body = s.get("body") or []
            if any(isinstance(x, dict) and x.get("op") == "wait" and x.get("edge") == "rising"
                   for x in body):
                return 1000
            p = s.get("period")
            if isinstance(p, str):
                try:
                    return parse_duration_to_ms(p)
                except ValueError:
                    return None
            return None
    return None


def _normalize_edit_code(raw) -> str:
    """Normalize a client-supplied JoI code block into the `{cron,period,script}`
    JSON shape the re_translate prompt expects (dict / JSON string / bare script)."""
    obj = raw
    if isinstance(raw, str):
        try:
            obj = json.loads(raw.strip(), strict=False)
        except Exception:
            obj = None
        if not isinstance(obj, dict):
            return json.dumps({"cron": "", "period": 0, "script": raw.strip()},
                              ensure_ascii=False)
    if isinstance(obj, dict):
        return json.dumps({
            "cron": str(obj.get("cron", "")),
            "period": obj.get("period", 0),
            "script": obj.get("script", obj.get("code", "")),
        }, ensure_ascii=False)
    return json.dumps({"cron": "", "period": 0, "script": str(raw)}, ensure_ascii=False)


def _unescape_script(code_json: str) -> str:
    return re.sub(
        r'("script"\s*:\s*")(.*?)(")',
        lambda m: m.group(1) + m.group(2).replace('\\n', '\n') + m.group(3),
        code_json, count=1, flags=re.DOTALL,
    )


def _duration_hints(code_obj) -> str:
    """Sustained-state tick thresholds (`*_ticks >= N`) × period → real seconds,
    computed here so re_translate never does the arithmetic."""
    try:
        period = int(code_obj.get("period") or 0)
        script = code_obj.get("script") or ""
    except Exception:
        return ""
    if period <= 0:
        return ""

    def _fmt(sec: float) -> str:
        if sec < 1:
            return f"{sec:g} seconds"
        sec = int(round(sec))
        if sec % 3600 == 0:
            h = sec // 3600
            return f"{h} hour" + ("s" if h != 1 else "")
        if sec % 60 == 0:
            m = sec // 60
            return f"{m} minute" + ("s" if m != 1 else "")
        return f"{sec} second" + ("s" if sec != 1 else "")
    seen = []
    for m in re.finditer(r'\b(\w*ticks)\b\s*>=\s*(\d+)', script):
        n = int(m.group(2))
        if n <= 1:
            continue
        line = f"- threshold {n} at period {period}ms = {_fmt(n * period / 1000.0)}"
        if line not in seen:
            seen.append(line)
    if not seen:
        return ""
    return "\n\n[Duration Hints] (already computed — use verbatim, do NOT recompute)\n" + "\n".join(seen)


# 고치기 라운드의 시스템 프롬프트 꼬리: 예문 은행은 빼고(2B 가 예문을 베껴 새로 짜 버림) 문법 + 할 일만
_FIX_TAIL = """

---

## Fixing mode
You are given a DRAFT JoI block and GATE FEEDBACK that says how the draft's behavior
differs from the Timeline IR. Do NOT rewrite the program from scratch. Keep the draft's
structure, period and cron; change only the lines needed so the behavior matches the IR.
Use only the selectors listed in [Precision Selectors]. Output exactly one JSON object
{"cron": ..., "period": ..., "script": ...} and nothing else."""


def _lower_by_llm(ir, sentence, selection, service_details, connected_devices, infer, log_buf,
                  extra="", fix=False):
    """LLM lowering. (joi_json, code_plan) 을 돌려준다.
    extra: 입력 끝에 덧붙일 글 — 규칙이 만든 초안 코드 + 게이트 피드백(고치기 라운드에서 씀).
    fix: 고치기 모드 — 예문 은행 없이 문법(joi_common) + 고치기 지시만 시스템 프롬프트로."""
    precision_output = {"selectors": selection["selectors"]}
    ir_json_str = json.dumps(ir, ensure_ascii=False, indent=2)
    bucket = classify_ir(ir)
    log_buf.append(f"📦 IR bucket: {bucket}")
    prompt_key = f"joi_from_ir_{bucket}"
    try:
        if fix:
            common = PROMPTS.get("joi_common")
            if not common:
                raise FileNotFoundError("joi_common.md not loaded by PROMPTS")
            system_prompt = common + _FIX_TAIL
        else:
            system_prompt = _load_lowering_prompt(bucket, ir=ir)
    except FileNotFoundError as e:
        raise JoiGenerationError(f"Lowering prompt missing: {e}", "\n".join(log_buf),
                                 error_code="missing_lowering_prompt")

    joi_input = (
        f"[Command]\n{sentence}\n\n"
        f"[Timeline IR]\n{ir_json_str}\n\n"
        f"[Precision Selectors]\n{render_selectors(precision_output['selectors'])}\n\n"
        f"[Service Details]\n{json.dumps(service_details, indent=2, ensure_ascii=False)}"
        + (("\n\n" + extra) if extra else "")
    )

    def _finalize(raw: str) -> dict:
        """Parse + post-process raw LLM output into the final joi_block dict."""
        script = re.sub(r'<Reasoning>.*?</Reasoning>', '', raw, flags=re.DOTALL).strip()
        joi_json = {}
        try:
            m = re.search(r'"script"\s*:\s*"(.*?)"\s*\}', script, re.DOTALL)
            if m:
                fixed_inner = m.group(1).replace('\n', '\\n')
                script = script[:m.start(1)] + fixed_inner + script[m.end(1):]
            joi_json = json.loads(script)
            if "script" in joi_json:
                joi_json["script"] = _strip_selector_extra_parens(joi_json["script"])
                joi_json["script"] = _apply_service_prefix(joi_json["script"])
                joi_json["script"] = _normalize_script_newlines(joi_json["script"])
            joi_json.setdefault("name", "Scenario")  # overwritten by naming stage below
            joi_json = {"name": joi_json.pop("name"), **joi_json}
        except (json.JSONDecodeError, TypeError):
            body = _apply_service_prefix(_strip_selector_extra_parens(script))
            joi_json = {"name": "Scenario", "cron": "", "period": 0,
                        "script": _normalize_script_newlines(body)}

        try:
            _ = validate_joi(joi_json.get("script", ""), connected_devices, _SERVICE_CATEGORY_MAP)
        except Exception as e:
            log_buf.append(f"⚠️ validate_joi warning: {e}")

        _override_ms = _wrapper_period_from_ir(ir)
        if _override_ms is not None and joi_json.get("period") != _override_ms:
            log_buf.append(f"🔧 wrapper.period override: {joi_json.get('period')} → {_override_ms} (from IR cycle.period)")
            joi_json["period"] = _override_ms

        if "script" in joi_json:
            # Re-apply any/all the lowering LLM may have dropped, THEN canonicalize
            # `any(...) ==` → `all(...) ==|`.
            joi_json["script"] = _reapply_precision_quantifiers(joi_json["script"], precision_output["selectors"])
            joi_json["script"] = _post_process_joi_any_quantifiers(joi_json["script"])
        return joi_json

    raw = infer(prompt_key, joi_input, system=system_prompt)
    joi_json = _finalize(raw)
    code_plan = _extract_reasoning(raw)  # lowering's control-flow notes for re_translate
    return joi_json, code_plan


# 규칙 lowering 이 게이트 밖이면 LLM 에게 고치게 하는 라운드 수(0 = 안 함). 2B 한 번에 ~3초.
LLM_FIX_ROUNDS = int(os.environ.get("JOI_LLM_FIX", "2"))
# 피드백 세기: verdict(판정만) / trace(첫 갈라짐까지, 기본)
FEEDBACK_LEVEL = os.environ.get("JOI_FEEDBACK", "trace")
# 이 이유들은 IR·기기 쪽 문제라 코드를 고쳐도 안 바뀐다 — LLM 을 부르지 않는다
_IR_SIDE_REASONS = ("인자 위치에 여러 대 자리", "read 위치에 여러 대 자리", "cond tokenize",
                    "여러 대 읽기의 비교 상대", "cron 앵커 불일치")


def _code_side(verdict: str, note: str) -> bool:
    """게이트가 거른 이유가 코드 쪽인가(= LLM 이 고칠 여지가 있나)."""
    return not any(r in (note or "") for r in _IR_SIDE_REASONS)


def _feedback_text(draft: dict | None, verdict: str, note: str) -> str:
    """LLM 에게 줄 글: 초안 코드(있으면) + 게이트가 본 것 + 할 일."""
    lines = []
    if draft:
        lines += ["[Draft Code]", json.dumps({k: draft.get(k, "" if k != "period" else 0)
                                              for k in ("cron", "period", "script")}, ensure_ascii=False)]
    if verdict == "CANT":
        lines += ["[Gate Feedback]", f"규칙 lowering 이 이 IR 모양을 못 만들었음: {note}"]
    elif FEEDBACK_LEVEL == "verdict":
        lines += ["[Gate Feedback]", f"판정: {verdict} (코드가 IR 과 같지 않음)"]
    else:
        lines += ["[Gate Feedback]", f"판정: {verdict} — {note}"]
    lines += ["[Task]", "위 피드백을 반영해 IR 과 같은 동작이 되도록 코드를 고쳐라. 초안이 있으면 꼭 필요한 줄만 바꿔라. "
                         "출력은 {\"cron\", \"period\", \"script\"} JSON 하나만."]
    return "\n".join(lines)


def _run_gate(ir, jb, connected_devices, selection, log_buf):
    """게이트: IR 과 코드 블록을 나란히 돌려 같은지 본다. (verdict, note) 를 돌려준다."""
    _t = time.perf_counter()
    try:
        g = gate_row(ir, jb, connected_devices, selection)
        verdict, note = g.verdict, ((g.notes or [""])[-1] if g.notes else "")
        if verdict == "DIVERGE" and g.product and g.product.divergences:
            d = g.product.divergences[0]
            note = (note + f" | 첫 갈라짐 IR:{d.actions_a} 코드:{d.actions_b}").strip(" |")
    except Exception as e:  # 게이트 자체가 터지면 판정 못 한 것으로 친다
        verdict, note = "REFUSED", f"게이트 오류: {type(e).__name__}: {e}"
    log_buf.append(f"🚧 gate: {verdict} ({time.perf_counter() - _t:.2f}s) {note}".rstrip())
    return verdict, note


# ─────────────────────────────────────────────────────────────────────────────
# Main entry
# ─────────────────────────────────────────────────────────────────────────────
def generate_joi_code_ir(
    sentence,
    connected_devices,
    other_params,
    base_url=None,
    current_code=None,
):
    """A natural-language command → a JoI block.

    `current_code` (optional): an already-generated JoI block the user wants to
    EDIT; `sentence` is then the edit request and Stage 0 rewrites it into one
    complete standalone command before the normal pipeline runs.
    `base_url` is accepted for backward compatibility and ignored — there is one
    in-process model (engine.py)."""
    connected_devices = _parse_dict_input(connected_devices, None)
    other_params = _parse_dict_input(other_params, {})

    start = time.perf_counter()
    log_buf = []

    def infer(key, user_input, *, system=None, enable_thinking=False, max_tokens=512, prefill=None):
        sys_content = system or PROMPTS.get(key, "")
        content, log_line = run_llm_inference(key, [
            {"role": "system", "content": sys_content},
            {"role": "user", "content": user_input}
        ], enable_thinking=enable_thinking, max_tokens=max_tokens, prefill=prefill)
        log_buf.append(log_line)
        if enable_thinking:
            content = re.sub(r'<think>.*?</think>\s*', '', content, flags=re.DOTALL).strip()
        return content

    if not isinstance(connected_devices, dict) or not connected_devices:
        raise JoiGenerationError("No connected devices provided.", "\n".join(log_buf),
                                 error_code="no_devices")

    # ── Stage 0 (optional): feedback edit — understand the current code in words
    # (re_translate → re_translate_kor), then apply only the requested change.
    if current_code:
        code_block = _normalize_edit_code(current_code)
        current_nl = ""
        try:
            _cur_en = infer("re_translate", f"[Code]\n{code_block}", max_tokens=512).strip()
            log_buf.append(f"📝 edit re_translate (EN): {_cur_en}")
            _cur_ko = infer("re_translate_kor", _cur_en, max_tokens=1024).strip() if _cur_en else ""
            if _cur_ko:
                log_buf.append(f"📝 edit re_translate (KO): {_cur_ko}")
            current_nl = _cur_ko or _cur_en
        except Exception as _e:
            log_buf.append(f"⚠️ edit code-understanding failed ({_e}) — editing raw feedback")
        if current_nl:
            edited = infer("feedback_edit",
                           f"[Current Command]\n{current_nl}\n\n[Edit Request]\n{sentence}",
                           max_tokens=512).strip()
            if edited:
                log_buf.append(f"✏️ feedback_edit: {sentence!r} on {current_nl!r} → {edited!r}")
                sentence = edited
            else:
                log_buf.append("⚠️ feedback_edit produced empty output — using raw feedback")

    original_sentence = sentence

    # ── Stage 1: command → Timeline IR (joi_slm; no approval, used as built) ──
    _t = time.perf_counter()
    try:
        slm_out = _slm_pipe()(sentence, connected_devices)
    except Exception as e:
        log_buf.append(f"⛔ ir (joi_slm): {type(e).__name__}: {e}")
        raise JoiGenerationError(f"IR build failed: {e}", "\n".join(log_buf), error_code="ir_failed")
    ir = slm_out["ir"]
    segments = slm_out.get("segments", [])
    log_buf.append(f"🧩 segments ({time.perf_counter() - _t:.2f}s): "
                   + " | ".join(f"[{s.get('type')}] {s.get('text')}" for s in segments))
    log_buf.append(f"🧱 IR: {json.dumps(ir, ensure_ascii=False)}")

    # ── Stage 2: IR services × connected devices → 기기 고르기 + 수량 + selectors (Python) ──
    try:
        selection = build_selectors(ir, connected_devices, slm_out)
    except MissingDevices as e:
        log_buf.append(f"⛔ devices: {e}")
        raise JoiGenerationError(f"Cannot fulfill command — {e}", "\n".join(log_buf),
                                 error_code="no_suitable_device")
    ir = selection["ir"]                                   # 능력 검사가 call 을 고쳤을 수 있음
    if selection["swaps"]:
        log_buf.append("🔧 능력 검사: " + ", ".join(f"{a}→{b}" for a, b in selection["swaps"]))
    precision_output = {"selectors": selection["selectors"], "resolved": selection["resolved"],
                        "reasoning": "명사·태그·닉네임 어휘 조인 + 수량 정책 (joi/devices.py)"}
    selected_services = selection["selected_services"]
    service_details = extract_service_details(selected_services, SERVICE_DATA)
    log_buf.append(f"🎯 selectors: {selection['selectors']}"
                   + (f"  자리별: {selection['slots']}" if selection.get("slots") else ""))

    # ── Stage 3: feasibility → lowering → 게이트 ──
    try:
        check_feasibility(ir)
    except FeasibilityError as e:
        log_buf.append(f"⛔ feasibility: {e}")
        raise JoiGenerationError(f"IR infeasible: {e}", "\n".join(log_buf), error_code="ir_infeasible")

    code_plan = ""
    gate_verdict, gate_note = "", ""
    lowering_used, fix_rounds = "rules", 0
    if LOWER_MODE != "llm":
        # 기본: 규칙 lowering (LLM 없음) → 게이트가 EQUIV 라고 할 때만 통과.
        # 규칙이 못 만들거나 게이트 밖이면, 코드 쪽 문제일 때만 LLM 에게 초안+피드백을 주고
        # 고치게 한다(최대 LLM_FIX_ROUNDS 번). 그래도 EQUIV 가 아니면 거절 — 폴백 없음.
        _t = time.perf_counter()
        joi_json, cant = None, ""
        try:
            jb = lower_ir(ir, selection)
            joi_json = {"name": "Scenario", "cron": jb.get("cron") or "",
                        "period": int(jb.get("period") or 0), "script": jb.get("script", "")}
            log_buf.append(f"🧮 lowering(규칙) ({time.perf_counter() - _t:.2f}s)")
            try:
                _ = validate_joi(joi_json["script"], connected_devices, _SERVICE_CATEGORY_MAP)
            except Exception as e:
                log_buf.append(f"⚠️ validate_joi warning: {e}")
            gate_verdict, gate_note = _run_gate(ir, joi_json, connected_devices, selection, log_buf)
        except CantLower as e:
            cant = str(e)
            log_buf.append(f"⛔ lowering(규칙): 아직 못 만드는 모양 — {e}")
            gate_verdict, gate_note = "CANT", cant
        if gate_verdict != "EQUIV" and LLM_FIX_ROUNDS > 0 and (cant or _code_side(gate_verdict, gate_note)):
            draft = joi_json
            for k in range(1, LLM_FIX_ROUNDS + 1):
                fix_rounds = k
                extra = _feedback_text(draft, gate_verdict, gate_note)
                log_buf.append(f"🔁 LLM 고치기 {k}/{LLM_FIX_ROUNDS} ← {gate_verdict} {gate_note}".rstrip())
                try:
                    cand, code_plan = _lower_by_llm(ir, sentence, selection, service_details,
                                                    connected_devices, infer, log_buf,
                                                    extra=extra, fix=draft is not None)
                except JoiGenerationError as e:
                    log_buf.append(f"⚠️ LLM 고치기 실패: {e}")
                    break
                log_buf.append(f"🧾 LLM 코드 {k}: {json.dumps(cand, ensure_ascii=False)[:400]}")
                v, n = _run_gate(ir, cand, connected_devices, selection, log_buf)
                draft, gate_verdict, gate_note = cand, v, n
                if v == "EQUIV":
                    joi_json, lowering_used = cand, "rules+llm"
                    break
            if gate_verdict != "EQUIV":
                joi_json = draft or joi_json
        elif gate_verdict != "EQUIV":
            log_buf.append("ℹ️ LLM 고치기 건너뜀 (IR·기기 쪽 이유거나 JOI_LLM_FIX=0)")
        if gate_verdict == "CANT":
            raise JoiGenerationError(f"규칙 lowering 밖의 IR 모양: {cant}", "\n".join(log_buf),
                                     error_code="lowering_unsupported")
        if gate_verdict != "EQUIV":
            err = JoiGenerationError(f"게이트 {gate_verdict}: 코드가 IR 과 같다고 확인되지 않음 — {gate_note}",
                                     "\n".join(log_buf),
                                     error_code=f"lowering_gate_{gate_verdict.lower()}")
            err.joi_json = joi_json            # 거절했지만 만든 코드는 붙여 둔다(test.py 가 보여줌)
            err.gate = {"verdict": gate_verdict, "note": gate_note}
            err.fix_rounds = fix_rounds
            raise err
    else:
        lowering_used = "llm"
        joi_json, code_plan = _lower_by_llm(ir, sentence, selection, service_details,
                                            connected_devices, infer, log_buf)
        # 기준선 측정용: 게이트 판정은 기록만 하고 거르지 않는다
        gate_verdict, gate_note = _run_gate(ir, joi_json, connected_devices, selection, log_buf)

    joi_code_raw = json.dumps(joi_json, indent=2, ensure_ascii=False)
    code_pretty = _unescape_script(joi_code_raw)

    # ── Stage 4: 이름 짓기 — code → EN NL → KO NL → 짧은 이름.
    # 기본은 안 돌린다(코드 만들기와 상관없는 단계라 시간만 먹는다). 켜려면 JOI_NAME=1.
    _id2nick = {rid: info["nickname"] for rid, info in (connected_devices or {}).items()
                if isinstance(info, dict) and info.get("nickname")}

    def _ids_to_nick(text: str) -> str:
        return re.sub(r'#([\w\-]+)',
                      lambda m: ('#' + _id2nick[m.group(1)].replace(' ', '_'))
                      if m.group(1) in _id2nick else m.group(0), text)

    translated_sentence = ""
    translated_sentence_kor = ""
    if os.environ.get("JOI_NAME") == "1":
        is_korean = bool(re.search(r"[가-힣]", original_sentence))
        try:
            _eng_plan = f"\n\n[Code Plan]\n{code_plan}" if code_plan else ""
            _re_in = (
                f"[Code]\n{_ids_to_nick(joi_code_raw)}{_eng_plan}{_duration_hints(joi_json)}\n\n"
                f"[Service Descriptions]\n{json.dumps(service_details, indent=2, ensure_ascii=False)}"
            )
            translated_sentence = infer("re_translate", _re_in).strip()
            log_buf.append(f"📝 re_translate (EN): {translated_sentence}")
        except Exception as _e:
            log_buf.append(f"⚠️ re_translate failed ({_e})")
        if is_korean and translated_sentence:
            try:
                translated_sentence_kor = infer("re_translate_kor", translated_sentence, max_tokens=1024).strip()
                log_buf.append(f"📝 re_translate (KO): {translated_sentence_kor}")
            except Exception as _e:
                log_buf.append(f"⚠️ re_translate_kor failed ({_e})")
        scenario_name = ""
        try:
            _name_in = translated_sentence_kor if is_korean else (translated_sentence or original_sentence)
            if _name_in:
                scenario_name = infer("scenario_name", _name_in).strip()
        except Exception as _e:
            log_buf.append(f"⚠️ scenario_name failed ({_e})")
        if not scenario_name:  # fallback: snake_case the English re-translation
            scenario_name = re.sub(r'[^\w\s]', '', (translated_sentence or "").strip())
        scenario_name = re.sub(r'\s+', '_', scenario_name.strip())
        scenario_name = re.sub(r'[^\w:]', '', scenario_name).strip('_') or "Scenario"
        log_buf.append(f"🏷️ scenario name: {scenario_name}")
        try:
            _cj = json.loads(joi_code_raw)
            _cj = {"name": scenario_name, **{k: v for k, v in _cj.items() if k != "name"}}
            joi_code_raw = json.dumps(_cj, indent=2, ensure_ascii=False)
            code_pretty = _unescape_script(joi_code_raw)
        except (json.JSONDecodeError, TypeError):
            pass

    elapsed = time.perf_counter() - start

    return {
        "code": code_pretty,
        "ir": ir,
        "segments": segments,
        "mapping": slm_out.get("mapping", {}),
        "precision": precision_output["selectors"],
        "precision_reasoning": precision_output["reasoning"],
        "lowering": lowering_used,             # rules / rules+llm(게이트 피드백으로 LLM 이 고침) / llm
        "fix_rounds": fix_rounds,
        "gate": {"verdict": gate_verdict, "note": gate_note},
        "log": {
            "response_time": f"{elapsed:.4f} seconds",
            "translated_sentence": translated_sentence_kor or translated_sentence,
            "logs": "\n".join(log_buf),
        },
    }


# Alias matching the original name so callers can swap imports easily.
generate_joi_code = generate_joi_code_ir
