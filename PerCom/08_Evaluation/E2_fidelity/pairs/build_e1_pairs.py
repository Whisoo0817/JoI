"""Build the frozen E2 pair set on the E1 20 base IRs.

~/temp/bin/python build_e1_pairs.py      (run from pairs/)

Inputs
- base IRs, bindings, devices, start times: E1 data files (Stage A `cases.py` + `irs.py`;
  depth v2 `depth_cases_v2.py` + `depth_attempts_v2.py`), read as data;
- JoI implementations and fault variants: `e1_pairs_src.py` (hand-written for E2).

Checks (the build fails otherwise)
- every fault replacement string occurs exactly the declared number of times in its correct script;
- every script (correct and faulty) parses with the ANTLR deployment grammar (lowering/parser/generated);
- a fault changes the script.

Output: `e1_pairs.json` (pairs + sha256 of this file, the source file and the E1 data files it read).
No reference, runner or Explorer is run here.
"""
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
E1 = ROOT / "PerCom/08_Evaluation/E1_adequacy"
DEPTH = E1 / "breadth/depth"
GEN = ROOT / "lowering/parser/generated"


def load(name, path, extra_path=None):
    if extra_path:
        sys.path.insert(0, str(extra_path))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def parse_errors(src):
    sys.path.insert(0, str(GEN))
    from antlr4 import CommonTokenStream, InputStream
    from antlr4.error.ErrorListener import ErrorListener
    from JOILangLexer import JOILangLexer
    from JOILangParser import JOILangParser

    class Collect(ErrorListener):
        def __init__(self):
            self.errors = []

        def syntaxError(self, recognizer, symbol, line, column, msg, e):
            self.errors.append(f"{line}:{column} {msg}")

    lexer = JOILangLexer(InputStream(src))
    parser = JOILangParser(CommonTokenStream(lexer))
    c = Collect()
    for x in (lexer, parser):
        x.removeErrorListeners()
        x.addErrorListener(c)
    parser.scenario()
    return c.errors


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    cases = load("e1_cases", E1 / "cases.py")
    irs = load("e1_irs", E1 / "irs.py")
    dcases = load("depth_cases_v2", DEPTH / "depth_cases_v2.py", DEPTH)
    dattempts = load("depth_attempts_v2", DEPTH / "depth_attempts_v2.py", DEPTH)
    src = load("e1_pairs_src", HERE / "e1_pairs_src.py")

    stage_a = {c["id"]: c for c in cases.CASES}
    depth = {c["id"]: c for c in dcases.CASES}

    pairs, problems = [], []
    for base in src.BASES:
        cid = base["case"]
        if cid in stage_a:
            c = stage_a[cid]
            ir = irs.IRS[cid]["ir"]
            binding, catalog = c["binding"], "files/service_list_ver2.0.7.json"
            t_start, cron = c["t_start_ms"], c["cron"]
            devices = copy.deepcopy(c["devices"])
        else:
            c = depth[cid]
            autos = {a["name"]: a for a in dattempts.ATTEMPTS[cid]["automations"]}
            ir = autos[base.get("automation", "main")]["ir"]
            binding = None  # depth IRs name devices in their atoms: Service[Device,...].Member
            catalog = "PerCom/08_Evaluation/E1_adequacy/breadth/depth/runs/fixture_catalog_v2.json"
            t_start, cron = c["t_start_ms"], ""
            devices = copy.deepcopy(c["devices"])
        for did, tags in base.get("retag", {}).items():
            devices[did]["tags"] = list(tags)
        block = {"name": base["id"], "cron": base.get("cron", cron), "period": base["period"],
                 "script": base["script"]}
        common = dict(base_case=cid, automation=base.get("automation", "main"), ir=ir, binding=binding,
                      devices=devices, catalog=catalog, t_start_ms=t_start, ir_cron=cron,
                      retag=base.get("retag", {}), joi_note=base.get("note", ""))
        errs = parse_errors(block["script"])
        if errs:
            problems.append(f"{base['id']} correct: parse errors {errs}")
        pairs.append(dict(pair_id=f"{base['id']}/correct", kind="correct", family=None,
                          description="correct implementation (author intent)", joi=block, **common))
        for i, f in enumerate(base["faults"], 1):
            fam, desc, old, new = f[:4]
            count = f[4] if len(f) > 4 else 1
            n = block["script"].count(old)
            if n != count:
                problems.append(f"{base['id']} fault {i} ({fam}): '{old[:40]}' occurs {n}x, expected {count}")
                continue
            script = block["script"].replace(old, new)
            if script == block["script"]:
                problems.append(f"{base['id']} fault {i}: no change")
                continue
            errs = parse_errors(script)
            if errs:
                problems.append(f"{base['id']} fault {i}: parse errors {errs}")
            pairs.append(dict(pair_id=f"{base['id']}/fault{i}", kind="fault", family=fam, description=desc,
                              change={"old": old, "new": new, "count": count},
                              joi={**block, "script": script}, **common))
    if problems:
        print("BUILD FAILED")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    inputs = [HERE / "build_e1_pairs.py", HERE / "e1_pairs_src.py", E1 / "cases.py", E1 / "irs.py",
              DEPTH / "depth_cases.py", DEPTH / "depth_cases_v2.py", DEPTH / "depth_attempts.py",
              DEPTH / "depth_attempts_v2.py", DEPTH / "runs/fixture_catalog_v2.json",
              ROOT / "files/service_list_ver2.0.7.json"]
    out = {"inputs_sha256": {str(p.relative_to(ROOT)): sha(p) for p in inputs},
           "n_pairs": len(pairs),
           "n_correct": sum(p["kind"] == "correct" for p in pairs),
           "n_fault": sum(p["kind"] == "fault" for p in pairs),
           "families": sorted({p["family"] for p in pairs if p["family"]}),
           "pairs": pairs}
    (HERE / "e1_pairs.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    from collections import Counter
    print(out["n_pairs"], "pairs:", out["n_correct"], "correct,", out["n_fault"], "faults")
    print(dict(Counter(p["family"] for p in pairs if p["family"])))


if __name__ == "__main__":
    main()
