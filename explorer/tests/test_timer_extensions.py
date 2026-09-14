"""Independent use-site, calendar, snapshot and witness boundary regressions."""
import itertools
import unittest

from explorer.runtime.interp import parse, step as concrete_step, Unsupported
from explorer.runtime.ir_step import IrRunner
from explorer.runtime.pause import PauseRunner
from explorer.runtime.oneshot import OneShotRunner
from explorer.verification.timer_analysis import analyze
from explorer.verification.timer_product import timer_product
from explorer.verification.product import check_supported_pair, replay_divergence
from explorer.analysis.modular import counter_moduli


def run(a,b,domains,t0=0,step=100):
    return timer_product(a,b,domains=domains,
        axes=check_supported_pair(a,b,input_domains=domains), input_step_ms=step,
        t0_ms=t0,max_states=3000,max_transitions=100000,max_input_combinations=100)


def snapshot_pair(limit=3, code_limit=None, strict=False):
    cond=f'$ta == null or Clock.Timestamp - $ta >= {limit} or $tb == null or Clock.Timestamp - $tb >= {limit}'
    a=IrRunner({'timeline':[{'op':'start_at','anchor':'now'},
        {'op':'cycle','count':'n','period':'0 MSEC','body':[
            {'op':'cycle','period':'0 MSEC','body':[
                {'op':'wait','cond':'Sensor.Present == true','edge':'rising'},
                {'op':'if','cond':cond,'then':[{'op':'break'}]}]},
            {'op':'call','target':'Switch.On','args':{}},
            {'op':'if','cond':'n % 2 == 0',
             'then':[{'op':'read','var':'ta','src':'Clock.Timestamp'}],
             'else':[{'op':'read','var':'tb','src':'Clock.Timestamp'}]}]}]})
    source='''armed := true
slot := 0
has_a := false
has_b := false
ta := 0
tb := 0
p = (#Sensor).Present
ts = (#Clock).Timestamp
if (p == true) {
 if (armed == true) {
  armed = false
  if (has_a == false or ts - ta OP LIMIT or has_b == false or ts - tb >= LIMIT) {
   (#Switch).On()
   if (slot == 0) { ta = ts has_a = true slot = 1 }
   else { tb = ts has_b = true slot = 0 }
  }
 }
} else { armed = true }
'''.replace('LIMIT',str(limit if code_limit is None else code_limit)).replace('OP','>' if strict else '>=')
    return a,PauseRunner(source,True,100)


class ExtensionTests(unittest.TestCase):
    def test_modulo_lcm_and_negative_updates_match_unreduced_execution(self):
        for delta in (-5,1,7):
            source=f'''n := -1
if (n % 2 == 0) {{ (#Switch).On() }}
if (n % 3 == 1) {{ (#Switch).Off() }}
n = n + {delta}
'''
            # Negative literals are unary expressions; use a positive decrement.
            if delta<0: source=source.replace(f'+ {delta}',f'- {-delta}')
            source=source.replace(':= -1',':= 5')
            stmts=parse(source)
            self.assertEqual(counter_moduli(stmts),{'n':6})
            b=PauseRunner(stmts,True,100)
            av,bv={},{}
            for tick in range(40):
                ra=concrete_step(stmts,av,{}, {},tick*100,first_tick=tick==0)
                rb=b.step(bv,{}, {},tick*100,first_tick=tick==0)
                self.assertEqual(ra.actions,rb.actions)
                self.assertEqual(ra.vars['n']%6,rb.vars['n'])
                av,bv=ra.vars,rb.vars

    def test_modulo_raw_use_and_leak_are_not_quotiented(self):
        base='n := 0 if (n % 3 == 1) { (#Switch).On() } n = n + 1 '
        for tail in ('x = n','if (n >= 5) { (#Switch).Off() }',
                     '(#Switch).On(n % 3)','n = n * 2'):
            self.assertNotIn('n',counter_moduli(parse(base+tail)))

    def test_any_action_rejected_but_any_read_parses(self):
        with self.assertRaisesRegex(ValueError,'ACTION position'):
            parse('any(#Switch).On()')
        self.assertTrue(parse('x = any(#Sensor).Present'))

    def test_hour_shared_overapprox_and_one_shot(self):
        a=IrRunner({'timeline':[{'op':'start_at','anchor':'now'},
            {'op':'wait','cond':'Sensor.Present == true or Clock.Hour >= 6'},
            {'op':'if','cond':'Sensor.Present == true','then':[
                {'op':'call','target':'Switch.On','args':{}}]}]})
        b=OneShotRunner('wait until((#Sensor).Present == true or (#Clock).Hour >= 6) if ((#Sensor).Present == true) { (#Switch).On() }')
        self.assertEqual(run(a,b,{'sensor.present':[False,True]}).verdict,'EQUIV')
        with self.assertRaisesRegex(Unsupported,'align'):
            run(a,b,{'sensor.present':[False,True]},t0=1)

    def test_calendar_fault_is_replayed_at_real_hour_boundary(self):
        a=IrRunner({'timeline':[{'op':'start_at','anchor':'now'},
            {'op':'wait','cond':'Sensor.Present == true'},
            {'op':'if','cond':'Clock.Hour < 6','then':[{'op':'call','target':'Switch.On','args':{}}]}]})
        b=OneShotRunner('wait until((#Sensor).Present == true) if ((#Clock).Hour <= 6) { (#Switch).On() }')
        r=run(a,b,{'sensor.present':[False,True]},t0=21600000-100)
        self.assertEqual(r.verdict,'DIVERGE',r.notes)
        self.assertTrue(replay_divergence(a,b,r.divergences[0]).confirmed)
        self.assertTrue(all(not any(k.startswith('clock.') for k in w)
                            for w,_ in r.divergences[0].path))

    def test_snapshot_regions_and_boundary_mutants(self):
        for t0 in (0,900,5000000000):
            a,b=snapshot_pair()
            self.assertEqual(run(a,b,{'sensor.present':[False,True]},t0=t0).verdict,'EQUIV')
        for kw in ({'code_limit':2},{'code_limit':4},{'strict':True}):
            a,b=snapshot_pair(**kw)
            r=run(a,b,{'sensor.present':[False,True]})
            self.assertEqual(r.verdict,'DIVERGE',r.notes)
            self.assertTrue(replay_divergence(a,b,r.divergences[0]).confirmed)
            self.assertFalse(any(k.startswith('clock.') for w,_ in r.divergences[0].path for k in w))

    def test_snapshot_exhaustive_short_histories_and_reset(self):
        a,b=snapshot_pair(limit=1)
        for bits in itertools.product((False,True),repeat=7):
            av,bv={},{}
            for tick,p in enumerate(bits):
                now=tick*100
                ra=a.step(av,{}, {'sensor.present':p},now,first_tick=tick==0)
                rb=b.step(bv,{}, {'sensor.present':p},now,first_tick=tick==0)
                self.assertEqual(ra.actions,rb.actions)
                av,bv=ra.vars,rb.vars

    def test_snapshot_literal_reset_and_output_leak_rejected(self):
        for extra in ('ta = 0','(#Switch).On(ta)','x = ts + 1','ta = ts + 1'):
            a,b=snapshot_pair()
            b=PauseRunner(b.stmts+parse(extra),True,100)
            with self.assertRaises(Unsupported): analyze(a,b,100)

    def test_timestamp_alias_cannot_survive_a_blocking_continuation(self):
        a,b=snapshot_pair()
        stmts=b.stmts+parse('delay(1 SEC) if (ts - ta > 3) { (#Switch).Off() }')
        with self.assertRaisesRegex(Unsupported,'nonblocking'):
            analyze(a,PauseRunner(stmts,True,100),100)

    def test_multistage_missing_reset_witness_preserves_input_start(self):
        a=IrRunner({'timeline':[{'op':'start_at','anchor':'now'},
            {'op':'cycle','period':'100 MSEC','body':[
                {'op':'wait','cond':'Sensor.Present == true','edge':'rising'},
                {'op':'call','target':'Switch.On','args':{}},
                {'op':'cycle','period':'100 MSEC','body':[
                    {'op':'wait','cond':'Sensor.Present == false'},
                    {'op':'wait','cond':'Sensor.Present == true','timeout':'5 SEC',
                     'on_timeout':[{'op':'call','target':'Switch.Off','args':{}},{'op':'break'}]},
                    {'op':'call','target':'Switch.On','args':{}}]}]}]})
        b=PauseRunner('''armed := true
state := 0
ticks := 0
p = (#Sensor).Present
if (state == 0) {
 if (p == true) { if (armed == true) { (#Switch).On() armed = false state = 1 } }
 else { armed = true }
} else if (state == 1) {
 if (p == false) { state = 2 }
} else {
 ticks = ticks + 1
 if (p == true) { (#Switch).On() state = 1 }
 else if (ticks >= 50) { (#Switch).Off() state = 0 }
}''',True,100)
        r=run(a,b,{'sensor.present':[False,True]})
        self.assertEqual(r.verdict,'DIVERGE',r.notes)
        self.assertTrue(replay_divergence(a,b,r.divergences[0]).confirmed)


if __name__=='__main__': unittest.main()
