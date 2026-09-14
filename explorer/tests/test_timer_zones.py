"""Timer proof obligations, boundary faults and small exhaustive histories."""
import itertools
import json
import unittest
from dataclasses import asdict

from explorer.runtime.ir_step import IrRunner
from explorer.runtime.pause import PauseRunner
from explorer.runtime.interp import Unsupported
from explorer.verification.product import check_supported_pair, replay_divergence
from explorer.verification.timer_product import timer_product
from explorer.verification.timer_analysis import analyze
from explorer.verification.timer_domain import Number, Zone, Split, reaction
from explorer.verification.timed import timed_product


def pair(limit=4, code_limit=None, step=100, extra=''):
    body = [
        {'op': 'wait', 'cond': 'Sensor.Present == true', 'edge': 'rising'},
        {'op': 'if', 'cond': 'Sensor.Dark == false', 'then': [
            {'op': 'wait', 'cond': 'Sensor.Dark == true or Sensor.Present == false',
             'edge': 'rising', 'timeout': f'{limit * step} MSEC',
             'on_timeout': [{'op': 'read', 'var': 'unused', 'src': 'Clock.Hour'}]},
            {'op': 'if', 'cond': 'Sensor.Dark == true and Sensor.Present == true',
             'then': [{'op': 'call', 'target': 'Switch.On', 'args': {}}]},
        ]},
    ]
    ir = IrRunner({'timeline': [{'op': 'start_at', 'anchor': 'now'},
                               {'op': 'cycle', 'period': f'{step} MSEC', 'body': body}]})
    code = PauseRunner('''armed := true
state := 0
ticks := 0
p = (#Sensor).Present
d = (#Sensor).Dark
if (state == 0) {
    if (p == true) {
        if (armed == true) {
            armed = false
            if (d == false) { state = 1 ticks = 0 }
        }
    } else { armed = true }
} else {
    ticks = ticks + 1
    if (d == true or p == false) {
        if (d == true and p == true) { (#Switch).On() }
        state = 0
    } else if (ticks >= LIMIT) { state = 0 }
}
'''.replace('LIMIT', str(limit if code_limit is None else code_limit)) + extra, True, step)
    return ir, code


DOMAINS = {'sensor.present': [False, True], 'sensor.dark': [False, True]}


def run(a, b, step=100, **caps):
    return timer_product(a, b, domains=DOMAINS,
        axes=check_supported_pair(a, b, input_domains=DOMAINS), input_step_ms=step,
        t0_ms=0, max_states=caps.get('max_states', 2000),
        max_transitions=caps.get('max_transitions', 100000), max_input_combinations=100)


def concrete(a, b, history, step=100):
    av, bv = {}, {}
    for i, world in enumerate(history):
        ra = a.step(av, {}, world, i * step, first_tick=i == 0)
        rb = b.step(bv, {}, world, i * step, first_tick=i == 0)
        if ra.actions != rb.actions: return False
        av, bv = ra.vars, rb.vars
    return True


class TimerTests(unittest.TestCase):
    def test_sustain_and_timeout_simultaneous_and_reset(self):
        for sustain, timeout in ((4, 4), (3, 5), (5, 3)):
            a = IrRunner({'timeline': [{'op': 'start_at', 'anchor': 'now'},
                {'op': 'wait', 'cond': 'Sensor.Present == true',
                 'for': f'{sustain * 100} MSEC', 'timeout': f'{timeout * 100} MSEC',
                 'on_timeout': [{'op': 'call', 'target': 'Switch.Off', 'args': {}}]},
                {'op': 'call', 'target': 'Switch.On', 'args': {}}]})
            source = '''entered := false
done := false
active := false
elapsed := 0
held := 0
p = (#Sensor).Present
if (done == false) {
    if (entered == false) { entered = true } else { elapsed = elapsed + 1 }
    if (p == true) {
        if (active == false) { active = true held = 0 } else { held = held + 1 }
    } else { active = false held = 0 }
    if (p == true and held >= SUSTAIN) { (#Switch).On() done = true }
    else if (elapsed >= TIMEOUT) { (#Switch).Off() done = true }
}'''.replace('SUSTAIN', str(sustain)).replace('TIMEOUT', str(timeout))
            b = PauseRunner(source, True, 100)
            r = run(a, b)
            self.assertEqual(r.claim, 'EQUIV-FIXPOINT', r.notes)
            worlds = [{'sensor.present': p, 'sensor.dark': False} for p in (False, True)]
            self.assertTrue(all(concrete(a, b, h) for h in itertools.product(worlds, repeat=7)))

    def test_original_long_window_cost_is_independent_of_ticks(self):
        sizes = []
        for limit in (4, 72000, 144000):
            a, b = pair(limit)
            r = run(a, b)
            self.assertEqual(r.claim, 'EQUIV-FIXPOINT', r.notes)
            self.assertTrue(r.symbolic_certificate['complete'])
            json.dumps(asdict(r))
            sizes.append(r.n_states)
        self.assertLess(max(sizes), 30)

    def test_one_tick_early_and_late_are_never_certified(self):
        for limit in (3, 5):
            a, b = pair(4, limit)
            r = run(a, b)
            self.assertEqual(r.verdict, 'DIVERGE', r.notes)
            self.assertTrue(replay_divergence(a, b, r.divergences[0]).confirmed)

    def test_constant_input_boundary_witness_is_replayed(self):
        a = IrRunner({'timeline': [{'op': 'start_at', 'anchor': 'now'},
            {'op': 'delay', 'duration': '400 MSEC'},
            {'op': 'call', 'target': 'Switch.On', 'args': {}}]})
        b = PauseRunner('''ticks := 0
done := false
if (done == false) {
    ticks = ticks + 1
    if (ticks >= 6) { (#Switch).On() done = true }
}''', True, 100)
        r = run(a, b)
        self.assertEqual(r.verdict, 'DIVERGE', r.notes)
        self.assertTrue(replay_divergence(a, b, r.divergences[0]).confirmed)
        self.assertLessEqual(len(r.divergences[0].path), 3)

    def test_deadline_before_equal_after_and_reset_restart(self):
        a, b = pair(4)
        light = {'sensor.present': True, 'sensor.dark': False}
        dark = {'sensor.present': True, 'sensor.dark': True}
        absent = {'sensor.present': False, 'sensor.dark': False}
        for when in (3, 4, 5):
            for prefix in ([], [light, absent], [light, light, absent]):
                self.assertTrue(concrete(a, b, prefix + [light] * when + [dark, absent, light, dark]))

    def test_all_small_histories_and_boundary_mutants(self):
        worlds = [dict(zip(DOMAINS, xs)) for xs in itertools.product(*DOMAINS.values())]
        for limit in (1, 2, 3):
            a, b = pair(2, limit)
            found = any(not concrete(a, b, h) for h in itertools.product(worlds, repeat=5))
            r = run(a, b)
            self.assertEqual(r.verdict, 'DIVERGE' if found else 'EQUIV', r.notes)

    def test_action_leak_and_derived_copy_rejected(self):
        for extra in ('\n(#Switch).On(ticks)', '\nsaved = ticks'):
            a, b = pair(extra=extra)
            with self.assertRaises(Unsupported): analyze(a, b, 100)

    def test_live_clock_and_off_grid_deadline_rejected(self):
        a, b = pair(extra='\nh = (#Clock).Timestamp')
        with self.assertRaises(Unsupported): analyze(a, b, 100)
        a, b = pair()
        next(x for x in a.prog.ins if x.to_sec).to_sec += 0.001
        with self.assertRaises(Unsupported): analyze(a, b, 100)

    def test_unused_clock_read_must_be_dead_and_nonreserved(self):
        for name in ('unused', '__fin'):
            a, b = pair()
            read = next(x for x in a.prog.ins if x.kind == 'READ')
            read.var = name
            if name == 'unused':
                next(x for x in a.prog.ins if x.kind == 'CALL').args = (('var', name),)
                self.assertNotIn(name, analyze(a, b, 100).dead)
            else:
                with self.assertRaises(Unsupported): analyze(a, b, 100)

    def test_unknown_wrapper_rejected(self):
        class HiddenClock:
            def __init__(self, inner): self.inner = inner
            def __getattr__(self, name): return getattr(self.inner, name)
        a, b = pair()
        with self.assertRaises(Unsupported): analyze(HiddenClock(a), b, 100)

    def test_cap_is_not_equivalence(self):
        a, b = pair()
        for cap in ({'max_states': 1}, {'max_transitions': 1}):
            self.assertEqual(run(a, b, **cap).claim, 'INCONCLUSIVE')

    def test_bounded_call_does_not_use_unbounded_proof(self):
        a, b = pair()
        r = timed_product(a, b, input_domains=DOMAINS, horizon_ms=200)
        self.assertEqual(r.claim, 'EQUIV-BOUNDED')
        self.assertIsNone(r.symbolic_certificate)


class DomainTests(unittest.TestCase):
    def test_guard_partition_inclusive_integer_boundaries(self):
        x = Number({'x': 1})
        zone = Zone(('x',)).constrain(-x).constrain(x - 5)
        for op, fn in (('<', lambda x: x < 3), ('<=', lambda x: x <= 3),
                       ('==', lambda x: x == 3), ('!=', lambda x: x != 3),
                       ('>', lambda x: x > 3), ('>=', lambda x: x >= 3)):
            pending, regions = [zone], []
            while pending:
                z = pending.pop()
                try:
                    with reaction(z) as ctx: answer = bool(fn(x))
                    regions.append((ctx[0], answer))
                except Split as split: pending.extend(split.zones)
            for value in range(6):
                point = Zone().image({'x': Number(constant=value)})
                matched = [answer for z, answer in regions if z.covers(point)]
                self.assertEqual(matched, [fn(value)], op)

    def test_two_timers_same_deadline_and_different_reset(self):
        x, y = Number({'x': 1}), Number({'y': 1})
        zone = Zone(('x', 'y')).constrain(x-y).constrain(y-x).constrain(-x).constrain(x-8)
        with reaction(zone): self.assertTrue(x == y)
        advanced = zone.image({'x': x+1, 'y': y+1})
        with reaction(advanced): self.assertTrue(x == y)
        reset = advanced.image({'x': Number(constant=0), 'y': y})
        with reaction(reset): self.assertTrue(x < y)

    def test_widen_contains_both_and_retains_difference(self):
        old = Zone().image({'x': Number(constant=0), 'y': Number(constant=1)})
        new = Zone().image({'x': Number(constant=1), 'y': Number(constant=2)})
        widened = old.widen(new, (-1, 0, 1, 10))
        self.assertTrue(widened.covers(old) and widened.covers(new))
        with reaction(widened.canonical()):
            self.assertTrue(Number({'y': 1}) - Number({'x': 1}) == 1)


if __name__ == '__main__': unittest.main()
