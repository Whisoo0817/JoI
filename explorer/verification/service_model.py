"""Catalog-backed adapter; no change to the Timeline IR or binding schema.

Read roles below are reviewed model assumptions from descriptors, NOT an
official catalog category or a proof about the server implementation.
"""
from __future__ import annotations

import copy
from dataclasses import fields, is_dataclass
from decimal import Decimal
from fractions import Fraction
import math
import re

from timeline_ir.catalog import load_service_specs
from explorer.runtime import expr as e
from explorer.runtime import joi_parser as jp
from explorer.runtime.interp import Unsupported
from explorer.verification.input_coverage import predicate_value, unique
from explorer.verification.input_model import validate_domains


# Explicit descriptor review, scoped to the catalog hash recorded in each run.
# Unknown functions may be observed as ACTION statements, never silently read.
READ_FUNCTIONS = {
    ('WeatherProvider', 'Forecast'), ('WeatherProvider', 'GetWeatherInfo'),
    ('ArmRobotDetail', 'GetMotion'), ('ArmRobotDetail', 'ListMotions'),
    ('MenuProvider', 'GetMenu'), ('NewsProvider', 'GetNewsDigest'),
    ('CloudServiceProvider', 'IsAvailable'),
}
# Clock Hour/Minute/Second bounds corrected; reviewed read-function descriptors
# are byte-for-byte unchanged (see CATALOG_RANGE_ANALYSIS.md).
REVIEWED_CATALOG_SHA256 = 'fe25ecbf5a9028b46232ce156072654217f23997e5b4f974368fa448fcffd1a4'


class ServiceModel:
    def __init__(self, devices, path=None):
        self.snapshot = load_service_specs() if path is None else load_service_specs(path)
        self.devices = devices
        self.services, self.members = {}, {}
        self.used = {}
        for skill in self.snapshot['skills']:
            sid = skill['id']
            if sid.lower() in self.services:
                raise Unsupported('catalog service alias collision: ' + sid)
            self.services[sid.lower()] = skill
            enums = {v['id']: [m['value'] for m in v['members']]
                     for v in skill.get('enums', [])}
            for kind, collection in [('value', 'values'), ('function', 'functions')]:
                for member in skill.get(collection, []):
                    key = e.canonical_key(sid, member['id'])
                    if (kind, key) in self.members:
                        raise Unsupported('catalog member alias collision: ' + repr(key))
                    spec = copy.deepcopy(member)
                    spec.update(service=sid, kind=kind)
                    for domain in [spec, *spec.get('arguments', [])]:
                        if domain.get('type') == 'ENUM':
                            domain['members'] = enums.get(domain.get('format'))
                    ret = spec.get('return_type', 'VOID')
                    spec['return_spec'] = {'type': ret} if isinstance(ret, str) else ret
                    # User-approved target runtime contract, not a nullable
                    # declaration inferred for every catalog STRING.
                    if (sid, member['id']) == ('MenuProvider', 'GetMenu'):
                        spec['return_spec'] = {**spec['return_spec'],
                            'nullable': False, 'domain_basis': 'menu-string-return-v1: user contract'}
                    # Descriptor explicitly identifies WeatherEnum names. Keep
                    # STRING type; this is a reviewed descriptor interpretation.
                    if (sid, member['id']) == ('WeatherProvider', 'Forecast'):
                        spec['return_spec'] = {**spec['return_spec'],
                            'members': enums.get('WeatherEnum'),
                            'domain_basis': 'descriptor: WeatherEnum value names'}
                    self.members[kind, key] = spec

    def resolve(self, service, member, kind):
        key = e.canonical_key(service, member)
        spec = self.members.get((kind, key))
        if spec is None:
            raise Unsupported(f'unknown catalog {kind}: {service}.{member}')
        self.used[f"{spec['service']}.{spec['id']}:{kind}"] = spec
        return spec

    def device_supports(self, did, service):
        if did not in self.devices:
            raise Unsupported('unknown device: ' + did)
        categories = self.devices[did].get('category') or []
        if service.lower() not in [s.lower() for s in categories]:
            raise Unsupported(f'device {did} does not declare capability {service}')

    def clock_integer_range(self, key):
        """Catalog bounds for implemented, non-null derived clock readings.

        The implementation-range checks below only guard adapter conformance;
        the interval used by the proof comes from the supplied catalog. A wider
        catalog stays wider; absent/malformed/narrower declarations give no proof.
        IR clock.time is the numeric built-in hour*100+minute, NOT the catalog's
        STRING Clock.Time attribute. Its range is derived from those two fields.
        """
        if key == 'clock.time':
            hour = self.clock_integer_range('clock.hour')
            minute = self.clock_integer_range('clock.minute')
            if hour is not None and minute is not None:
                return (hour[0] * 100 + minute[0], hour[1] * 100 + minute[1])
            return None
        implementation = {'clock.hour': (0, 23), 'clock.minute': (0, 59)}
        if key not in implementation:
            return None
        spec = self.members.get(('value', tuple(key.split('.'))))
        if spec is None or spec.get('type') != 'INTEGER':
            return None
        bounds = spec.get('bound')
        if (not isinstance(bounds, (list, tuple)) or len(bounds) != 2
                or any(type(v) is not int for v in bounds)
                or not bounds[0] <= implementation[key][0] <= implementation[key][1] <= bounds[1]):
            return None
        self.resolve('Clock', spec['id'], 'value')
        return tuple(bounds)

    def call(self, spec, args, expression):
        expected = spec.get('arguments', [])
        if len(args) != len(expected):
            raise Unsupported(f"argument count: {spec['service']}.{spec['id']} needs {len(expected)}, got {len(args)}")
        pair = spec['service'], spec['id']
        if pair in READ_FUNCTIONS and self.snapshot['sha256'] != REVIEWED_CATALOG_SHA256:
            raise Unsupported('read-role descriptor review is stale for this catalog hash')
        if spec['service'] == 'GlobalVariable':
            if expression != spec['id'].startswith('Get'):
                raise Unsupported('GV getter/setter used in unsupported call position')
        elif expression and pair not in READ_FUNCTIONS:
            raise Unsupported(f'return-assigned/effectful or unreviewed function cannot be a silent input: {pair}')
        elif not expression and pair in READ_FUNCTIONS:
            raise Unsupported(f'read function in ACTION position requires explicit result assignment: {pair}')
        for value, domain in zip(args, expected):
            if isinstance(value, e.Lit):
                self.validate_value(value.value, domain, f'{pair}.{domain["id"]}', missing=False)

    @staticmethod
    def validate_value(value, spec, label, *, missing=True):
        from explorer.verification.symbolic_values import SymbolicValue, validate_symbolic
        if isinstance(value, SymbolicValue):
            if missing:
                raise Unsupported('symbolic objects are not explicit concrete input values')
            return validate_symbolic(value, spec, label)
        typ = spec.get('type')
        if value is None and missing and typ not in ('BOOL', 'BOOLEAN') and spec.get('nullable', True):
            return  # Non-BOOL inputs retain the declared missing-value model.
        valid = {'BOOL': lambda: type(value) is bool,
                 'BOOLEAN': lambda: type(value) is bool,
                 'INTEGER': lambda: type(value) is int,
                 'DOUBLE': lambda: type(value) in (int, float) and math.isfinite(value),
                 'STRING': lambda: isinstance(value, str),
                 'ENUM': lambda: value in (spec.get('members') or [])}.get(typ)
        if valid is None or not valid():
            raise Unsupported(f'catalog type/domain mismatch: {label} expects {typ}, got {value!r}')
        if spec.get('members') is not None and value not in spec['members']:
            raise Unsupported(f'catalog enum mismatch: {label} got {value!r}')
        if spec.get('bound') and not spec['bound'][0] <= value <= spec['bound'][1]:
            raise Unsupported(f'catalog bound mismatch: {label} got {value!r}, bound={spec["bound"]}')

    def normalize_ir(self, ir, binding):
        """Validate before grounding; retain argument insertion/slot walk order."""
        ir, binding = copy.deepcopy(ir), copy.deepcopy(binding)
        normalized = {}
        for name, ids in binding.items():
            svc, sep, suffix = name.partition('#')
            skill = self.services.get(svc.lower())
            # Unused binding entries are allowed by the earlier contract.
            name = (skill['id'] if skill else svc) + (sep + suffix if sep else '')
            if name in normalized:
                raise Unsupported('binding service alias collision: ' + name)
            normalized[name] = ids

        def ref(svc, member):
            if svc.lower() == 'clock':
                return f'{svc}.{member}'
            spec = self.resolve(svc, member, 'value')
            return f"{spec['service']}.{spec['id']}"

        def text_refs(src, *, template=False):
            # Quoted literals are never rewritten. Template placeholders alone
            # are expressions; ordinary dotted template text remains data.
            pattern = r'"[^"\\]*"|\x27[^\x27\\]*\x27|\$?([A-Za-z_]\w*)\.([A-Za-z_]\w*)'
            if template:
                pattern = r'\$([A-Za-z_]\w*)\.([A-Za-z_]\w*)'
            def replace(m):
                if m.group(1) is None or (template and not m.group().startswith('$')):
                    return m.group()
                return ('$' if m.group().startswith('$') else '') + ref(m.group(1), m.group(2))
            return re.sub(pattern, replace, src)

        def walk(steps):
            for node in steps:
                for field in ('cond', 'until'):
                    if node.get(field):
                        node[field] = text_refs(node[field])
                if node.get('op') == 'read':
                    node['src'] = ref(*node['src'].split('.', 1))
                if node.get('op') == 'call':
                    spec = self.resolve(*node['target'].split('.', 1), 'function')
                    node['target'] = f"{spec['service']}.{spec['id']}"
                    given = node.get('args') or {}
                    if not isinstance(given, dict):
                        raise Unsupported('IR call arguments must be named')
                    arg_names = {a['id'].lower(): a['id'] for a in spec.get('arguments', [])}
                    if len(arg_names) != len(spec.get('arguments', [])):
                        raise Unsupported('catalog argument alias collision')
                    args = {}
                    for name, value in given.items():
                        name = arg_names.get(name.lower())
                        if name is None or name in args:
                            raise Unsupported('unknown/duplicate named argument for ' + node['target'])
                        args[name] = value
                    if set(args) != set(arg_names.values()):
                        raise Unsupported('missing named arguments for ' + node['target'])
                    vals = [args[a['id']] for a in spec.get('arguments', [])]
                    self.call(spec, [e.VarRef(v) if isinstance(v, str) and '$' in v
                                     else e.Lit(v) for v in vals], bool(node.get('var')))
                    for name, value in args.items():
                        if isinstance(value, str) and '$' in value:
                            from explorer.runtime.ir_step import parse_cond, default_to_key
                            try:
                                parse_cond(value, default_to_key)
                                template = False
                            except (Unsupported, ValueError):
                                template = True
                            args[name] = text_refs(value, template=template)
                    node['args'] = args
                for value in node.values():
                    if isinstance(value, list):
                        walk([v for v in value if isinstance(v, dict)])
        walk(ir.get('timeline') or [])
        return ir, normalized

    def order_grounded_ir(self, ir):
        def walk(value):
            if isinstance(value, dict):
                if value.get('op') == 'call':
                    spec = self.resolve(*value['target'].split('.', 1), 'function')
                    args = value.get('args') or {}
                    value['args'] = {a['id']: args[a['id']] for a in spec.get('arguments', [])}
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)
        walk(ir)

    def validate_joi(self, stmts):
        """Run on grounded AST; concrete IDs avoid selector-tag type guesses."""
        def walk(node, statement=False):
            if isinstance(node, jp.CallStmt):
                walk(node.call, True)
                return
            if isinstance(node, jp.CallExpr):
                spec = self.resolve(node.service, node.method, 'function' if node.args is not None else 'value')
                if spec['service'] not in ('Clock', 'GlobalVariable'):
                    if not node.tags:
                        raise Unsupported('service call needs a resolved device selector')
                    for did in node.tags:
                        self.device_supports(did, spec['service'])
                if node.args is not None:
                    self.call(spec, node.args, not statement)
                    # Dynamic read arguments are already outside D7. Refuse
                    # here too so no argument type check is skipped.
                    if spec['service'] != 'GlobalVariable' and not statement and any(
                            not isinstance(a, e.Lit) for a in node.args):
                        raise Unsupported('dynamic read arguments require a service model')
                    for arg in node.args:
                        walk(arg)
                return
            if isinstance(node, e.DeviceRef):
                self.input_spec(node.key)
                return
            if isinstance(node, (list, tuple)):
                for child in node:
                    walk(child)
            elif is_dataclass(node):
                for field in fields(node):
                    walk(getattr(node, field.name))
        walk(stmts)

    def validate_source(self, stmts, bound=frozenset()):
        # Grounding removes capability names from property reads. Check them
        # before that information is lost, including a function used as a field.
        # Reads of bound services resolve to binding devices; validate_joi checks those.
        from explorer.runtime.ground import match
        from explorer.verification.gate import devs_of, pick_by_rule
        inventory = devs_of(self.devices)
        def walk(node, expand=False):
            if isinstance(node, e.QuantRef):
                svc, member = node.key.split('.', 1)
                if svc not in ('clock', 'globalvariable') and svc not in bound:
                    spec = self.resolve(svc, member, 'value')
                    matches = match(inventory, node.tags)
                    if matches:
                        selected = matches if expand or node.quant in ('any', 'all') else [pick_by_rule(matches)]
                        for dev in selected:
                            self.device_supports(dev.id, spec['service'])
            if isinstance(node, (list, tuple)):
                for child in node:
                    walk(child)
            elif is_dataclass(node):
                for field in fields(node):
                    walk(getattr(node, field.name), isinstance(node, e.BinaryOp) and node.op.endswith('|'))
        walk(stmts)

    def input_spec(self, key):
        base = key.split('(', 1)[0]
        if base == 'clock.isholiday':
            return {'type': 'BOOL'}
        if base.startswith(('@gv:', 'clock.')):
            return None  # Separately declared GV / built-in clock contract.
        did, _, member = base.partition('.')
        if did not in self.devices:
            raise Unsupported('unbound catalog input: ' + key)
        hits = []
        for service in self.devices[did].get('category') or []:
            for kind in ('value', 'function'):
                spec = self.members.get((kind, e.canonical_key(service, member)))
                if spec is not None:
                    hits.append(spec)
        if len(hits) != 1:
            raise Unsupported('unknown/ambiguous concrete input member: ' + key)
        spec = hits[0]
        self.used[f"{spec['service']}.{spec['id']}:{spec['kind']}"] = spec
        if spec['kind'] == 'function':
            if (spec['service'], spec['id']) not in READ_FUNCTIONS:
                raise Unsupported('unreviewed function input: ' + key)
            if self.snapshot['sha256'] != REVIEWED_CATALOG_SHA256:
                raise Unsupported('read-role descriptor review is stale for this catalog hash')
            return spec['return_spec']
        return spec

    def domains(self, coverage, declared=None):
        """Partition the declared catalog domain, never filter old witnesses.

        Filtering mixed-type representatives could remove a whole valid class
        (e.g. bool False had represented integer zero). Rebuild witnesses using
        catalog types and bounds before taking truth-vector equivalence classes.
        """
        required = {k: p for k, p in coverage.predicates.items()
                    if not (k.startswith('@gv:') and k[4:] in coverage.writes)}
        if declared is not None:
            validate_domains(declared, required=required)
            for key, values in declared.items():
                spec = self.input_spec(key)
                if spec is not None:
                    for value in values:
                        self.validate_value(value, spec, key)
            return copy.deepcopy(declared)
        from explorer.verification.input_coverage import representatives
        result = {}
        for key, predicates in required.items():
            spec = self.input_spec(key)
            if spec is None:
                if key in coverage.exact:
                    raise Unsupported('explicit input domain required: ' + key)
                result[key] = representatives(predicates)[0]
            else:
                result[key] = self.representatives(spec, predicates, key in coverage.exact)
        validate_domains(result, required=required)
        return result

    @staticmethod
    def representatives(spec, predicates, exact=False):
        typ, bound = spec.get('type'), spec.get('bound')
        if typ in ('BOOL', 'BOOLEAN'):
            # User contract: both Boolean values, no missing state or 0/1 aliases.
            # Exhausting two values is cheaper and clearer than partitioning them.
            return [False, True]
        candidates = [None] if spec.get('nullable', True) else []
        if spec.get('members') is not None:
            candidates += spec['members']
        elif typ in ('INTEGER', 'DOUBLE'):
            scale = 1 if typ == 'INTEGER' else 10
            lo = math.ceil(Fraction(str(bound[0])) * scale) if bound else None
            hi = math.floor(Fraction(str(bound[1])) * scale) if bound else None
            if exact:
                if lo is None or hi - lo > 100000:
                    raise Unsupported('explicit input domain required for observable large/unbounded catalog value')
                integers = range(lo, hi + 1)
            else:
                integers = {0, 1, -1}
                if lo is not None:
                    integers.update((lo, hi))
                for op, c in predicates:
                    if isinstance(c, (int, float)):
                        if not math.isfinite(c) or abs(c) > 10**12:
                            raise Unsupported('explicit input domain required for large threshold')
                        n = math.floor(Fraction(c) * scale)
                        integers.update((n - 1, n, n + 1))
                    elif c is not None and op not in ('==', '!=', 'truth'):
                        raise Unsupported('ordered comparison incompatible with numeric catalog input')
            candidates += [(int(n) if scale == 1 else float(Decimal(n) / 10))
                           for n in sorted(integers)
                           if lo is None or lo <= n <= hi]
            if typ == 'DOUBLE' and exact:
                # DOUBLE accepts int as well as float. Their numeric guards
                # agree, but observable conversion distinguishes 1 from 1.0.
                # Enumerate both representations; never cast the input itself.
                candidates += [n // 10 for n in integers if n % 10 == 0]
            if typ == 'DOUBLE' and any(type(v) is float and v == 0 for v in candidates):
                candidates.append(-0.0)  # Observable arguments preserve sign.
        elif typ == 'STRING':
            if exact:
                raise Unsupported('explicit input domain required for observable STRING return/value')
            strings = [''] + [c for _, c in predicates if isinstance(c, str)]
            candidates += strings + [s + '\0' for s in strings]
        else:
            raise Unsupported('unsupported catalog input type: ' + str(typ))
        candidates = unique(candidates)
        if exact:
            return candidates
        vectors = {}
        try:
            for value in candidates:
                vector = tuple(predicate_value(op, value, c) for op, c in predicates)
                vectors.setdefault(vector, value)
        except TypeError as error:
            raise Unsupported('guard incompatible with catalog input type') from error
        return list(vectors.values())

    def evidence(self):
        return {'catalog_path': self.snapshot['path'], 'catalog_sha256': self.snapshot['sha256'],
                'boolean_input_policy': 'strict-two-valued-v1',
                'menu_return_policy': 'menu-string-return-v1: MenuProvider.GetMenu is non-null STRING',
                'members': copy.deepcopy(self.used),
                'assumptions': ['descriptor-reviewed read roles (not server side-effect proof)',
                    'BOOL/BOOLEAN sensor and read-result inputs are exactly false/true; missing is outside the model',
                    'non-BOOL inputs retain missing/None except MenuProvider.GetMenu (user-approved non-null STRING)',
                    'DOUBLE external input precision 0.1 from agreed contract',
                    'fixed binding and inventory; independent external inputs',
                    'same device/member/argument read key returns one held value per input instant',
                    'GV initial domains remain separate model declarations']}


class CatalogRunner:
    """Check Boolean snapshots and ACTION arguments during exploration/replay."""
    def __init__(self, inner, model):
        self.inner, self.model = inner, model
        self.catalog_model = model
        self._boolean_keys = None
        self._nonnullable_specs = None

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def step(self, vars_, gv, inputs, now_ms, first_tick=False):
        if self._boolean_keys is None:
            self._boolean_keys = tuple(k for k in self.inner.axes.cells
                if (self.model.input_spec(k) or {}).get('type') in ('BOOL', 'BOOLEAN'))
        for key in self._boolean_keys:
            if key not in inputs or type(inputs[key]) is not bool:
                raise Unsupported('BOOL input requires true/false snapshot: ' + key)
        if self._nonnullable_specs is None:
            self._nonnullable_specs = {k: spec for k in self.inner.axes.cells
                if (spec := self.model.input_spec(k)) and spec.get('nullable') is False}
        from explorer.verification.symbolic_values import InputSymbol
        for key, spec in self._nonnullable_specs.items():
            value = inputs.get(key)
            if getattr(value, '_smt_input', False):
                if value.key != key or value.spec != spec or value.spec.get('nullable', True):
                    raise Unsupported('SMT input violates non-null contract: ' + key)
            elif isinstance(value, InputSymbol):
                if value.key != key or value.type != spec['type'] or value.nullable:
                    raise Unsupported('symbolic input violates non-null return contract: ' + key)
            else:
                self.model.validate_value(value, spec, key)
        result = self.inner.step(vars_, gv, inputs, now_ms, first_tick)
        for action in result.actions:
            spec = self.model.resolve(action.service, action.method, 'function')
            domains = spec.get('arguments', [])
            if len(action.args) != len(domains):
                raise Unsupported('runtime ACTION argument count mismatch')
            for value, domain in zip(action.args, domains):
                self.model.validate_value(value, domain, spec['id'], missing=False)
        return result


def runner_input_domains(runner_a, runner_b, declared=None):
    """Shared by gate and both timed engines; catalog checks cannot be bypassed
    by calling an engine directly on catalog-prepared runners.
    """
    a, b = (getattr(r, 'catalog_model', None) for r in (runner_a, runner_b))
    if a is None and b is None:
        return declared
    if a is None or a is not b:
        raise Unsupported('both runners must share one prepared catalog snapshot')
    from explorer.verification.input_coverage import merged_coverage
    coverage = merged_coverage(runner_a.axes.coverage, runner_b.axes.coverage)
    if coverage.errors:
        raise Unsupported('; '.join(coverage.errors))
    return a.domains(coverage, declared)
