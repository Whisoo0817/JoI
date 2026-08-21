"""Pure single-tick interpreter for JoI scripts.

The v1 simulator (sim/joi_simulator.py) drives the whole run: it owns the
clock, the event schedule (World/Scenario), and the trace. Here the loop is
inverted for state-space exploration: the caller owns time and inputs, and
this module exposes exactly one thing — a side-effect-free step function.

    step(stmts, vars_in, gv_in, inputs, now_ms, first_tick) -> StepResult

Given the variable store, global variables, this tick's sensor readings, and
the current time, it executes the script body once and returns the new
variable store, new globals, and the list of emitted actions. Calling it
twice with the same arguments returns the same result; nothing persists
inside the module. That purity is what lets an explorer memoize states and
choose time jumps.

Semantics mirror sim/joi_simulator.py for the periodic fragment:
- `:=` assigns run only on the first tick; `=` assigns run every tick.
- One vars dict persists across ticks (a `:=` var updated via `=` keeps its
  value between ticks, e.g. the `was_pushed = pushed` edge idiom).
- `wait until(cond)` false → abort the rest of this tick.
- `break` → script terminates (StepResult.terminated).
- Clock reads (`(#Clock).clock_hour` etc.) resolve from `now_ms`; t=0 is
  Monday 00:00. Holidays are environment input ("clock.isholiday").
- GlobalVariable get*/set* read and write the gv dict; set* is also recorded
  as an Action so cross-scenario writes stay an observable output channel.

Out of scope (raise Unsupported): ForEach (v2 grounding unrolls it before
simulation), delay() inside periodic bodies, one-shot/cron scheduling —
schedule handling belongs to the driver, not the tick function.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import expr as expr_mod
from . import joi_parser as jp
from .expr import canonical_key


class Unsupported(Exception):
    """Construct outside the supported periodic fragment."""


@dataclass
class AbortTickStmt:
    """Skip the rest of THIS tick; state persists and the next tick runs.
    Produced by the cron driver for top-level `break` (in cron semantics a
    break ends the current firing window, not the script)."""


@dataclass(frozen=True)
class OpaqueToken:
    """Return value of a query the environment has no axis for (e.g. a
    camera capture). The simulator cannot know the content — and doesn't
    need to: what verification checks is PROVENANCE. The token flows
    through variables into action arguments, so the product comparison
    naturally checks "does the email carry the capture from the same
    device?" — a mis-wired redeploy shows up as an argument mismatch."""
    service: str
    target: tuple
    method: str
    args: tuple = ()

    def __repr__(self) -> str:
        tgt = "#".join(self.target) if self.target else self.service
        return f"⟨{self.method}@{tgt}⟩"


@dataclass(frozen=True)
class Action:
    service: str
    method: str
    args: tuple
    target: tuple = ()   # selector tag set — the device identity

    def __repr__(self) -> str:  # compact for demos/traces
        tgt = "#" + "#".join(self.target) if self.target else ""
        return f"{self.service}{tgt}.{self.method}{self.args}"


def world_key(tags: tuple, service: str, method: str) -> str:
    """Device-state key. Assumption (locked 2026-07-31): distinct selectors
    denote distinct devices — no aliasing — so the sorted tag set IS the
    identity. Clock and single-tag selectors keep their v1-style short key
    (e.g. "door.contact") so existing inputs stay readable."""
    svc, attr = canonical_key(service, method)
    if svc == "clock":
        return f"clock.{attr}"
    low = sorted(t.lower() for t in tags)
    if len(low) <= 1:
        return f"{svc}.{attr}"
    return f"{'+'.join(low)}.{attr}"


@dataclass
class StepResult:
    vars: dict[str, Any]
    gv: dict[str, Any]
    actions: list[Action]
    terminated: bool = False
    guards: tuple = ()          # (id(IfStmt), taken) in execution order


# ── Clock ────────────────────────────────────────────────────────────────────

_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday",
             "friday", "saturday", "sunday")
_DAY_MS = 86_400_000


def clock_state(now_ms: int, holiday: bool = False) -> dict[str, Any]:
    """Derive every clock.* reading from a concrete time. t=0 = Monday 00:00."""
    total_min = now_ms // 60_000
    return {
        # JoI timestamps are epoch SECONDS: corpus cooldowns compare
        # `now - reg` against constants like 600 (10 min) or 3600*3 (3 h).
        "clock.timestamp": now_ms // 1000,
        "clock.hour": (total_min // 60) % 24,
        "clock.minute": total_min % 60,
        "clock.weekday": _WEEKDAYS[(now_ms // _DAY_MS) % 7],
        "clock.isholiday": holiday,
    }


# ── Step function ────────────────────────────────────────────────────────────

MAX_LOOP_ITERS = 10_000  # runaway guard for loop(cond)


class _AbortTick(Exception):
    pass


class _Break(Exception):
    pass


class _Ctx:
    def __init__(self, world: dict, vars_: dict, gv: dict, actions: list):
        self.world = world      # sensor readings + clock.* (read-only this tick)
        self.vars = vars_
        self.gv = gv
        self.actions = actions
        # (id(IfStmt), branch taken) in execution order. The code's own
        # decision path — the intensional summary of why this tick did what
        # it did, and the projection edges collapse onto.
        self.guards: list = []


def parse(src: str) -> list:
    return jp.parse_script(src)


def step(stmts: list, vars_in: dict, gv_in: dict, inputs: dict,
         now_ms: int, first_tick: bool = False,
         holiday: bool = False) -> StepResult:
    """Execute the script body once. Pure: inputs are never mutated."""
    vars_ = dict(vars_in)
    gv = dict(gv_in)
    actions: list[Action] = []
    world = {**clock_state(now_ms, holiday), **inputs}
    ctx = _Ctx(world, vars_, gv, actions)
    terminated = False
    try:
        for s in stmts:
            _exec(s, ctx, first_tick)
    except _AbortTick:
        pass
    except _Break:
        terminated = True
    return StepResult(vars_, gv, actions, terminated, tuple(ctx.guards))


def _exec(stmt: Any, ctx: _Ctx, first_tick: bool) -> None:
    if isinstance(stmt, jp.Assign):
        if stmt.op == ":=":
            if first_tick:
                ctx.vars[stmt.name] = _eval(stmt.rhs, ctx)
            # later ticks: value persists, initializer skipped
        else:
            ctx.vars[stmt.name] = _eval(stmt.rhs, ctx)
    elif isinstance(stmt, jp.IfStmt):
        taken = _truthy(_eval(stmt.cond, ctx))
        ctx.guards.append((id(stmt), taken))
        body = stmt.then_body if taken else stmt.else_body
        for s in body:
            _exec(s, ctx, first_tick)
    elif isinstance(stmt, jp.CallStmt):
        _do_call(stmt.call, ctx, as_read=False)
    elif isinstance(stmt, jp.Loop):
        iters = 0
        try:
            while _truthy(_eval(stmt.cond, ctx)):
                iters += 1
                if iters > MAX_LOOP_ITERS:
                    raise Unsupported("loop() exceeded iteration cap")
                for s in stmt.body:
                    _exec(s, ctx, first_tick)
        except _Break:
            pass  # break exits the loop, not the script
    elif isinstance(stmt, jp.WaitUntil):
        if not _truthy(_eval(stmt.cond, ctx)):
            raise _AbortTick()
    elif isinstance(stmt, jp.Break):
        raise _Break()
    elif isinstance(stmt, AbortTickStmt):
        raise _AbortTick()
    elif isinstance(stmt, jp.Delay):
        raise Unsupported("delay() inside a periodic body")
    elif isinstance(stmt, jp.ForEach):
        raise Unsupported("ForEach must be grounded before simulation")
    else:
        raise Unsupported(f"unknown stmt: {type(stmt).__name__}")


def _truthy(v: Any) -> bool:
    return bool(v)


# ── Calls: GlobalVariable vs external actions ────────────────────────────────

def _do_call(call: jp.CallExpr, ctx: _Ctx, as_read: bool = True) -> Any:
    """Statement-position calls (as_read=False) are actuations and are
    recorded as Actions. Expression-position calls (as_read=True) are queries
    — e.g. `fc = (#WeatherProvider).weatherProvider_forecast(h)` — answered
    from the environment under the parameterized key "svc.method(args)"
    (falling back to "svc.method"), with nothing recorded."""
    svc, method = canonical_key(call.service, call.method)
    args = tuple(_eval(a, ctx) for a in (call.args or ()))
    if svc == "globalvariable":
        if method.startswith("get"):
            return ctx.gv.get(args[0])
        if method.startswith("set"):
            ctx.gv[args[0]] = args[1]
            ctx.actions.append(Action(svc, method, args))
            return args[1]
        raise Unsupported(f"GlobalVariable method: {method}")
    wkey = world_key(call.tags, call.service, call.method)
    if as_read:
        pkey = f"{wkey}({','.join(map(repr, args))})"
        if pkey in ctx.world:
            return ctx.world[pkey]
        if wkey in ctx.world:
            return ctx.world[wkey]
        # no environment axis answers this query → opaque provenance token
        return OpaqueToken(svc, tuple(call.tags), method, args)
    ctx.actions.append(Action(svc, method, args, tuple(call.tags)))
    return ctx.world.get(wkey)


# ── Expression evaluation ────────────────────────────────────────────────────

def _eval(node: Any, ctx: _Ctx) -> Any:
    if isinstance(node, jp.CallExpr):
        if node.args is None:  # attribute read, e.g. (#Door).contact
            return ctx.world.get(world_key(node.tags, node.service, node.method))
        return _do_call(node, ctx)
    if isinstance(node, expr_mod.QuantRef):
        svc = node.tags[-1] if node.tags else ""
        return ctx.world.get(world_key(node.tags, svc, node.member))
    if isinstance(node, expr_mod.DeviceRef):
        return ctx.world.get(node.key)
    # Lit / ClockRef / VarRef / UnaryOp / BinaryOp / FuncCall share the v1
    # evaluator; ClockRef fields map onto the same clock.* world keys.
    ec = expr_mod.EvalContext(
        ctx.world, ctx.vars,
        {"time": ctx.world["clock.hour"] * 100 + ctx.world["clock.minute"],
         "dayOfWeek": ctx.world["clock.weekday"],
         "timestamp": ctx.world["clock.timestamp"]},
    )
    return _hybrid_eval(node, ec, ctx)


def _hybrid_eval(node: Any, ec: expr_mod.EvalContext, ctx: _Ctx) -> Any:
    """expr_mod.evaluate, except CallExpr subtrees route back through _eval
    so GV reads inside compound expressions still hit the gv dict."""
    if isinstance(node, (jp.CallExpr, expr_mod.DeviceRef)):
        return _eval(node, ctx)
    if isinstance(node, expr_mod.UnaryOp):
        v = _hybrid_eval(node.operand, ec, ctx)
        return (not v) if node.op == "not" else -v
    if isinstance(node, expr_mod.BinaryOp):
        # Quantified compares (`>|` etc.) evaluate as their plain op until
        # grounding unrolls the device set — exact for a 1-instance world.
        op = node.op[:-1] if node.op.endswith("|") else node.op
        rebuilt = expr_mod.BinaryOp(
            op,
            expr_mod.Lit(_hybrid_eval(node.left, ec, ctx)),
            expr_mod.Lit(_hybrid_eval(node.right, ec, ctx)),
        )
        return expr_mod.evaluate(rebuilt, ec)
    if isinstance(node, expr_mod.FuncCall):
        rebuilt = expr_mod.FuncCall(
            node.name, [expr_mod.Lit(_hybrid_eval(a, ec, ctx)) for a in node.args])
        return expr_mod.evaluate(rebuilt, ec)
    return expr_mod.evaluate(node, ec)
