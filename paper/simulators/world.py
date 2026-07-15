"""Virtual world: clock + device state during a simulation.

Both IR and JoI simulators share this implementation so cond evaluation,
expression evaluation, and effect application are identical given the same
scenario input.
"""

from __future__ import annotations

from .scenario import Scenario, ScenarioEvent

_DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
_MS_PER_DAY = 86_400_000


class World:
    """Mutable world state advanced by the simulator.

    Time origin: Monday 00:00:00 of an arbitrary week. `t_ms` is ms since that
    instant. `clock.time` returns hhmm-int (0 to 2359). `clock.dayOfWeek`
    returns one of MON..SUN.
    """

    def __init__(self, scenario: Scenario):
        self.t_ms: int = 0
        self.scenario = scenario
        self.state: dict = dict(scenario.initial_world)
        self.vars: dict = {}
        # Pending events queue — already sorted in scenario.add()
        self._pending: list[ScenarioEvent] = list(scenario.events)
        # Apply any t=0 events immediately (in addition to initial_world)
        self._drain_due()

    # ── Time advance ─────────────────────────────────────────────────────────

    def advance_to(self, target_ms: int) -> None:
        """Advance the virtual clock to `target_ms`, applying any due events."""
        if target_ms < self.t_ms:
            raise ValueError(f"cannot rewind clock: {self.t_ms} -> {target_ms}")
        self.t_ms = target_ms
        self._drain_due()

    def advance_by(self, dt_ms: int) -> None:
        self.advance_to(self.t_ms + dt_ms)

    def _drain_due(self) -> None:
        """Apply all pending scenario events whose at_ms <= self.t_ms."""
        while self._pending and self._pending[0].at_ms <= self.t_ms:
            ev = self._pending.pop(0)
            self.state[ev.key] = ev.value

    # ── Clock readout ────────────────────────────────────────────────────────

    @property
    def clock(self) -> dict:
        """Returns {time: int hhmm, date: str YYYYMMdd, dayOfWeek: str MON..SUN}.

        Date returned as 8-digit string anchored at 20260427 (a Monday) for
        determinism. Day-of-week derived from t_ms regardless of date.
        """
        ms_in_day = self.t_ms % _MS_PER_DAY
        hour = ms_in_day // 3_600_000
        minute = (ms_in_day // 60_000) % 60
        days_elapsed = (self.t_ms // _MS_PER_DAY) + self._dow_offset()
        dow = _DAYS[days_elapsed % 7]

        # Anchor: 2026-04-27 is a Monday (per memory date).
        base_y, base_m, base_d = 2026, 4, 27
        # Simple day-add for date; good enough for 7-day window.
        day_num = self.t_ms // _MS_PER_DAY
        # advance base date by day_num days
        from datetime import date, timedelta
        d = date(base_y, base_m, base_d) + timedelta(days=day_num)
        return {
            "time": hour * 100 + minute,
            "date": d.strftime("%Y%m%d"),
            "dayOfWeek": dow,
        }

    def _dow_offset(self) -> int:
        """Offset from Monday given the scenario's start_dow."""
        try:
            return _DAYS.index(self.scenario.start_dow)
        except ValueError:
            return 0

    # ── Effect application ──────────────────────────────────────────────────

    def effect_key(self, service: str, method: str) -> str | None:
        """Canonical world-state key a call to `service.method` writes, or None.

        Shared by apply_effect (the write) and the IR sim's `var` capture (the
        read-back), so a read-modify-write op observes the slot its own call
        just updated. Keys are canonical (lowercase, service-prefix stripped),
        the same namespace DeviceRef reads use.
        """
        from .expr import canonical_name
        svc = (service or "").lower()
        m = canonical_name(service, method)
        if m in ("on", "off", "toggle"):
            return f"{svc}.switch"
        if m.startswith("set") and m != "set":
            return f"{svc}.{m[3:]}"  # "setbrightness" → "brightness"
        if m.startswith("moveto") and m != "movecolor":
            return f"{svc}.{m[6:]}"
        return None

    def apply_effect(self, service: str, method: str, args_named: dict) -> None:
        """Best-effort: apply common setter effects to world state.

        Keys stored in canonical form (lowercase, service-prefix stripped) so
        DeviceRef reads and apply_effect writes use the same namespace.
        """
        from .expr import canonical_name
        key = self.effect_key(service, method)
        if key is None:
            return
        m = canonical_name(service, method)
        if m == "on":
            self.state[key] = True
        elif m == "off":
            self.state[key] = False
        elif m == "toggle":
            self.state[key] = not bool(self.state.get(key, False))
        elif args_named and len(args_named) == 1:
            self.state[key] = next(iter(args_named.values()))
        # Else (setter without resolvable single arg): leave state untouched
