"""Input-use certificates for the grounded JoI / compiled IR fragment.

The certificate describes a model, not a discovered physical sensor type.
See INPUT_COVERAGE.md for the domains and the trace-preservation argument.
"""
from dataclasses import dataclass, field
from fractions import Fraction
import itertools
import math

from explorer.runtime import expr as e
from explorer.runtime import joi_parser as jp
from explorer.runtime.expr import canonical_key
from explorer.runtime.interp import Unsupported, world_key
from explorer.verification.state_key import freeze_state

CMP = {"==", "!=", "<", ">", "<=", ">="}
MIRROR = {"<": ">", ">": "<", "<=": ">=", ">=": "<=", "==": "==", "!=": "!="}


def unique(values):
    return list({freeze_state(v): v for v in values}.values())


def predicate_value(op, value, constant):
    if op == "truth":
        return bool(value)
    if op == "==":
        return value == constant
    if op == "!=":
        return value != constant
    if value is None or constant is None:
        return False
    return {"<": lambda: value < constant, ">": lambda: value > constant,
            "<=": lambda: value <= constant, ">=": lambda: value >= constant}[op]()


def representatives(predicates):
    """Joint truth-vector partition; never overwrite a type's predicates.

    Ordered numeric guards propose nullable numeric inputs, ordered string
    guards nullable strings. Equality/truth alone use all scalar types.
    Mixed order types or large numeric thresholds require an explicit model.
    """
    order_types = {"string" if isinstance(c, str) else "numeric"
                   for op, c in predicates if op in ("<", ">", "<=", ">=") and c is not None}
    if len(order_types) > 1:
        raise ValueError("mixed numeric/string ordering requires an explicit input domain")
    family = next(iter(order_types), "scalar")
    numbers = [c for _, c in predicates if isinstance(c, (int, float))]
    string_constants = [c for _, c in predicates if isinstance(c, str)]
    if (family == "numeric" and string_constants) or (family == "string" and numbers):
        raise ValueError("mixed comparison types require an explicit input domain")
    if any(abs(c) > 10**12 or not math.isfinite(c) for c in numbers):
        raise ValueError("numeric threshold outside certified automatic range; explicit input domain required")
    numeric = [0.0, 1.0]
    for c in numbers:
        base = (Fraction(c) * 10).__floor__()
        numeric.extend(n / 10 for n in (base - 1, base, base + 1))
    strings = string_constants
    # s + NUL is the immediate successor of s in finite-string lexicographic
    # order. Together with the minimum "", these witness every nonempty cell.
    strings = [""] + strings + [s + "\0" for s in [""] + strings]
    candidates = [None]
    if family != "string":
        candidates += [False, True] + numeric
    if family != "numeric":
        candidates += strings
    by_vector = {}
    for value in unique(candidates):
        vector = tuple(predicate_value(op, value, c) for op, c in predicates)
        by_vector.setdefault(vector, value)
    return list(by_vector.values()), family


@dataclass
class Coverage:
    predicates: dict = field(default_factory=dict)
    exact: set = field(default_factory=set)
    writes: set = field(default_factory=set)
    errors: list = field(default_factory=list)

    def require(self, key):
        if key.startswith("clock.") and key[6:] not in {"hour", "minute", "weekday", "isholiday", "timestamp", "time"}:
            self.errors.append("unmodeled clock input: " + key)
            return
        if key.startswith("clock.") and key != "clock.isholiday":
            return
        self.predicates.setdefault(key, [])

    def add(self, key, op, constant=None):
        self.require(key)
        if key in self.predicates:
            self.predicates[key] = unique(self.predicates[key] + [(op, constant)])


class Collector:
    def __init__(self, definitions, expressions, actions, writes=()):
        self.definitions = definitions
        self.expressions = expressions
        self.actions = actions
        self.coverage = Coverage(writes=set(writes))

    def leaves(self, node, visiting=frozenset()):
        tag = node[0]
        if tag in ("read", "lit"):
            return [node]
        if tag == "var":
            name = node[1]
            if name in visiting:
                return []
            # Unset reads are None. All assignments (including := and branch
            # assignments) are possible sources; control order only refines it.
            out = [("lit", None)]
            for rhs in self.definitions.get(name, ()):
                out += self.leaves(rhs, visiting | {name})
            return out
        if tag == "bool":
            return [("lit", False), ("lit", True)]
        return [("computed", tuple(sorted(self.sources(node))))]

    def sources(self, node, visiting=frozenset()):
        if node[0] == "read":
            return {node[1]}
        if node[0] == "var":
            if node[1] in visiting:
                return set()
            return set().union(*(self.sources(rhs, visiting | {node[1]})
                                 for rhs in self.definitions.get(node[1], ())))
        if node[0] == "lit":
            return set()
        return set().union(*(self.sources(child, visiting) for child in node[2]))

    def compare(self, left, right, op):
        for a, b in itertools.product(self.leaves(left), self.leaves(right)):
            if a[0] == "read" and b[0] == "lit":
                self.coverage.add(a[1], op, b[1])
            elif b[0] == "read" and a[0] == "lit":
                self.coverage.add(b[1], MIRROR[op], a[1])
            elif a[0] != "lit" or b[0] != "lit":
                # Relations between independently captured raw values cannot
                # be represented by independent one-dimensional partitions.
                for leaf in (a, b):
                    if leaf[0] == "read":
                        self.coverage.exact.add(leaf[1])
                    elif leaf[0] == "computed":
                        self.coverage.exact.update(leaf[1])

    def visit(self, node, truth=False):
        tag = node[0]
        for key in self.sources(node):
            self.coverage.require(key)
        if truth:
            for leaf in self.leaves(node):
                if leaf[0] == "read":
                    self.coverage.add(leaf[1], "truth")
                elif leaf[0] == "computed":
                    self.coverage.exact.update(leaf[1])
        if tag in ("read", "var", "lit"):
            return
        op, children = node[1], node[2]
        if op in CMP:
            self.compare(children[0], children[1], op)
        for child in children:
            self.visit(child, op in ("and", "or", "not"))
        if tag == "computed":
            # Conservatively require exact inputs even for dead computations:
            # arithmetic, string conversion and functions may distinguish cells.
            self.coverage.exact.update(self.sources(node))

    def run(self):
        for rhs_list in self.definitions.values():
            for rhs in rhs_list:
                self.visit(rhs)
        for node, truth in self.expressions:
            self.visit(node, truth)
        for node in self.actions:
            self.visit(node)
            self.coverage.exact.update(self.sources(node))
        self.coverage.exact.intersection_update(self.coverage.predicates)
        return self.coverage


def joi_coverage(stmts):
    from explorer.analysis.predicates import walk_stmts, stmt_exprs
    from explorer.analysis.explore import _read_key
    definitions, expressions, actions, writes, errors = {}, [], [], set(), []
    all_stmts = list(walk_stmts(stmts))

    def convert(node, statement_call=False):
        key = _read_key(node)
        if key is not None:
            return ("read", key)
        if isinstance(node, e.Lit):
            return ("lit", node.value)
        if isinstance(node, e.VarRef):
            # Match evaluate's live dotted-name fallback. A possibly assigned
            # dotted name needs both its variable definitions and fallback.
            if "." in node.name and node.name[0].isupper():
                svc, attr = canonical_key(*node.name.split(".", 1))
                fallback = ("read", f"{svc}.{attr}")
                defs = definitions.setdefault(node.name, [])
                if fallback not in defs:
                    defs.append(fallback)
            return ("var", node.name)
        if isinstance(node, jp.CallExpr):
            svc, method = canonical_key(node.service, node.method)
            args = node.args or ()
            if svc == "globalvariable":
                if not args or not isinstance(args[0], e.Lit) or not isinstance(args[0].value, str):
                    errors.append("GV name must be a literal string")
                    return ("lit", None)
                name = args[0].value
                if method.startswith("get") and len(args) == 1:
                    return ("var", "@gv:" + name)
                if method.startswith("set") and len(args) == 2:
                    if not statement_call:
                        errors.append("GV writes in expressions are unsupported")
                    writes.add(name)
                    value = convert(args[1])
                    definitions.setdefault("@gv:" + name, []).append(value)
                    actions.append(value)
                    return value
                errors.append("unsupported GV call shape")
                return ("lit", None)
            if not all(isinstance(arg, e.Lit) for arg in args):
                errors.append("query input coverage requires literal arguments")
                return ("computed", "query", tuple(convert(arg) for arg in args))
            from explorer.runtime.interp import call_world_key
            key = call_world_key(node)
            return ("read", key + "(" + ",".join(repr(arg.value) for arg in args) + ")" if args else key)
        if isinstance(node, e.BinaryOp):
            op = node.op.rstrip("|")
            if isinstance(node.left, e.Lit) and isinstance(node.right, e.Lit):
                try:
                    return ("lit", e.evaluate(e.BinaryOp(op, node.left, node.right), e.EvalContext({}, {}, {})))
                except (ValueError, TypeError, ArithmeticError):
                    errors.append("invalid constant expression")
            return ("bool" if op in CMP | {"and", "or"} else "computed", op,
                    (convert(node.left), convert(node.right)))
        if isinstance(node, e.UnaryOp):
            if isinstance(node.operand, e.Lit):
                try:
                    return ("lit", e.evaluate(node, e.EvalContext({}, {}, {})))
                except (ValueError, TypeError, ArithmeticError):
                    errors.append("invalid constant expression")
            return ("bool" if node.op == "not" else "computed", node.op, (convert(node.operand),))
        if isinstance(node, e.FuncCall):
            return ("computed", node.name, tuple(convert(arg) for arg in node.args))
        errors.append("uncovered expression: " + type(node).__name__)
        return ("lit", None)

    for stmt in all_stmts:
        if isinstance(stmt, jp.Assign):
            rhs = convert(stmt.rhs)
            definitions.setdefault(stmt.name, []).append(rhs)
        elif isinstance(stmt, jp.CallStmt):
            svc, method = canonical_key(stmt.call.service, stmt.call.method)
            if svc == "globalvariable":
                convert(stmt.call, statement_call=True)
            else:
                actions.extend(convert(a) for a in stmt.call.args or ())
        else:
            for node in stmt_exprs(stmt):
                expressions.append((convert(node), isinstance(stmt, (jp.IfStmt, jp.WaitUntil, jp.Loop))))
    # Reads of internal GVs can see the initial value or any preceding write.
    # Pair-level ownership later moves these pseudo-inputs to the initial axes.
    gv_names = set(writes)
    def gv_refs(node):
        if node[0] == "var" and node[1].startswith("@gv:"):
            gv_names.add(node[1][4:])
        elif node[0] not in ("lit", "read", "var"):
            for child in node[2]:
                gv_refs(child)
    for nodes in list(definitions.values()) + [[n for n, _ in expressions], actions]:
        for node in nodes:
            gv_refs(node)
    for name in gv_names:
        definitions.setdefault("@gv:" + name, []).append(("read", "@gv:" + name))
    result = Collector(definitions, expressions, actions, writes).run()
    result.errors.extend(errors)
    return result


def ir_coverage(ins):
    definitions, expressions, actions, errors = {}, [], [], []

    def convert(node):
        tag = node[0]
        if tag in ("lit", "var", "read"):
            return node[:2]
        if tag == "expr":
            return convert(node[1])
        if tag == "tmpl":
            return ("computed", "template", tuple(convert(x) for x in node[1] if isinstance(x, tuple)))
        if tag == "bin":
            op = node[1]
            return ("bool" if op in CMP | {"and", "or"} else "computed", op,
                    (convert(node[2]), convert(node[3])))
        if tag in ("not", "abs", "min", "max"):
            return ("bool" if tag == "not" else "computed", tag, tuple(convert(x) for x in node[1:]))
        errors.append("uncovered IR expression: " + tag)
        return ("lit", None)

    for x in ins:
        if x.cond is not None:
            expressions.append((convert(x.cond), True))
        if x.kind == "READ":
            definitions.setdefault(x.var, []).append(("read", x.key))
        if x.kind == "CALL":
            if x.var:
                if not all(a[0] == "lit" for a in x.args):
                    errors.append("query input coverage requires literal arguments")
                    continue
                key = x.key + "(" + ",".join(repr(a[1]) for a in x.args) + ")"
                # Zero-arg IR calls also have a property-read counterpart. The
                # base key is the canonical model axis used by both runners.
                if not x.args:
                    key = x.key
                definitions.setdefault(x.var, []).append(("read", key))
            else:
                actions.extend(convert(a) for a in x.args)
    result = Collector(definitions, expressions, actions).run()
    result.errors.extend(errors)
    return result


def merged_coverage(*coverages):
    result = Coverage()
    for coverage in coverages:
        if coverage is None:
            raise Unsupported("runner lacks an input coverage certificate")
        result.exact.update(coverage.exact)
        result.writes.update(coverage.writes)
        result.errors.extend(coverage.errors)
        for key, predicates in coverage.predicates.items():
            result.require(key)
            for op, constant in predicates:
                result.add(key, op, constant)
    return result


def coverage_domains(coverage):
    cells, initial, exact, initial_exact, families = {}, {}, set(), set(), {}
    for key, predicates in sorted(coverage.predicates.items()):
        internal = key.startswith("@gv:") and key[4:] in coverage.writes
        target, name = (initial, key[4:]) if internal else (cells, key)
        required = initial_exact if internal else exact
        try:
            values, family = representatives(predicates)
        except ValueError:
            values, family = [None], "explicit"
            required.add(name)
        if key in coverage.exact:
            required.add(name)
            family = "explicit"
        target[name] = values
        families[("initial:" + name) if internal else name] = family
    return cells, initial, exact, initial_exact, families


def install_coverage(axes, coverage):
    from dataclasses import replace
    cells, initial, exact, initial_exact, families = coverage_domains(coverage)
    return replace(axes, cells=cells, coverage=coverage, initial_cells=initial,
                   exact_reads=sorted(exact), initial_exact=sorted(initial_exact),
                   input_families=families, mirror_gv=sorted(initial),
                   observable_reads=[k for k in axes.observable_reads if k in cells])


def initial_domains(axes, declared=None):
    from explorer.verification.input_model import validate_domains
    if declared is None:
        if axes.initial_exact:
            raise Unsupported("explicit initial GV domain required: " + ", ".join(axes.initial_exact))
        return axes.initial_cells
    validate_domains(declared, required=axes.initial_cells)
    return declared
