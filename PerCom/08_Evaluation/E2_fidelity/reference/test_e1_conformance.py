"""E1 conformance of the independent reference against human-written expected ACTION traces.

1. Stage A: cases.py expected traces x irs.py IRs (12 cases, 41 histories), global catalog; ordered comparison,
   exact time and 1 s tolerance (cases.py header).
2. Depth v2: depth_cases_v2.py x depth_attempts_v2.py (8 cases, 12 histories), fixture_catalog_v2.json; rules T1–T7
   of depth_cases.py (T5 multiset comparison, NUM_EPS, T7 fault injection).
3. JoI blocks contained in the E1 files (E1-092 v2 deployment, E1-095 v1 JoI v3 block) on their case histories.
4. JoI probe pairs copied as data from the hand-computed probe file (15 pairs + 3 program-mutation controls).

The E1 data modules are loaded as data after an `ast` check that they import nothing but `copy`, `json`, `pathlib`,
`hashlib`, `depth_cases`, `depth_attempts`. Writes conformance_results.json and CONFORMANCE.md.
Run: ~/temp/bin/python test_e1_conformance.py
"""
import ast
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True           # never write .pyc next to the E1 data files

from common import REPO, val_eq          # noqa: E402
from run import run_ir, run_joi          # noqa: E402

E1 = REPO / "PerCom" / "08_Evaluation" / "E1_adequacy"
DEPTH = E1 / "breadth" / "depth"
FIXTURE_V2 = DEPTH / "runs" / "fixture_catalog_v2.json"
DATA_IMPORTS_ALLOWED = {"copy", "json", "pathlib", "hashlib", "depth_cases", "depth_attempts"}


def check_data_imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        mods = []
        if isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            mods = [node.module or ""]
        for m in mods:
            if m.split(".")[0] not in DATA_IMPORTS_ALLOWED:
                raise SystemExit(f"{path} imports {m}; not loading it as data")


def load(path, name):
    check_data_imports(path)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ───────────────────────────── comparisons ─────────────────────────────
def _sig(a, e, eps=0.0):
    return (a[1] == e[1] and a[3] == e[3] and len(a[2]) == len(e[2])
            and all(val_eq(x, y, eps) for x, y in zip(a[2], e[2])))


def flat(res):
    return [(t, f"{s}.{m}", list(args), d) for (t, s, m, args, d) in res["raw_actions"]]


def ordered_compare(actual, expected, tol):
    """Stage A: same signatures in the same order; exact = equal times; tolerance = |dt| <= tol."""
    if len(actual) != len(expected):
        return False, False, f"count {len(actual)} != expected {len(expected)}"
    exact = within = True
    first = None
    for i, (a, e) in enumerate(zip(actual, expected)):
        if not _sig(a, e):
            return False, False, f"#{i} signature {a} != expected {e}"
        if a[0] != e[0]:
            exact = False
            first = first or f"#{i} time {a[0]} != expected {e[0]}"
            if abs(a[0] - e[0]) > tol:
                within = False
    return exact, within, first


def multiset_compare(actual, expected, tol, eps):
    """Depth rule T5: multiset of signatures; exact = equal (time, signature) multisets; tolerance = distinct pairing."""
    if len(actual) != len(expected):
        return False, False, f"count {len(actual)} != expected {len(expected)}"
    rem = list(actual)
    exact = True
    for e in expected:
        idx = next((i for i, a in enumerate(rem) if a[0] == e[0] and _sig(a, e, eps)), None)
        if idx is None:
            exact = False
            break
        rem.pop(idx)
    rem = list(actual)
    within = True
    first = None
    for e in sorted(expected, key=lambda x: x[0]):
        cands = [(abs(a[0] - e[0]), i) for i, a in enumerate(rem) if _sig(a, e, eps) and abs(a[0] - e[0]) <= tol]
        if not cands:
            within = False
            first = f"no match for expected {e}"
            break
        rem.pop(min(cands)[1])
    if not exact and first is None:
        first = "times differ within tolerance"
    return exact, within, first


# ───────────────────────────── probe pairs (copied data) ─────────────────────────────
PROBE_DEVICES = {
    "lamp": {"category": ["Switch"], "tags": ["Lamp"]},
    "input": {"category": ["Switch"], "tags": ["Input"]},
    "weather": {"category": ["WeatherProvider"], "tags": ["Weather"]},
    "speaker": {"category": ["Speaker"], "tags": ["Speaker"]},
}
ON = "(#Lamp).switch_on()"
OFF = "(#Lamp).switch_off()"
INPUT = "(#Input).switch_switch"
QUERY = "(#Weather).weatherProvider_forecast(3)"
BRANCH = "if (x == true) { " + ON + " } else { " + OFF + " }"


def pa(t, method, args=(), target="lamp", service="switch"):
    return {"t_ms": t, "service": service, "method": method, "args": list(args), "target": [target]}


PROBES = [
    dict(id="delay_150", period=0, horizon_ms=300, script=ON + "\ndelay(150 MSEC)\n" + OFF,
         inputs=[[0, {}]], expected=[pa(0, "on"), pa(150, "off")]),
    dict(id="period_after_completion", period=1000, horizon_ms=2500, script=ON + "\ndelay(150 MSEC)\n" + OFF,
         inputs=[[0, {}]], expected=[pa(0, "on"), pa(150, "off"), pa(1150, "on"), pa(1300, "off"), pa(2300, "on"),
                                     pa(2450, "off")]),
    dict(id="wait_preserves_continuation", period=1000, horizon_ms=1400,
         script=ON + "\nwait until(" + INPUT + " == true)\n" + OFF,
         inputs=[[0, {"input.switch": False}], [300, {"input.switch": True}]],
         expected=[pa(0, "on"), pa(300, "off"), pa(1300, "on"), pa(1300, "off")]),
    dict(id="nested_delay_keeps_branch", period=0, horizon_ms=300,
         script="if (" + INPUT + " == true) {\n" + ON + "\ndelay(150 MSEC)\n" + OFF + "\n}",
         inputs=[[0, {"input.switch": True}], [100, {"input.switch": False}]], expected=[pa(0, "on"), pa(150, "off")]),
    dict(id="input_at_delay_expiry", period=0, horizon_ms=300, script="delay(200 MSEC)\nx = " + INPUT + "\n" + BRANCH,
         inputs=[[0, {"input.switch": True}], [200, {"input.switch": False}]], expected=[pa(200, "off")]),
    dict(id="zero_delay", period=0, horizon_ms=100, script=ON + "\ndelay(0 MSEC)\n" + OFF,
         inputs=[[0, {}]], expected=[pa(0, "on"), pa(0, "off")]),
    dict(id="break_absorbs", period=100, horizon_ms=300, script=ON + "\nbreak\n" + OFF,
         inputs=[[0, {}]], expected=[pa(0, "on")]),
    dict(id="initial_value_persists", period=100, horizon_ms=200, script="x := " + INPUT + "\n" + BRANCH,
         inputs=[[0, {"input.switch": True}], [100, {"input.switch": False}]],
         expected=[pa(0, "on"), pa(100, "on"), pa(200, "on")]),
    dict(id="edge_latch", period=100, horizon_ms=400,
         script="fired := false\nif (" + INPUT + " == true) {\n"
                "if (fired == false) {\n" + ON + "\nfired = true\n}\n"
                "} else { fired = false }",
         inputs=[[0, {"input.switch": True}], [200, {"input.switch": False}], [300, {"input.switch": True}]],
         expected=[pa(0, "on"), pa(300, "on")]),
    dict(id="query_same_snapshot", period=0, horizon_ms=100,
         script="a = " + QUERY + "\nb = " + QUERY + "\n" 'if (a == "rain" and b == "rain") { ' + ON + " }",
         inputs=[[0, {"weather.forecast(3)": "rain"}]], expected=[pa(0, "on")]),
    dict(id="query_after_delay", period=0, horizon_ms=300,
         script="a = " + QUERY + "\ndelay(150 MSEC)\nb = " + QUERY + "\n"
                'if (a == "rain" and b == "clear") { (#Speaker).speaker_speak(b) }',
         inputs=[[0, {"weather.forecast(3)": "rain"}], [100, {"weather.forecast(3)": "clear"}]],
         expected=[pa(150, "speak", ["clear"], "speaker", "speaker")]),
    dict(id="missing_query", period=0, horizon_ms=100,
         script="w = " + QUERY + '\nif (w == "rain") { ' + ON + " } else { " + OFF + " }",
         inputs=[[0, {"weather.forecast(3)": None}]], expected=[pa(0, "off")]),
    dict(id="effectful_return_refused", period=0, horizon_ms=0, script="x = (#Lamp).switch_toggle()",
         inputs=[[0, {}]], expected_refusal=True),
    dict(id="initializer_after_delay", period=100, horizon_ms=400,
         script="delay(150 MSEC)\nx := " + INPUT + "\n" + BRANCH,
         inputs=[[0, {"input.switch": True}], [100, {"input.switch": False}]], expected=[pa(150, "off"), pa(400, "off")]),
    dict(id="initializer_in_late_branch", period=100, horizon_ms=300,
         script="if (" + INPUT + " == true) { x := true }\n" + BRANCH,
         inputs=[[0, {"input.switch": False}], [100, {"input.switch": True}]],
         expected=[pa(0, "off"), pa(100, "off"), pa(200, "off"), pa(300, "off")]),
]
PROBE_CONTROLS = [("delay_150", "150 MSEC", "200 MSEC"),
                  ("wait_preserves_continuation", "wait until(" + INPUT + " == true)\n" + OFF,
                   "if (" + INPUT + " == true) { " + OFF + " }"),
                  ("initial_value_persists", ":=", "=")]


def probe_run(p, script=None):
    block = {"script": script or p["script"], "period": p["period"], "cron": ""}
    return run_joi(block, PROBE_DEVICES, [(t, u) for t, u in p["inputs"]], p["horizon_ms"])


def probe_match(res, expected):
    actual = [dict(t_ms=t, service=s.lower(), method=m.lower(), args=list(a), target=[d])
              for (t, s, m, a, d) in res["raw_actions"]]
    if len(actual) != len(expected):
        return False, actual
    for a, e in zip(actual, expected):
        if (a["t_ms"] != e["t_ms"] or a["service"] != e["service"].lower() or a["method"] != e["method"].lower()
                or a["target"] != e["target"] or len(a["args"]) != len(e["args"])
                or not all(val_eq(x, y) for x, y in zip(a["args"], e["args"]))):
            return False, actual
    return True, actual


# ───────────────────────────── main ─────────────────────────────
def stage_a():
    cases = load(E1 / "cases.py", "e1_cases")
    irs = load(E1 / "irs.py", "e1_irs")
    rows = []
    for c in cases.CASES:
        ir = irs.IRS[c["id"]]["ir"]
        for h in c["histories"]:
            res = run_ir(ir, c["binding"], c["devices"], h["events"], h["horizon"], None, c["t_start_ms"], c["cron"])
            act = flat(res)
            if res["status"] == "ok":
                exact, within, diff = ordered_compare(act, h["expected"], cases.TOLERANCE_MS)
            else:
                exact = within = False
                diff = res["detail"]
            rows.append(dict(case=c["id"], history=h["name"], status=res["status"], detail=res["detail"],
                             exact=exact, within_tolerance=within, first_difference=diff,
                             actual=act, expected=[list(e) for e in h["expected"]]))
    return rows


def depth_v2():
    sys.path.insert(0, str(DEPTH))
    for f in ("depth_cases.py", "depth_attempts.py"):
        check_data_imports(DEPTH / f)
    dc1 = load(DEPTH / "depth_cases.py", "depth_cases")
    dc2 = load(DEPTH / "depth_cases_v2.py", "depth_cases_v2")
    da1 = load(DEPTH / "depth_attempts.py", "depth_attempts")
    da2 = load(DEPTH / "depth_attempts_v2.py", "depth_attempts_v2")
    ir_rows, joi_rows = [], []
    for c in dc2.CASES:
        autos = da2.ATTEMPTS[c["id"]]["automations"]
        for h in c["histories"]:
            faults = h.get("faults")
            merged, statuses, details = [], [], []
            for a in autos:
                res = run_ir(a["ir"], {}, c["devices"], h["events"], h["horizon"], str(FIXTURE_V2),
                             c["t_start_ms"], "", faults=faults)
                statuses.append(res["status"])
                details.append(res["detail"])
                merged += flat(res)
            merged.sort(key=lambda x: x[0])
            ok = all(s == "ok" for s in statuses)
            if ok:
                exact, within, diff = multiset_compare(merged, h["expected"], dc1.TOLERANCE_MS, dc1.NUM_EPS)
            else:
                exact = within = False
                diff = " | ".join(d for d in details if d)
            ir_rows.append(dict(case=c["id"], history=h["name"], automations=[a["name"] for a in autos],
                                status="ok" if ok else ",".join(statuses), detail=" | ".join(d for d in details if d),
                                exact=exact, within_tolerance=within, first_difference=diff,
                                actual=merged, expected=[list(e) for e in h["expected"]]))
        # JoI blocks present in the E1 files
        blocks = [a["joi"] for a in autos if a.get("joi")]
        source = "depth_attempts_v2 automations"
        if not blocks and "joi" in da1.ATTEMPTS.get(c["id"], {}):
            blocks = da1.ATTEMPTS[c["id"]]["joi"]["blocks"]
            source = "depth_attempts (v1) joi.blocks"
        if blocks:
            for h in c["histories"]:
                merged, statuses, details = [], [], []
                for b in blocks:
                    res = run_joi(b, c["devices"], h["events"], h["horizon"], str(FIXTURE_V2), c["t_start_ms"],
                                  faults=h.get("faults"))
                    statuses.append(res["status"])
                    details.append(res["detail"])
                    merged += flat(res)
                merged.sort(key=lambda x: x[0])
                ok = all(s == "ok" for s in statuses)
                if ok:
                    exact, within, diff = multiset_compare(merged, h["expected"], dc1.TOLERANCE_MS, dc1.NUM_EPS)
                else:
                    exact = within = False
                    diff = " | ".join(d for d in details if d)
                joi_rows.append(dict(case=c["id"], history=h["name"], source=source,
                                     blocks=[b.get("name") for b in blocks],
                                     status="ok" if ok else ",".join(statuses),
                                     detail=" | ".join(d for d in details if d), exact=exact, within_tolerance=within,
                                     first_difference=diff, actual=merged, expected=[list(e) for e in h["expected"]]))
    return ir_rows, joi_rows


def probes():
    rows = []
    for p in PROBES:
        res = probe_run(p)
        if p.get("expected_refusal"):
            passed = res["status"] == "unsupported"
            actual = res["detail"]
        else:
            passed, actual = probe_match(res, p["expected"]) if res["status"] == "ok" else (False, res["detail"])
        rows.append(dict(id=p["id"], status=res["status"], detail=res["detail"], passed=passed, actual=actual,
                         expected=p.get("expected", "REFUSED")))
    controls = []
    for pid, old, new in PROBE_CONTROLS:
        base = next(p for p in PROBES if p["id"] == pid)
        res = probe_run(base, base["script"].replace(old, new))
        same = res["status"] == "ok" and probe_match(res, base["expected"])[0]
        controls.append(dict(id=pid, replacement=[old, new], status=res["status"],
                             detected=(res["status"] == "ok" and not same)))
    return rows, controls


ANALYSIS = {       # written by the reference author after reviewing mismatches (text only; never changes the reference)
    "E1-095 JoI block (depth_attempts.py, JoI v3) — REF-UNSUPPORTED, not a trace disagreement": (
        "The block writes `(#Pool_Report #Pool).ReportDailyQuality(...)`. In depth_cases.py the device is "
        "`dev(\"Pool_Report\", \"Pool\", \"Pool\")`, i.e. tags `[\"Pool\", \"Pool\"]`; `Pool_Report` is the device ID, "
        "not a tag. JOI_SPEC §1.3: \"Multi-tag `(#A #B)`: Intersection — one device carrying BOTH tags\"; FRONTEND §3: "
        "\"태그 집합 T의 매칭 결과를 고정 inventory 순서의 장치 열 B(T)\". No text says a device ID or category matches "
        "a tag, so the reference matches `tags` only (SPEC_GAPS G1) and finds no device. The IR encoding of the same "
        "case matches exactly. Decision left to the author: either the block's selector or G1."),
}


def md_table(rows, keys):
    out = ["| " + " | ".join(keys) + " |", "|" + "---|" * len(keys)]
    for r in rows:
        out.append("| " + " | ".join(str(r.get(k, "")).replace("|", "\\|").replace("\n", " ")[:160] for k in keys) + " |")
    return "\n".join(out)


def main():
    a = stage_a()
    d_ir, d_joi = depth_v2()
    p, ctrl = probes()
    summary = dict(
        stage_a=dict(histories=len(a), exact=sum(r["exact"] for r in a), within_tolerance=sum(r["within_tolerance"] for r in a),
                     not_ok=sum(r["status"] != "ok" for r in a)),
        depth_v2_ir=dict(histories=len(d_ir), exact=sum(r["exact"] for r in d_ir),
                         within_tolerance=sum(r["within_tolerance"] for r in d_ir),
                         not_ok=sum(r["status"] != "ok" for r in d_ir)),
        e1_joi_blocks=dict(histories=len(d_joi), exact=sum(r["exact"] for r in d_joi),
                           within_tolerance=sum(r["within_tolerance"] for r in d_joi),
                           not_ok=sum(r["status"] != "ok" for r in d_joi)),
        joi_probe_pairs=dict(pairs=len(p), passed=sum(r["passed"] for r in p)),
        probe_mutation_controls=dict(controls=len(ctrl), detected=sum(c["detected"] for c in ctrl)),
    )
    out = dict(summary=summary, stage_a=a, depth_v2_ir=d_ir, e1_joi_blocks=d_joi, joi_probe_pairs=p,
               probe_mutation_controls=ctrl)
    (HERE / "conformance_results.json").write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str),
                                                    encoding="utf-8")
    lines = ["# CONFORMANCE — independent reference vs E1 human-written expected traces", "",
             "Generated by `test_e1_conformance.py` (details in `conformance_results.json`). The reference was not tuned "
             "to these results; disagreements are reported below with the specification text.", "",
             "## Summary", "", "```", json.dumps(summary, indent=1), "```", "",
             "## Stage A (IR reference, 41 histories, ordered comparison, tolerance 1 s)", "",
             md_table(a, ["case", "history", "status", "exact", "within_tolerance", "first_difference"]), "",
             "## Depth v2 (IR reference, 12 histories, rule T5 multiset, T7 faults)", "",
             md_table(d_ir, ["case", "history", "status", "exact", "within_tolerance", "first_difference"]), "",
             "## JoI blocks contained in the E1 files (JoI reference)", "",
             md_table(d_joi, ["case", "history", "source", "status", "exact", "within_tolerance", "first_difference"]), "",
             "## JoI probe pairs (copied from the hand-computed probe file)", "",
             md_table(p, ["id", "status", "passed", "detail"]), "",
             "Program-mutation controls (detected = ran and differed from the base expected trace):", "",
             md_table(ctrl, ["id", "status", "detected"]), ""]
    if ANALYSIS:
        lines += ["## Mismatch analysis", ""]
        for k, v in ANALYSIS.items():
            lines += [f"### {k}", "", v, ""]
    (HERE / "CONFORMANCE.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
