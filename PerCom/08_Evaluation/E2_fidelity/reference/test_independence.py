"""Independence check (PROTOCOL_DRAFT §1.1): no reference module imports explorer / timeline_ir / lowering (except the
ANTLR-generated parser loaded from its own directory) / sensys / the E1 runner files, and no module refers to a
forbidden source path. Also checks sys.modules after importing the reference.

Run: ~/temp/bin/python test_independence.py
"""
import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FORBIDDEN_TOP = {"explorer", "timeline_ir", "lowering", "sensys", "run_e1", "run_depth", "run_depth_v2"}
ALLOWED_GENERATED = {"JOILangLexer", "JOILangParser", "JOILangListener", "JOILangVisitor"}
FORBIDDEN_PATH_FRAGMENTS = ["explorer/runtime", "explorer/verification", "explorer/analysis", "explorer/eval/",
                            "timeline_ir/timeline_ir", "timeline_ir/mapping", "timeline_ir/catalog",
                            "lowering/parser/validator", "lowering/run_", "sensys/", "run_e1.py", "run_depth"]


def scan(path):
    problems = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        for n in names:
            top = n.split(".")[0]
            if top in FORBIDDEN_TOP:
                problems.append(f"{path.name}:{node.lineno} imports {n}")
            if top == "lowering" and not n.startswith("lowering.parser.generated"):
                problems.append(f"{path.name}:{node.lineno} imports {n}")
        if isinstance(node, ast.Call) and getattr(node.func, "attr", getattr(node.func, "id", "")) in (
                "import_module", "__import__"):
            for a in node.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str) and a.value.split(".")[0] in FORBIDDEN_TOP:
                    problems.append(f"{path.name}:{node.lineno} dynamic import {a.value}")
        if path.name != Path(__file__).name and isinstance(node, ast.Constant) and isinstance(node.value, str):
            for frag in FORBIDDEN_PATH_FRAGMENTS:
                if frag in node.value.replace("\\", "/"):
                    problems.append(f"{path.name}:{node.lineno} string refers to {frag!r}")
    return problems


def main():
    problems = []
    files = sorted(HERE.glob("*.py"))
    for f in files:
        problems += scan(f)
    sys.path.insert(0, str(HERE))
    import run  # noqa: F401
    import ir_ref  # noqa: F401
    import joi_ref  # noqa: F401
    for mod in list(sys.modules):
        top = mod.split(".")[0]
        if top in FORBIDDEN_TOP:
            problems.append(f"sys.modules contains {mod}")
        if top.startswith("JOILang") and top not in ALLOWED_GENERATED:
            problems.append(f"unexpected generated module {mod}")
    for name in ("JOILangParser", "JOILangLexer"):
        gen = sys.modules.get(name)
        expected = str(HERE / "grammar")
        if gen is None or not str(getattr(gen, "__file__", "")).startswith(expected):
            problems.append(f"{name} not loaded from {expected}: {getattr(gen, '__file__', None)}")
    g4 = (HERE / "grammar" / "JOILang.g4").read_text(encoding="utf-8")
    if "MODULO" not in g4:
        problems.append("reference/grammar/JOILang.g4 lacks the `%` (MODULO) author extension")
    for f in sorted((HERE / "grammar").glob("*.py")):   # generated files: only antlr4 / stdlib imports
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            mods = [a.name for a in node.names] if isinstance(node, ast.Import) else (
                [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            for m in mods:
                if m.split(".")[0] not in {"antlr4", "io", "sys", "typing", "JOILangParser", "JOILangListener", ""}:
                    problems.append(f"grammar/{f.name} imports {m}")
    print(f"scanned {len(files)} files: {[f.name for f in files]} + grammar/*.py")
    if problems:
        print("FAIL")
        for p in problems:
            print("  ", p)
        raise SystemExit(1)
    print("PASS: no forbidden imports or path references")


if __name__ == "__main__":
    main()
