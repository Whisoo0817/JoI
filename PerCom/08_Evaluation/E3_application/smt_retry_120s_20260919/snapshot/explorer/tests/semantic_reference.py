"""Independent executable semantics for the E1 composition kernel.

Standard Python only: no Explorer parsers, evaluators, compilers, runners,
observation normalization, state keys, input inference or scheduling imports.
Tuple expressions and structured statements are supplied by the frozen suite.
Python generator continuations implement Seq/If/Wait/Delay/Cycle/Break directly.
This is a bounded test oracle for the declared kernel, not a second full DSL.
"""


class ExitCycle(Exception):
    pass


class Reference:
    def __init__(self, body, period=0):
        self.now = 0
        self.inputs = {}
        self.variables = {}
        self.actions = []
        self.done = False
        self.pending = None
        self.execution = self.program(body, period)

    def value(self, expr):
        kind, *args = expr
        if kind == 'literal':
            return args[0]
        if kind == 'input':
            return self.inputs.get(args[0])
        if kind == 'variable':
            return self.variables.get(args[0])
        if kind == 'eq':
            return self.value(args[0]) == self.value(args[1])
        raise ValueError('unsupported reference expression: ' + kind)

    def sequence(self, body):
        for node in body:
            kind = node[0]
            if kind == 'call':
                _, service, method, target, args = node
                self.actions.append((self.now, service, method, target,
                                     tuple(self.value(x) for x in args)))
            elif kind == 'read':
                self.variables[node[1]] = self.value(node[2])
            elif kind == 'if':
                yield from self.sequence(node[2] if self.value(node[1]) else node[3])
            elif kind == 'delay':
                yield ('deadline', self.now + node[1])
            elif kind == 'wait':
                yield ('condition', node[1])
            elif kind == 'cycle':
                _, count, period, body = node
                try:
                    for iteration in range(count):
                        yield from self.sequence(body)
                        # Period separates iterations; exiting a finite cycle
                        # after its last body does not incur another period.
                        if iteration + 1 < count:
                            yield ('deadline', self.now + period)
                except ExitCycle:
                    pass
            elif kind == 'break':
                raise ExitCycle
            else:
                raise ValueError('unsupported reference statement: ' + kind)

    def program(self, body, period):
        try:
            while True:
                yield from self.sequence(body)
                if not period:
                    return
                yield ('deadline', self.now + period)
        except ExitCycle:
            return

    def step(self, now, inputs):
        self.now, self.inputs, self.actions = now, dict(inputs), []
        if self.done:
            return []
        for _ in range(10000):
            if self.pending is not None:
                kind, payload = self.pending
                ready = now >= payload if kind == 'deadline' else bool(self.value(payload))
                if not ready:
                    return self.actions
            try:
                self.pending = next(self.execution)
            except StopIteration:
                self.done = True
                return self.actions
        raise RuntimeError('reference reaction did not terminate')
