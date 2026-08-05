"""Stage ③e — NL edit requests → typed edits (editir).

"NL names the delta; contracts define correctness."  The model (or, here, a
rule backend) never writes reactive code: it CLASSIFIES the request into the
closed edit vocabulary and NAMES the anchor; the harness synthesizes the
Edit objects from the verified base's structure, and the normal pipeline
(splice check → contracts → miter) judges the result.

Decision kinds:

    param_change   "25.5도를 26도로 바꿔줘"  → ModifyPredicate / ReplaceArgument
                   (anchors: guard constants, call arguments, `:=` config
                   constants — the three places a parameter can live)
    device_swap    "에어컨 말고 선풍기로 교체해줘" → ReplaceSelector (tag swap);
                   role-contract recheck is the caller's next stage
    feature_drop   "스피커 알림은 빼줘"       → roles to drop (slicer plans the
                   deletion cone; editir only names the feature closure)
    env_adapt      "연결된 장치에 맞춰 수정해줘" → route to the bind pipeline
    reject         anything unmatched or ambiguous — fail closed, with the
                   candidate anchors listed so a human (or an LLM backend)
                   can disambiguate

Ambiguity is REJECTED, not guessed: a number that matches two anchors names
both in `candidates` and refuses. An LLM backend can slot in behind the same
interface later (7지선다: the 7 EDIT_OPS + reject); the rule backend is the
deterministic core the benchmark pins down.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from adapt.patch import Edit, replace_argument, replace_tag  # noqa: E402
from adapt.structure import Structure  # noqa: E402
from adapt.template import Template  # noqa: E402


@dataclass
class Anchor:
    site: str            # guard | arg | config
    text: str            # matched literal
    line: int
    detail: str          # human-readable location
    span: object = None
    ref: object = None   # DeviceRef for arg sites
    arg_index: int = -1


@dataclass
class EditDecision:
    kind: str                       # param_change|device_swap|feature_drop|env_adapt|reject
    edits: list[Edit] = field(default_factory=list)
    drop_roles: list[str] = field(default_factory=list)
    anchor: str = ""
    reason: str = ""
    candidates: list[str] = field(default_factory=list)


# ── device-name vocabulary (ko/en → catalog type) ───────────────────────────

DEVICE_WORDS = {
    "에어컨": "AirConditioner", "aircon": "AirConditioner", "ac": "AirConditioner",
    "airconditioner": "AirConditioner",
    "선풍기": "Fan", "fan": "Fan",
    "가습기": "Humidifier", "humidifier": "Humidifier",
    "제습기": "Dehumidifier", "dehumidifier": "Dehumidifier",
    "공기청정기": "AirPurifier", "청정기": "AirPurifier", "airpurifier": "AirPurifier",
    "조명": "Light", "불": "Light", "라이트": "Light", "light": "Light",
    "스피커": "Speaker", "speaker": "Speaker",
    "카메라": "Camera", "camera": "Camera",
    "이메일": "EmailProvider", "email": "EmailProvider",
    "토스트": "ToastPublisher", "toast": "ToastPublisher",
    "히터": "Heater", "heater": "Heater",
}

_NUM = r"\d+(?:\.\d+)?"


def _device_word(text: str) -> Optional[str]:
    t = text.strip().lower().replace(" ", "")
    return DEVICE_WORDS.get(t)


# ── anchor scan ──────────────────────────────────────────────────────────────

def _num_eq(a: str, b: str) -> bool:
    try:
        return float(a) == float(b)
    except ValueError:
        return False


def find_number_anchors(st: Structure, literal: str) -> list[Anchor]:
    """Every place `literal` appears as a standalone constant: guard sides,
    call arguments, and `:=`/`=` config-constant right-hand sides."""
    out: list[Anchor] = []
    for g in st.guards:
        for side, sp in (("rhs", g.rhs_span), ("lhs", g.lhs_span)):
            if sp is None:
                continue
            txt = sp.slice(st.src).strip()
            if txt == literal or _num_eq(txt, literal):
                out.append(Anchor("guard", txt, g.line,
                                  f"guard {side} @L{g.line}: {g.text.strip()[:60]}",
                                  span=sp))
    for d in st.devices:
        for i, a in enumerate(d.args or []):
            txt = a.text.strip()
            if txt == literal or _num_eq(txt, literal):
                out.append(Anchor("arg", txt, d.line,
                                  f"{'/'.join(d.tags)}.{d.member} arg{i} @L{d.line}",
                                  ref=d, arg_index=i))
    for a in st.assigns:
        txt = a.rhs_span.slice(st.src).strip()
        if txt == literal or _num_eq(txt, literal):
            out.append(Anchor("config", txt, a.line,
                              f"{a.name} {a.op} {txt} @L{a.line}",
                              span=a.rhs_span))
    return out


_HINTS = {
    "temp": ("온도", "temp"), "humid": ("습도", "humid"),
    "bright": ("밝기", "bright"), "co2": ("co2", "이산화탄소"),
    "grace": ("유예", "grace"), "cooldown": ("쿨다운", "간격", "cooldown"),
    "summer": ("여름", "summer"), "winter": ("겨울", "winter"),
}


def _narrow_by_hints(anchors: list[Anchor], nl: str) -> list[Anchor]:
    """Keep anchors whose location text mentions every concept the request
    mentions (여름/온도/유예…). Purely lexical — enough for the deterministic
    core; free-form synonyms are the LLM backend's job."""
    low = nl.lower()
    active = [words for words in _HINTS.values()
              if any(w in low for w in words)]
    if not active:
        return anchors
    kept = []
    for a in anchors:
        loc = a.detail.lower()
        if all(any(w in loc for w in words) for words in active):
            kept.append(a)
    return kept or anchors


def _edit_for(anchor: Anchor, new_text: str) -> Edit:
    if anchor.site == "arg":
        return replace_argument(anchor.ref, anchor.arg_index, new_text)
    op = "ModifyPredicate"   # guard constants and `:=` thresholds alike
    return Edit(anchor.span, new_text, op, anchor.detail)


# ── the rule backend ─────────────────────────────────────────────────────────

_P_PARAM = re.compile(
    rf"(?P<old>{_NUM})\s*(?:도|%|퍼센트|초|분|℃|°c)?\s*(?:를|을|에서)\s*"
    rf"(?P<new>{_NUM})\s*(?:도|%|퍼센트|초|분|℃|°c)?\s*(?:로|으로)", re.I)
_P_PARAM_EN = re.compile(
    rf"(?:change|set|replace)?[^0-9]*?(?P<old>{_NUM})\s*(?:to|with|->)\s*"
    rf"(?P<new>{_NUM})", re.I)
_P_SWAP = re.compile(
    r"(?P<old>[가-힣A-Za-z ]+?)\s*(?:말고|대신|대신에)\s*(?P<new>[가-힣A-Za-z ]+?)"
    r"\s*(?:로|으로)?\s*(?:교체|바꿔|변경|써|사용)", re.I)
_P_SWAP_EN = re.compile(
    r"replace\s+(?:the\s+)?(?P<old>[A-Za-z ]+?)\s+with\s+(?:an?\s+)?"
    r"(?P<new>[A-Za-z ]+)", re.I)
_P_DROP = re.compile(
    r"(?P<what>[가-힣A-Za-z ]+?)\s*(?:은|는|를|을)?\s*"
    r"(?:빼|제거|없애|삭제|끄|꺼)", re.I)
_P_ENV = re.compile(r"(connected|연결된)\s*(devices?|장치|기기)|환경에\s*맞", re.I)


def classify(nl: str, st: Structure, template: Optional[Template] = None,
             catalog: Optional[dict] = None) -> EditDecision:
    nl = nl.strip()

    if _P_ENV.search(nl):
        return EditDecision("env_adapt",
                            anchor="whole binding",
                            reason="route to the bind pipeline (stage ④)")

    m = _P_SWAP.search(nl) or _P_SWAP_EN.search(nl)
    if m:
        return _swap(m.group("old"), m.group("new"), st, catalog)

    m = _P_PARAM.search(nl) or _P_PARAM_EN.search(nl)
    if m:
        return _param(m.group("old"), m.group("new"), nl, st)

    m = _P_DROP.search(nl)
    if m:
        return _drop(m.group("what"), st, template)

    return EditDecision("reject",
                        reason="no rule pattern matched — escalate "
                               "(LLM backend / human)")


def _param(old: str, new: str, nl: str, st: Structure) -> EditDecision:
    anchors = find_number_anchors(st, old)
    if not anchors:
        return EditDecision("reject",
                            reason=f"constant {old} not found in the scenario")
    narrowed = _narrow_by_hints(anchors, nl)
    if len(narrowed) > 1:
        return EditDecision("reject",
                            reason=f"constant {old} is ambiguous "
                                   f"({len(narrowed)} anchors) — refuse to guess",
                            candidates=[a.detail for a in narrowed])
    a = narrowed[0]
    return EditDecision("param_change", edits=[_edit_for(a, new)],
                        anchor=a.detail)


def _swap(old_w: str, new_w: str, st: Structure,
          catalog: Optional[dict]) -> EditDecision:
    old_t, new_t = _device_word(old_w), _device_word(new_w)
    if old_t is None or new_t is None:
        unknown = old_w if old_t is None else new_w
        return EditDecision("reject",
                            reason=f"unknown device word {unknown!r}")
    if catalog is not None and new_t not in catalog:
        return EditDecision("reject",
                            reason=f"{new_t} is not in the platform catalog")
    refs = [d for d in st.devices if old_t in d.tags]
    if not refs:
        return EditDecision("reject",
                            reason=f"{old_t} is not referenced by this scenario")
    edits = replace_tag(st, old_t, new_t)
    return EditDecision("device_swap", edits=edits,
                        anchor=f"#{old_t} -> #{new_t} "
                               f"({len(edits)} selector sites)",
                        reason="role-contract recheck required (stage ②/④)")


def _scenario_facts(st: Structure, template: Optional[Template]) -> str:
    """The context an LLM needs to NAME a delta: the scenario's constants and
    device types. Never the code — the model translates intent, not programs."""
    lines = []
    for a in st.assigns:
        if a.op == ":=":
            lines.append(f"  {a.name} = {a.rhs_span.slice(st.src).strip()}")
    types = sorted({t for d in st.devices for t in d.tags})
    out = "constants:\n" + "\n".join(lines[:20])
    out += "\ndevice tags: " + ", ".join(types)
    if template is not None:
        out += "\nfeatures: " + ", ".join(sorted(
            {r.feature for r in template.roles if r.feature}))
    return out


_LLM_SYSTEM = """You translate a smart-home user's edit request into ONE delta JSON.
You never write code. Choose exactly one form:

{"kind":"param_change","old_value":"<number now in the scenario>","new_value":"<number>","hints":["<zero or more of: temp, humid, bright, co2, grace, cooldown, summer, winter>"]}
{"kind":"device_swap","old_device":"<word>","new_device":"<word>"}
{"kind":"feature_drop","device":"<device word>"}
{"kind":"env_adapt"}
{"kind":"reject","why":"<short reason>"}

Rules: old_value must be a constant that actually appears in the scenario facts.
If the user names only a target value, find which constant they mean from the
facts and hints. If the request is not an edit, or you cannot ground it in the
facts, answer reject. Output ONLY the JSON.

Example — facts contain `max_temp_summer = 25.5`, request "여름엔 좀 시원하게, 26도 기준으로 맞춰줘":
{"kind":"param_change","old_value":"25.5","new_value":"26","hints":["temp","summer"]}
Example — request "에어컨 대신 선풍기를 쓰고 싶어":
{"kind":"device_swap","old_device":"에어컨","new_device":"선풍기"}
Example — request "고마워!":
{"kind":"reject","why":"not an edit request"}"""


def classify_with_llm(nl: str, st: Structure,
                      template: Optional[Template] = None,
                      catalog: Optional[dict] = None) -> EditDecision:
    """Rule backend first; free-form leftovers go to the local sLLM, whose
    JSON delta re-enters the SAME deterministic synthesis path (anchors,
    ambiguity refusal, essential guard). The model names the delta; it never
    touches code, and a bad delta fails closed exactly like a bad request."""
    d = classify(nl, st, template, catalog)
    if not (d.kind == "reject" and d.reason.startswith("no rule pattern")):
        return d
    from adapt.llm import chat_json
    try:
        # thinking ON: grounding "음성 안내"→speaker or "PM10 기준"→st_pm10 needs
        # the reasoning pass; chat_json is hardened against leaked templates
        j = chat_json(f"scenario facts:\n{_scenario_facts(st, template)}\n\n"
                      f"request: {nl}", system=_LLM_SYSTEM, thinking=True)
    except Exception as e:
        return EditDecision("reject",
                            reason=f"llm backend unavailable/unparseable: {e}")
    kind = j.get("kind")
    if kind == "param_change":
        hint_text = " ".join(_HINTS_WORDS(h) for h in j.get("hints") or [])
        return _param(str(j.get("old_value", "")), str(j.get("new_value", "")),
                      nl + " " + hint_text, st)
    if kind == "device_swap":
        return _swap(str(j.get("old_device", "")), str(j.get("new_device", "")),
                     st, catalog)
    if kind == "feature_drop":
        return _drop(str(j.get("device", "")), st, template)
    if kind == "env_adapt":
        return EditDecision("env_adapt", anchor="whole binding",
                            reason="route to the bind pipeline (stage ④)")
    return EditDecision("reject",
                        reason=f"llm: {j.get('why', 'rejected')}")


def _HINTS_WORDS(key: str) -> str:
    words = _HINTS.get(key)
    return words[0] if words else ""


def _drop(what: str, st: Structure,
          template: Optional[Template]) -> EditDecision:
    dev = None
    for w in re.split(r"\s+", what.strip()):
        dev = dev or _device_word(w)
    dev = dev or _device_word(what)
    if dev is None:
        return EditDecision("reject", reason=f"unknown feature/device {what!r}")
    if template is None:
        return EditDecision("reject",
                            reason="feature drop needs the purpose template "
                                   "(essential/optional is a contract fact)")
    hit = [r for r in template.roles
           if any(dev in list(src.tags) for src in r.sources)]
    if not hit:
        return EditDecision("reject",
                            reason=f"{dev} does not source any role of "
                                   f"{template.id}")
    feats = {r.feature for r in hit if r.feature}
    closure = sorted({r.role for r in template.roles
                      if (r.feature in feats) or r.role in {h.role for h in hit}})
    ess = [r for r in closure if template.role(r).essential]
    if ess:
        return EditDecision("reject",
                            reason=f"{ess} is essential — dropping it kills "
                                   f"the scenario's purpose (abort, not edit)")
    return EditDecision("feature_drop", drop_roles=closure,
                        anchor=f"{dev} -> roles {closure}")
