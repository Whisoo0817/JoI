"""E4 grid generator: parametric (IR, binding, devices, JoI) pairs.

Four scale axes, all inside the supported fragment (no nested/parallel composition):
  W  input width  - how many BOOL sensors the guard reads   (input domain = 2**W)
  B  stages       - how many sequential wait->call stages    (program size / branching)
  T  wait length  - the timeout on each falling-edge wait    (ms)
  K  state memory - how many times the cycle body repeats    (cycle count)

Both sides are emitted from the same parameters, so EQUIV is the expected verdict;
that is the case that makes the Explorer do the full closure work.

Service and value names come from files/service_list_ver2.0.7.json, so every pair
is catalog-conformant (prepare_pair validates them).
"""

PERIOD_MS = 100

# (service category, BOOL value) - the guard reads these
SENSORS = [
    ("MotionSensor", "Motion"),
    ("ContactSensor", "Contact"),
    ("PresenceSensor", "Presence"),
    ("LeakSensor", "Leakage"),
    ("SmokeDetector", "Smoke"),
    ("Battery", "IsCharging"),
    ("PresenceVitalSensor", "Presence"),
]

# (service category, on function, off function) - one per stage
ACTUATORS = [
    ("Switch", "On", "Off"),
    ("DoorLock", "Unlock", "Lock"),
    ("Valve", "Open", "Close"),
    ("Camera", "StartRecording", "StopRecording"),
    ("WindowCovering", "UpOrOpen", "DownOrClose"),
    ("FaceRecognizer", "Start", "End"),
]

MAX_W, MAX_B = len(SENSORS), len(ACTUATORS)


def _ir_guard(w, value):
    return " and ".join(f"{s}.{v} == {value}" for s, v in SENSORS[:w])


def _joi_guard(w, value):
    return " and ".join(f"s{i} == {value}" for i in range(w))


def make_pair(w=1, b=1, t_ms=120000, k=1):
    """Return {"ir","binding","devices","joi","params"} for gate_pair."""
    if not (1 <= w <= MAX_W and 1 <= b <= MAX_B):
        raise ValueError(f"W must be 1..{MAX_W} and B must be 1..{MAX_B}")

    devices, binding = {}, {}
    for i, (svc, _) in enumerate(SENSORS[:w]):
        did = f"Sen{i}"
        devices[did] = {"category": [svc], "tags": [f"Sen{i}", svc]}
        binding[svc] = [did]
    for j, (svc, _, _) in enumerate(ACTUATORS[:b]):
        did = f"Act{j}"
        devices[did] = {"category": [svc], "tags": [f"Act{j}", svc]}
        binding[svc] = [did]

    body = []
    for j, (svc, on, off) in enumerate(ACTUATORS[:b]):
        body += [
            {"op": "wait", "cond": _ir_guard(w, "true"), "edge": "rising"},
            {"op": "call", "target": f"{svc}.{on}", "args": {}},
            {"op": "wait", "cond": _ir_guard(w, "false"), "edge": "none",
             "timeout": f"{t_ms} MSEC",
             "on_timeout": [{"op": "call", "target": f"{svc}.{off}", "args": {}},
                            {"op": "break"}]},
            {"op": "call", "target": f"{svc}.{off}", "args": {}},
        ]
    ir = {"timeline": [{"op": "start_at", "anchor": "now"},
                       {"op": "cycle", "until": None, "period": f"{PERIOD_MS} MSEC",
                        "count": k, "body": body}]}

    return {"cell_id": f"W{w}_B{b}_T{t_ms}_K{k}",
            "ir": ir, "binding": binding, "devices": devices,
            "joi": {"name": f"E4_W{w}B{b}T{t_ms}K{k}", "cron": "", "period": PERIOD_MS,
                    "script": _joi_script(w, b, t_ms, k)},
            "params": {"W": w, "B": b, "T_ms": t_ms, "K": k}}


def _joi_script(w, b, t_ms, k):
    """Explicit state machine mirroring the IR.

    `stage` picks the actuator, `phase` picks the wait half, and `prev` carries the
    guard's previous value so the rising-edge wait is encoded exactly (an `armed`
    flag only approximates it and breaks when the cycle wraps).
    The falling edge advances to the next stage and wraps the cycle `k` times; the
    timeout path fires the off call and then stops, which is what the IR's `break`
    does. Stage WRAP burns the one `period` the IR waits between iterations.
    """
    ticks = max(1, t_ms // PERIOD_MS)
    STOP, WRAP = 99, 90
    L = ["stage := 0", "phase := 0", "prev := false", "ticks := 0", "rounds := 0"]
    for i, (svc, val) in enumerate(SENSORS[:w]):
        L.append(f"s{i} = (#Sen{i} #{svc}).{val}")
    hi, lo = _joi_guard(w, "true"), _joi_guard(w, "false")
    for j, (svc, on, off) in enumerate(ACTUATORS[:b]):
        L.append(("if" if j == 0 else "} else if") + f" (stage == {j}) {{")
        L += [
            "    if (phase == 0) {",
            f"        if ({hi}) {{",
            "            if (prev == false) {",
            f"                (#Act{j} #{svc}).{on}()",
            "                phase = 1",
            "                ticks = 0",
            "            }",
            "        }",
            "    } else {",
            "        ticks = ticks + 1",
            f"        if ({lo}) {{",
            f"            (#Act{j} #{svc}).{off}()",
            "            phase = 0",
        ]
        if j + 1 < b:
            L.append(f"            stage = {j + 1}")
        else:
            L += ["            rounds = rounds + 1",
                  f"            if (rounds >= {k}) {{",
                  f"                stage = {STOP}",
                  "            } else {",
                  f"                stage = {WRAP}",
                  "            }"]
        L += [
            f"        }} else if (ticks >= {ticks}) {{",
            f"            (#Act{j} #{svc}).{off}()",
            f"            stage = {STOP}",
            "        }",
            "    }",
        ]
    if k > 1:
        L += [f"}} else if (stage == {WRAP}) {{", "    stage = 0", "    phase = 0"]
    L.append("}")
    L.append(f"prev = {hi}")
    return "\n".join(L)


# ── the grid ───────────────────────────────────────────────────────
# Base sits mid-scale so every axis has room to grow and to shrink.
BASE = {"w": 2, "b": 2, "t_ms": 120000, "k": 5}
AXES = {
    "W": ("w", [1, 2, 3, 4, 5, 6, 7]),
    "B": ("b", [1, 2, 3, 4, 5, 6]),
    "T": ("t_ms", [100, 1000, 10000, 120000, 1800000, 14400000]),
    "K": ("k", [1, 2, 5, 10, 20, 50, 100, 200]),
}
# All axes grow together - this is where the budget actually runs out.
DIAGONAL = [(1, 1, 1), (2, 2, 2), (3, 3, 5), (4, 4, 10), (5, 5, 20), (6, 6, 50), (7, 6, 100)]


def grid():
    """One-factor-at-a-time sweeps from BASE, plus a diagonal where all axes grow."""
    cells = []
    for axis, (key, levels) in AXES.items():
        for lv in levels:
            kw = dict(BASE, **{key: lv})
            cells.append({"axis": axis, "level": lv, "kw": kw,
                          "cell_id": make_pair(**kw)["cell_id"]})
    for w, b, k in DIAGONAL:
        kw = {"w": w, "b": b, "t_ms": BASE["t_ms"], "k": k}
        cells.append({"axis": "D", "level": f"{w}/{b}/{k}", "kw": kw,
                      "cell_id": make_pair(**kw)["cell_id"]})
    return cells


if __name__ == "__main__":
    g = grid()
    print(f"{len(g)} sweep points, {len(set(c['cell_id'] for c in g))} distinct programs")
    for c in g:
        print(f"  {c['axis']:<2} {str(c['level']):<10} {c['cell_id']}")
