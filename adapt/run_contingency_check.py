"""M-E evidence run: contingency tables — exhaustive offline, lookup at runtime.

Asserts, over the real templates + base-office inventory:

1. **exhaustive**   — every (template x device instance) has a row; the action
   histogram is printed (no silent caps).
2. **intrusion 4-role prototype** — toast dead -> abort (an intrusion scenario
   that cannot alert is purpose-dead); speaker dead -> redeploy without the
   spoken notice; camera dead -> redeploy dropping the WHOLE evidence closure
   (camera + email — dropping the camera alone would leave the email reading an
   undefined `video`; the closure rule handles it) while the [긴급] toast
   survives; email dead -> same closure artifact.
3. **source-level cuts** — thermo: AQ dead cuts both its loops but keeps the TS
   and HS loops feeding the averages; TS dead cuts one loop only.
4. **artifact validity** — every redeploy artifact re-parses and contains no
   reference to the dead device type (for single-instance types).
5. **runtime path** — save to disk, reload, lookup: mean latency measured over
   10k lookups (the ms-claim of contingency compilation); a stale table (source
   hash changed) raises instead of deploying an outdated artifact.

    python3 -m adapt.run_contingency_check
"""

from __future__ import annotations

import json
import os
import time

from .contingency import StaleTable, Table, compile_table, save_table, TABLE_DIR
from .inventory import base_office
from .structure import extract, parse_errors
from .template import list_templates, load_template

_failures: list[str] = []


def check(cond: bool, label: str) -> bool:
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        _failures.append(label)
    return cond


def main() -> int:
    inv = base_office()
    tables: dict[str, Table] = {}

    print("[compile] all templates x all devices")
    t_all0 = time.perf_counter()
    for tid in list_templates():
        tables[tid] = compile_table(load_template(tid), inv)
    total_ms = (time.perf_counter() - t_all0) * 1000
    n_rows = sum(len(tb.rows) for tb in tables.values())
    hist: dict[str, int] = {}
    for tb in tables.values():
        for r in tb.rows.values():
            hist[r.action] = hist.get(r.action, 0) + 1
    check(n_rows == len(tables) * len(inv.devices),
          f"exhaustive: {n_rows} rows = {len(tables)} templates x {len(inv.devices)} devices "
          f"in {total_ms:.0f} ms offline")
    print(f"       actions: {dict(sorted(hist.items()))}")
    check(hist.get("escalate", 0) == 0,
          f"no escalations on this corpus+inventory (holes would be reported, not hidden)")

    print("\n[intrusion_alert] the 4-role prototype")
    tb = tables["intrusion_alert"]
    check(tb.rows["tp1"].action == "abort",
          f"toast dead -> abort ({tb.rows['tp1'].notice[:40]}...)")
    sp = tb.rows["sp1"]
    check(sp.action == "redeploy" and sp.dropped_features == ["voice_notice"]
          and "speaker" not in (sp.artifact or "").lower(),
          "speaker dead -> redeploy, spoken notice dropped")
    cam = tb.rows["cam1"]
    check(cam.action == "redeploy" and cam.dropped_features == ["evidence"]
          and "camera" not in (cam.artifact or "").lower()
          and "emailProvider" not in (cam.artifact or ""),
          "camera dead -> evidence closure dropped (camera AND email)")
    check("[긴급] 침입 의심" in (cam.artifact or ""),
          "…while the [긴급] alert toast — the scenario's purpose — survives")
    em = tb.rows["em1"]
    check(em.action == "redeploy" and em.artifact == cam.artifact,
          "email dead -> same closure artifact (deterministic)")

    print("\n[thermo_comfort] source-level cuts")
    tb = tables["thermo_comfort"]
    aq = tb.rows["aq1"]
    ok = aq.action == "redeploy" and "AirQualitySensor" not in (aq.artifact or "")
    if ok:
        after = extract(aq.artifact, "aq-dead")
        iters = [(d.tags[0], d.member) for d in after.devices if d.kind == "iter"]
        ok = ("TemperatureSensor", "temperatureSensor_temperature") in iters \
            and ("HumiditySensor", "humiditySensor_humidity") in iters \
            and any(a.name == "temp_sum" for a in after.assigns)
    check(ok, f"AQ dead -> both its loops cut, TS+HS loops keep feeding the averages "
              f"({aq.artifact_bytes}B)")
    ts = tb.rows["ts1"]
    check(ts.action == "redeploy" and (ts.artifact or "").count("for (") == 3,
          f"TS dead -> exactly one loop cut (4 -> {(ts.artifact or '').count('for (')})")
    check(tb.rows["ac1"].action == "abort", "AC dead -> abort (no substitute in this home)")

    print("\n[artifacts] every redeploy artifact is deployable")
    bad = 0
    single_instance_types = {d.type for d in inv.devices
                             if sum(1 for x in inv.devices if x.type == d.type) == 1}
    for tid, tb in tables.items():
        for dev_id, row in tb.rows.items():
            if row.action != "redeploy":
                continue
            errs = parse_errors(row.artifact or "")
            dead_type = row.device_type
            dangling = dead_type in (row.artifact or "") and dead_type in single_instance_types
            if errs or dangling:
                bad += 1
                print(f"       !! {tid}/{dev_id}: errs={errs[:1]} dangling={dangling}")
    check(bad == 0, f"all {hist.get('redeploy', 0)} artifacts re-parse, no dangling dead-type refs")

    print("\n[runtime] save -> reload -> lookup latency + staleness")
    for tb in tables.values():
        save_table(tb)
    path = os.path.join(TABLE_DIR, "intrusion_alert.json")
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    check(raw["base_hash"] == tables["intrusion_alert"].base_hash and len(raw["rows"]) == len(inv.devices),
          f"table persisted ({os.path.getsize(path)} B on disk)")

    tb = tables["intrusion_alert"]
    good_hash = tb.base_hash
    n = 10_000
    t0 = time.perf_counter()
    for i in range(n):
        row = tb.lookup("cam1", good_hash)
    dt_us = (time.perf_counter() - t0) / n * 1e6
    check(row.action == "redeploy" and dt_us < 1000,
          f"lookup mean {dt_us:.1f} µs over {n} calls -> runtime response is table lookup + deploy")

    try:
        tb.lookup("cam1", "0" * 64)
        check(False, "stale table detected")
    except StaleTable as e:
        check(True, f"stale table refused ({str(e)[:50]}...)")

    unknown = tb.lookup("nonexistent", good_hash)
    check(unknown.action == "keep", "unknown device -> keep (scenario unaffected)")

    print(f"\n{'ALL PASS' if not _failures else str(len(_failures)) + ' FAILURES'}")
    for f in _failures:
        print("  -", f)
    return 1 if _failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
