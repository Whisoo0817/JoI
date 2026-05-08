"""Scenario: external events scheduled along the virtual timeline.

A scenario is the input fed to both IR and JoI simulators so trace-equivalence
is evaluated under identical world conditions.

Each ScenarioEvent specifies that at virtual time `at_ms` (or before, applied
as initial state if `at_ms == 0`), the world's `world[key]` becomes `value`.
The simulators consume this list in order: when the virtual clock reaches an
event's time, the world dict is mutated. Conditions referring to that key
will then evaluate against the new value.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ScenarioEvent:
    at_ms: int          # absolute virtual time (ms since Mon 00:00)
    key: str            # "Service.Attr"
    value: object       # new value (bool, int, float, str)

    def __repr__(self) -> str:
        return f"@{self.at_ms}ms {self.key}={self.value!r}"


@dataclass
class Scenario:
    """A scheduled list of external state changes + initial world overrides.

    `initial_world` seeds the world dict at t=0 (used for stable starting state
    like "door is closed initially").
    `events` are sorted by `at_ms` ascending.
    `start_clock`: hhmm at virtual t=0 (default 0 = Monday midnight).
    `start_dow`: dayOfWeek at virtual t=0 (default "MON").
    """
    initial_world: dict = field(default_factory=dict)
    events: list[ScenarioEvent] = field(default_factory=list)
    start_clock: int = 0          # hhmm at t=0
    start_dow: str = "MON"

    def add(self, at_ms: int, key: str, value: object) -> None:
        self.events.append(ScenarioEvent(at_ms, key, value))
        self.events.sort(key=lambda e: e.at_ms)

    def events_in_window(self, t_lo_ms: int, t_hi_ms: int) -> list[ScenarioEvent]:
        """Events with t_lo_ms <= at_ms <= t_hi_ms."""
        return [e for e in self.events if t_lo_ms <= e.at_ms <= t_hi_ms]
