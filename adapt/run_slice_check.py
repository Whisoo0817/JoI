"""M-D evidence run: feature drops as verified deletions + static checks.

Pilot cases (the ones locked in ideas.md §9 ③):

1. **Humidifier dead** (thermo_comfort): the whole winter-humidity block goes;
   temperature control survives byte-identical; drop-signature clean.
2. **TemperatureSensor source dead** (thermo_comfort): only its for-loop goes;
   the AirQualitySensor loop keeps feeding temp_sum (no undefined survivors).
3. **AirPurifier dead** (air_quality): both purifier if-blocks go, the toast
   inside the ON-block goes with them (collateral notifier), CO2 warning and
   indicator survive.
4. **Escalations fail closed**: dropping CLOCK (live actuation inside its cone)
   and dropping TEMP_SENSORS entirely (surviving consumers) both refuse.
5. **Static checks bite on value edits**: 25.5 -> 26.0 passes; 24.0 (band
   inversion) and 99 (domain) are refused — the "simplest request still needs a
   checker" demo.
6. **End-to-end degrade**: bind (device dead) -> drop plan -> patch -> checks,
   on the real inventory.

    python3 -m adapt.run_slice_check
"""

from __future__ import annotations

from .bind import bind
from .check import check_static
from .inventory import base_office
from .patch import Edit, apply_and_check
from .slicer import plan_drop
from .structure import extract
from .template import load_skeleton, load_template

_failures: list[str] = []


def check(cond: bool, label: str) -> bool:
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        _failures.append(label)
    return cond


def _tpl(tid: str):
    t = load_template(tid)
    st = extract(load_skeleton(t), t.name)
    return t, st


def test_drop_humidity() -> None:
    print("\n[1] thermo_comfort: drop humidity feature (HUMID_SENSORS + HUMID_ACTUATOR)")
    t, st = _tpl("thermo_comfort")
    plan = plan_drop(t, st, ["HUMID_SENSORS", "HUMID_ACTUATOR"])
    check(plan.ok, f"plan computed ({len(plan.edits)} deletions; tainted={sorted(plan.tainted_vars)[:4]}...)")
    if not plan.ok:
        print("       reason:", plan.reason)
        return
    res = apply_and_check(st, plan.edits)
    check(res.ok, f"deletions splice + re-parse ({res.splice.kept_chars} chars kept)")
    after = res.structure_after
    check("humidifier" not in res.output.lower() and "humid" not in
          {d.member.lower() for d in after.devices and after.devices or []} and
          all("humid" not in d.member.lower() for d in after.devices),
          "no humidity reads/calls remain")
    ac_before = [d for d in st.devices if "AirConditioner" in d.tags]
    ac_after = [d for d in after.devices if "AirConditioner" in d.tags]
    check(len(ac_before) == len(ac_after) == 4, "temperature control intact (4 AC refs)")
    fs = check_static(t, after, before=st, dropped_roles=["HUMID_SENSORS", "HUMID_ACTUATOR"])
    blocking = [f for f in fs if f.severity == "blocking"]
    check(not blocking, f"static checks clean ({[f.detail for f in blocking][:2]})")


def test_drop_one_temp_source() -> None:
    print("\n[2] thermo_comfort: TemperatureSensor source dead, AQ survives")
    t, st = _tpl("thermo_comfort")
    contract = t.role("TEMP_SENSORS")
    from .template import refs_for_role
    ts_refs = refs_for_role(st, contract, source=contract.sources[1])
    check(len(ts_refs) == 1 and ts_refs[0].kind == "iter", "the TS source is one for-loop")

    # plan a source-level drop by slicing just that iter seed: reuse plan_drop on a
    # synthetic single-source role view
    import copy
    r2 = copy.deepcopy(contract)
    r2.sources = [contract.sources[1]]
    r2.essential = False   # dropping ONE source of a multi-source role is a degrade,
                           # not an essential loss (the other source keeps the role alive)
    t2 = copy.deepcopy(t)
    t2.roles = [r2 if r.role == "TEMP_SENSORS" else r for r in t2.roles]
    plan = plan_drop(t2, st, ["TEMP_SENSORS"])
    check(plan.ok, f"plan ok ({len(plan.edits)} deletion)")
    if not plan.ok:
        print("       reason:", plan.reason)
        return
    res = apply_and_check(st, plan.edits)
    after = res.structure_after
    check(res.ok and not [d for d in after.devices if "TemperatureSensor" in d.tags],
          "TS loop gone")
    aq_iters = [d for d in after.devices if d.kind == "iter" and "AirQualitySensor" in d.tags]
    check(len(aq_iters) == 2, "AQ loops (temp + humid) survive")
    check(any(a.name == "temp_sum" for a in after.assigns), "temp_sum still written (no undefined survivor)")


def test_drop_purifier() -> None:
    print("\n[3] air_quality: drop PURIFIER (toast inside goes as collateral)")
    t, st = _tpl("air_quality")
    plan = plan_drop(t, st, ["PURIFIER"])
    check(plan.ok, f"plan ok ({len(plan.edits)} deletions)")
    if not plan.ok:
        print("       reason:", plan.reason)
        return
    res = apply_and_check(st, plan.edits)
    after = res.structure_after
    check(res.ok and not [d for d in after.devices if "AirPurifier" in d.tags],
          "purifier blocks gone")
    toasts = [d for d in after.devices if "ToastPublisher" in d.tags]
    check(len(toasts) == 1, f"CO2 warning toast survives, purifier toast went with its block ({len(toasts)} toast)")
    lights = [d for d in after.devices if "Light" in d.tags]
    check(len(lights) == len([d for d in st.devices if "Light" in d.tags]),
          "CO2 indicator untouched")
    fs = check_static(t, after, before=st, dropped_roles=["PURIFIER"])
    check(not [f for f in fs if f.severity == "blocking"], "static checks clean")


def test_escalations() -> None:
    print("\n[4] escalations fail closed")
    t, st = _tpl("thermo_comfort")
    plan = plan_drop(t, st, ["CLOCK"])
    check(not plan.ok and "essential" in plan.reason,
          f"dropping CLOCK refused: {plan.reason[:70]}")
    plan2 = plan_drop(t, st, ["TEMP_SENSORS"])
    check(not plan2.ok and "essential" in plan2.reason,
          f"dropping all TEMP_SENSORS refused: {plan2.reason[:70]}")


def test_static_value_edits() -> None:
    print("\n[5] static checks on value edits (the '25 -> 26' demo)")
    t, st = _tpl("thermo_comfort")
    slot_val = {"fine": "26.0", "band_invert": "24.0", "out_of_domain": "99"}

    def edit_max_summer(v: str):
        a = next(x for x in st.assigns if x.name == "max_temp_summer" and x.persistent)
        res = apply_and_check(st, [Edit(a.rhs_span, v, "ModifyPredicate", "max_temp_summer")])
        return res, check_static(t, res.structure_after)

    res, fs = edit_max_summer(slot_val["fine"])
    check(res.ok and not [f for f in fs if f.severity == "blocking"],
          "25.5 -> 26.0 accepted (syntactically and semantically)")
    res, fs = edit_max_summer(slot_val["band_invert"])
    bad = [f for f in fs if f.check == "band"]
    check(res.ok and bad, f"25.5 -> 24.0 re-parses fine but band check refuses: {bad[0].detail[:60] if bad else '-'}")
    res, fs = edit_max_summer(slot_val["out_of_domain"])
    bad = [f for f in fs if f.check == "domain"]
    check(res.ok and bad, f"25.5 -> 99 re-parses fine but domain check refuses: {bad[0].detail[:60] if bad else '-'}")


def test_end_to_end_degrade() -> None:
    print("\n[6] end to end: humidifier dies -> bind -> slice -> patch -> checks")
    t, st = _tpl("thermo_comfort")
    inv = base_office(); inv.set_online("hf1", False)
    rep = bind(t, st, inv)
    drops = [d.role for d in rep.decisions if d.action == "drop_feature"]
    check(rep.verdict == "degrade" and "HUMID_ACTUATOR" in drops,
          f"bind verdict degrade, drop set {sorted(set(drops))}")
    # HUMID_SENSORS stays bound (AQ alive) but its consumer feature is gone;
    # the feature-level drop is actuator+sensors of feature 'humidity_control'
    feature_roles = [r.role for r in t.roles if r.feature == "humidity_control"]
    plan = plan_drop(t, st, feature_roles)
    res = apply_and_check(st, plan.edits) if plan.ok else None
    check(plan.ok and res is not None and res.ok,
          f"feature drop applied ({len(plan.edits)} deletions)")
    if res is not None:
        fs = check_static(t, res.structure_after, before=st, dropped_roles=feature_roles)
        check(not [f for f in fs if f.severity == "blocking"], "post-drop static checks clean")
        print(f"       degraded scenario: {len(res.output)} chars "
              f"(from {len(st.src)}), report: 'humidity_control abandoned — humidifier offline'")


def main() -> int:
    test_drop_humidity()
    test_drop_one_temp_source()
    test_drop_purifier()
    test_escalations()
    test_static_value_edits()
    test_end_to_end_degrade()
    print(f"\n{'ALL PASS' if not _failures else str(len(_failures)) + ' FAILURES'}")
    for f in _failures:
        print("  -", f)
    return 1 if _failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
