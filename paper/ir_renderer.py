"""Deterministic controlled-English renderer for Timeline IR.

The renderer is intentionally not a free-form summarizer. It preserves IR order
and scope while flattening common temporal structures that are hard for
non-expert users to read as nested blocks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any


_DURATION_RE = re.compile(r"^(\d+)\s+(HOUR|MIN|SEC|MSEC)$")
_DURATION_UNIT_EN = {
    "HOUR": ("hour", "hours"),
    "MIN": ("minute", "minutes"),
    "SEC": ("second", "seconds"),
    "MSEC": ("millisecond", "milliseconds"),
}
_DOW_EN = {
    "1": "Monday",
    "2": "Tuesday",
    "3": "Wednesday",
    "4": "Thursday",
    "5": "Friday",
    "6": "Saturday",
    "7": "Sunday",
    "MON": "Monday",
    "TUE": "Tuesday",
    "WED": "Wednesday",
    "THU": "Thursday",
    "FRI": "Friday",
    "SAT": "Saturday",
    "SUN": "Sunday",
}

_SERVICE_NAMES = {
    "AirConditioner": "air conditioner",
    "AirPurifier": "air purifier",
    "AirQualitySensor": "air quality sensor",
    "ColorControl": "color control",
    "ContactSensor": "contact sensor",
    "Door": "door",
    "HumiditySensor": "humidity sensor",
    "Humidifier": "humidifier",
    "Light": "light",
    "LevelControl": "level control",
    "MotionSensor": "motion sensor",
    "MultiButton": "multi-button",
    "PresenceSensor": "presence sensor",
    "Speaker": "speaker",
    "Switch": "selected switch",
    "TemperatureSensor": "temperature sensor",
    "WindowCovering": "window covering",
}

_ATTR_NAMES = {
    "Brightness": "brightness",
    "Button1": "button 1",
    "Button2": "button 2",
    "Button3": "button 3",
    "Button4": "button 4",
    "CurrentLevel": "current level",
    "CurrentPosition": "current position",
    "DoorState": "door state",
    "FineDustLevel": "fine dust level",
    "Humidity": "humidity",
    "Motion": "motion",
    "Presence": "presence",
    "Temperature": "temperature",
}


@dataclass
class Sections:
    start: list[str] = field(default_factory=list)
    repeat: list[str] = field(default_factory=list)
    behavior: list[str] = field(default_factory=list)
    stop: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def extend(self, other: "Sections") -> None:
        self.start.extend(other.start)
        self.repeat.extend(other.repeat)
        self.behavior.extend(other.behavior)
        self.stop.extend(other.stop)
        self.notes.extend(other.notes)


@dataclass
class RenderContext:
    var_labels: dict[str, str] = field(default_factory=dict)
    var_source_labels: dict[str, str] = field(default_factory=dict)


def render_ir_readable(ir: dict[str, Any]) -> str:
    """Render Timeline IR into deterministic, flat controlled English."""
    sections = Sections()
    ctx = RenderContext()
    timeline = ir.get("timeline", [])

    if timeline and isinstance(timeline[0], dict) and timeline[0].get("op") == "start_at":
        sections.start.append(_render_start(timeline[0]))
        rest = timeline[1:]
    else:
        rest = timeline

    sections.extend(_render_steps(rest, ctx))
    return _format_sections(sections)


def _render_steps(steps: list[dict[str, Any]], ctx: RenderContext) -> Sections:
    sections = Sections()
    if not steps:
        return sections

    if len(steps) == 1 and steps[0].get("op") == "cycle":
        return _render_cycle(steps[0], ctx)

    if (
        len(steps) == 2
        and steps[0].get("op") == "wait"
        and steps[1].get("op") == "cycle"
    ):
        sections.behavior.extend(_render_wait(steps[0], ctx))
        cycle_sections = _render_cycle(steps[1], ctx, prefix="After that, ")
        sections.extend(cycle_sections)
        return sections

    sections.behavior.extend(_render_sequence(steps, ctx))
    return sections


def _render_cycle(
    step: dict[str, Any],
    ctx: RenderContext,
    *,
    prefix: str = "",
) -> Sections:
    sections = Sections()
    body = step.get("body", []) or []
    period = step.get("period")
    until = step.get("until")
    count = step.get("count")

    wait = body[0] if body and isinstance(body[0], dict) and body[0].get("op") == "wait" else None
    if wait and wait.get("edge") in {"rising", "falling"} and period == "100 MSEC":
        event = _event_phrase_from_wait(wait, ctx)
        sections.repeat.append(f"{prefix}Watch for each new {event}.")
        sections.repeat.append("Run the following behavior once for every new occurrence.")
        if wait.get("for"):
            sections.notes.extend(_wait_for_notes(wait, ctx))
        remaining = body[1:]
        if count and _is_modulo_pattern(remaining, count):
            sections.behavior.extend(_render_modulo_pattern(remaining[0], count, event, ctx))
        else:
            sections.behavior.extend(_render_sequence(remaining, ctx))
    else:
        cadence = _cadence_to_en(period) if period else "iteration"
        first_read = body[0] if body and body[0].get("op") == "read" else None
        if first_read:
            label = _source_label(first_read.get("src", "value"))
            sections.repeat.append(f"{prefix}Every {cadence}, check the {label}.")
        elif body and body[0].get("op") == "if":
            label = _first_condition_source_label(body[0].get("cond", ""))
            if label:
                sections.repeat.append(f"{prefix}Every {cadence}, check the {label}.")
            else:
                sections.repeat.append(f"{prefix}Every {cadence}, run the following behavior.")
        else:
            sections.repeat.append(f"{prefix}Every {cadence}, run the following behavior.")
        sections.behavior.extend(_render_sequence(body, ctx))

    stop_after = _count_until_limit(until, count)
    if stop_after is not None:
        sections.stop.append(f"Stop after {stop_after} times.")
    elif until:
        sections.stop.append(f"Stop when {_render_cond(until, ctx)}.")

    return sections


def _render_sequence(steps: list[dict[str, Any]], ctx: RenderContext) -> list[str]:
    lines: list[str] = []
    for step in steps:
        op = step.get("op")
        if op == "read":
            lines.append(_render_read(step, ctx))
        elif op == "if":
            lines.extend(_render_if_chain(step, ctx))
        elif op == "wait":
            lines.extend(_render_wait(step, ctx))
        elif op == "delay":
            lines.append(f"Wait for {_duration_to_en(step.get('duration'))}.")
        elif op == "call":
            lines.append(_capitalize(_render_call_phrase(step, ctx)) + ".")
        elif op == "cycle":
            nested = _render_cycle(step, ctx)
            lines.extend(_flatten_nested_sections(nested))
        elif op == "break":
            lines.append("Stop the current repeat loop.")
        elif op == "start_at":
            lines.append(_render_start(step))
        else:
            lines.append(f"Run unsupported IR step `{op}`.")
    return lines


def _render_if_chain(step: dict[str, Any], ctx: RenderContext) -> list[str]:
    chain, final_else = _collect_if_chain(step)
    lines: list[str] = []
    for i, branch in enumerate(chain):
        cond = _render_cond(branch.get("cond", ""), ctx)
        action = _render_branch_phrase(branch.get("then", []), ctx)
        if i == 0:
            lines.append(f"If {cond}, {action}.")
        else:
            lines.append(f"Otherwise, if {cond}, {action}.")

    if final_else:
        lines.append(f"Otherwise, {_render_branch_phrase(final_else, ctx)}.")
    else:
        lines.append("Otherwise, do nothing.")
    return lines


def _collect_if_chain(step: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    chain = []
    current = step
    while isinstance(current, dict) and current.get("op") == "if":
        chain.append(current)
        else_body = current.get("else", []) or []
        if len(else_body) == 1 and isinstance(else_body[0], dict) and else_body[0].get("op") == "if":
            current = else_body[0]
            continue
        return chain, else_body
    return chain, []


def _render_branch_phrase(steps: list[dict[str, Any]], ctx: RenderContext) -> str:
    if not steps:
        return "do nothing"
    phrases: list[str] = []
    for step in steps:
        op = step.get("op")
        if op == "call":
            phrases.append(_render_call_phrase(step, ctx))
        elif op == "delay":
            phrases.append(f"wait for {_duration_to_en(step.get('duration'))}")
        elif op == "break":
            phrases.append("stop the current repeat loop")
        elif op == "read":
            phrases.append(_render_read(step, ctx).rstrip(".").lower())
        elif op == "if":
            nested = _render_if_chain(step, ctx)
            phrases.append("; ".join(line.rstrip(".").lower() for line in nested))
        else:
            phrases.append(f"run `{op}`")
    return _join_phrases(phrases)


def _render_read(step: dict[str, Any], ctx: RenderContext) -> str:
    var = step.get("var", "")
    src = step.get("src", "")
    source_label = _source_label(src)
    current_label = f"the current {source_label}"
    if var:
        ctx.var_labels[var] = current_label
        ctx.var_labels[f"${var}"] = current_label
        ctx.var_source_labels[var] = source_label
        ctx.var_source_labels[f"${var}"] = source_label
    return f"Read {src} as {current_label}."


def _render_wait(step: dict[str, Any], ctx: RenderContext) -> list[str]:
    cond = _render_cond(step.get("cond", ""), ctx)
    sustain = step.get("for")
    edge = step.get("edge", "none")
    if sustain:
        line = f"Wait until {cond} stays true for {_duration_to_en(sustain)}."
        return [line] + _wait_for_notes(step, ctx)
    if edge == "rising":
        return [f"Wait until {cond} becomes true."]
    if edge == "falling":
        return [f"Wait until {cond} becomes false."]
    return [f"Wait until {cond} is true."]


def _wait_for_notes(step: dict[str, Any], ctx: RenderContext) -> list[str]:
    cond = _render_cond(step.get("cond", ""), ctx)
    duration = _duration_to_en(step.get("for"))
    return [f"If {cond} becomes false before {duration}, the timer starts over."]


def _render_modulo_pattern(
    step: dict[str, Any],
    count: str,
    event: str,
    ctx: RenderContext,
) -> list[str]:
    chain, final_else = _collect_if_chain(step)
    parsed: list[tuple[int, int, list[dict[str, Any]]]] = []
    modulo = None
    for branch in chain:
        m = re.fullmatch(
            rf"\s*\$?{re.escape(count)}\s*%\s*(\d+)\s*==\s*(\d+)\s*",
            str(branch.get("cond", "")),
        )
        if not m:
            return _render_if_chain(step, ctx)
        modulo = int(m.group(1))
        parsed.append((modulo, int(m.group(2)), branch.get("then", [])))

    lines: list[str] = []
    event_noun = _event_noun(event)
    for mod, value, then_steps in parsed:
        ordinal = _ordinal(value + 1)
        lines.append(
            f"On the {ordinal} {event_noun} in the pattern, "
            f"{_render_branch_phrase(then_steps, ctx)}."
        )
    if modulo is not None and final_else:
        ordinal = _ordinal(modulo)
        lines.append(
            f"On the {ordinal} {event_noun} in the pattern, "
            f"{_render_branch_phrase(final_else, ctx)}."
        )
        lines.append(f"After the {ordinal} {event_noun}, repeat the same pattern.")
    return lines


def _is_modulo_pattern(steps: list[dict[str, Any]], count: str) -> bool:
    if len(steps) != 1 or steps[0].get("op") != "if":
        return False
    chain, final_else = _collect_if_chain(steps[0])
    if not chain or not final_else:
        return False
    for branch in chain:
        if not re.fullmatch(
            rf"\s*\$?{re.escape(count)}\s*%\s*\d+\s*==\s*\d+\s*",
            str(branch.get("cond", "")),
        ):
            return False
    return True


def _render_call_phrase(step: dict[str, Any], ctx: RenderContext) -> str:
    target = step.get("target", "")
    args = step.get("args") or {}
    service, method = _split_target(target)
    service_name = _service_name(service)

    if method in {"On", "Off", "Toggle"}:
        verb = {"On": "turn on", "Off": "turn off", "Toggle": "toggle"}[method]
        return f"{verb} the {service_name}"

    if method == "MoveToBrightness":
        value = args.get("Brightness")
        if value is not None:
            return f"set the {service_name} brightness to {_num(value)}%"

    if method == "SetTargetTemperature":
        value = args.get("Temperature")
        if value is not None:
            return f"set the {service_name} target temperature to {_num(value)}"

    mode = args.get("Mode")
    if method.startswith("Set") and mode is not None:
        return f"set the {service_name} mode to {mode}"

    if args:
        arg_text = ", ".join(f"{k}={v}" for k, v in args.items())
        return f"run {target}({arg_text})"
    return f"run {target}()"


def _render_cond(expr: str, ctx: RenderContext) -> str:
    s = str(expr).strip()
    s = s.replace("&&", " and ").replace("||", " or ")
    s = s.replace(">=", " >= ").replace("<=", " <= ")
    s = s.replace("!=", " != ").replace("==", " == ")
    s = re.sub(r"\s+", " ", s).strip()

    for var, label in sorted(ctx.var_labels.items(), key=lambda item: len(item[0]), reverse=True):
        if var.startswith("$"):
            s = s.replace(var, label)
        else:
            s = re.sub(rf"\b{re.escape(var)}\b", label, s)

    if " or " in s:
        return " or ".join(_render_comparison(part) for part in s.split(" or "))
    if " and " in s:
        return " and ".join(_render_comparison(part) for part in s.split(" and "))
    return _render_comparison(s)


def _render_comparison(part: str) -> str:
    text = part.strip()
    m = re.fullmatch(r"(.+?)\s*(>=|<=|==|!=|>|<)\s*(.+)", text)
    if not m:
        return f"[{text}]"
    left, op, right = m.groups()
    left = _humanize_operand(left.strip())
    right = _clean_literal(right.strip())
    if op == ">=":
        return f"{left} is at least {right}"
    if op == "<=":
        return f"{left} is at most {right}"
    if op == ">":
        return f"{left} is above {right}"
    if op == "<":
        return f"{left} is below {right}"
    if op == "==":
        return f"{left} is {right}"
    return f"{left} is not {right}"


def _humanize_operand(value: str) -> str:
    if "." in value and not value.startswith("clock."):
        service, attr = value.split(".", 1)
        return f"the {_attr_name(attr)} of the {_service_name(service)}"
    if value.startswith("clock."):
        return value
    return value


def _clean_literal(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    if value == "true":
        return "true"
    if value == "false":
        return "false"
    return value


def _event_phrase_from_wait(step: dict[str, Any], ctx: RenderContext) -> str:
    cond = str(step.get("cond", "")).strip()
    m = re.fullmatch(r"(.+Button\d*)\s*==\s*\"?pushed\"?", cond)
    if m:
        return f"press of {m.group(1)}"
    return f"occurrence where {_render_cond(cond, ctx)}"


def _event_noun(event: str) -> str:
    if event.startswith("press of "):
        return "press"
    return "occurrence"


def _count_until_limit(until: Any, count: Any) -> int | None:
    if not until or not count:
        return None
    m = re.fullmatch(rf"\s*\$?{re.escape(str(count))}\s*>=\s*(\d+)\s*", str(until))
    if not m:
        return None
    return int(m.group(1))


def _first_condition_source_label(cond: str) -> str | None:
    m = re.search(r"\b[A-Z][A-Za-z0-9]*\.([A-Za-z][A-Za-z0-9_]*)\b", str(cond))
    if not m:
        return None
    return _attr_name(m.group(1))


def _render_start(step: dict[str, Any]) -> str:
    if step.get("anchor") == "cron":
        return f"Start {_cron_to_en(step.get('cron', ''))}."
    return "Start now."


def _format_sections(sections: Sections) -> str:
    blocks = ["Execution plan"]
    for name, lines in (
        ("Start", sections.start),
        ("Repeat", sections.repeat),
        ("Behavior", sections.behavior),
        ("Stop", sections.stop),
        ("Notes", sections.notes),
    ):
        if not lines:
            continue
        blocks.append("")
        blocks.append(f"{name}:")
        blocks.extend(f"- {line}" for line in lines)
    return "\n".join(blocks)


def _flatten_nested_sections(sections: Sections) -> list[str]:
    lines: list[str] = []
    for part in (sections.repeat, sections.behavior, sections.stop, sections.notes):
        lines.extend(part)
    return lines


def _duration_to_en(dur: Any) -> str:
    if not isinstance(dur, str):
        return str(dur)
    m = _DURATION_RE.match(dur.strip())
    if not m:
        return dur
    n = int(m.group(1))
    singular, plural = _DURATION_UNIT_EN[m.group(2)]
    return f"{n} {singular if n == 1 else plural}"


def _cadence_to_en(dur: Any) -> str:
    text = _duration_to_en(dur)
    return text[2:] if text.startswith("1 ") else text


def _cron_to_en(cron: str) -> str:
    parts = str(cron).split()
    if len(parts) != 5:
        return f"cron '{cron}'"
    minute, hour, day, month, dow = parts
    if hour.startswith("*/") and minute == "0" and day == "*" and month == "*":
        return f"every {hour[2:]} hours on {_format_dow(dow)}"
    if minute.startswith("*/") and hour == "*" and day == "*" and month == "*":
        return f"every {minute[2:]} minutes on {_format_dow(dow)}"
    time = _format_time(hour, minute)
    if dow != "*":
        return f"at {time} on {_format_dow(dow)}"
    if day != "*" and month != "*":
        return f"at {time} every year on {month}/{day}"
    if day != "*":
        return f"at {time} on day {day} of every month"
    return f"at {time} every day"


def _format_time(hour: str, minute: str) -> str:
    if not (hour.isdigit() and minute.isdigit()):
        return f"{hour}:{minute}"
    h24 = int(hour)
    m = int(minute)
    suffix = "AM" if h24 < 12 else "PM"
    h12 = h24 % 12 or 12
    return f"{h12}:{m:02d} {suffix}"


def _format_dow(dow: str) -> str:
    if dow == "*":
        return "every day"
    if dow == "1-5":
        return "weekdays"
    if dow == "6,7":
        return "weekends"
    names = [_DOW_EN.get(part.upper(), part) for part in dow.split(",")]
    if len(names) == 1:
        return names[0] + "s"
    if len(names) == 2:
        return f"{names[0]}s and {names[1]}s"
    return ", ".join(name + "s" for name in names[:-1]) + f", and {names[-1]}s"


def _split_target(target: str) -> tuple[str, str]:
    if "." not in target:
        return target, ""
    return target.split(".", 1)


def _service_name(service: str) -> str:
    return _SERVICE_NAMES.get(service, _split_camel(service).lower())


def _attr_name(attr: str) -> str:
    return _ATTR_NAMES.get(attr, _split_camel(attr).lower())


def _source_label(src: str) -> str:
    attr = src.split(".")[-1]
    return _attr_name(attr)


def _split_camel(value: str) -> str:
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", str(value))
    s = re.sub(r"[_-]+", " ", s)
    return s.strip()


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _num(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _join_phrases(phrases: list[str]) -> str:
    phrases = [p for p in phrases if p]
    if not phrases:
        return "do nothing"
    if len(phrases) == 1:
        return phrases[0]
    if len(phrases) == 2:
        return f"{phrases[0]} and {phrases[1]}"
    return ", ".join(phrases[:-1]) + f", and {phrases[-1]}"


def _capitalize(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text
