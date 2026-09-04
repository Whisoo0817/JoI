# Minimal abstract grammar

This grammar is an advisor-level abstract syntax. Concrete YAML/JSON spelling may differ, but must map uniquely to this AST.

```ebnf
Program    ::= Decls Rule+
Decls      ::= StateDecl* TimerDecl* ActionSig* EnvDecl
Rule       ::= "on" Trigger ["when" Expr] "reentry" Reentry "do" Stmt
Trigger    ::= EventPat | EdgePat | StatePat | TimerExpired
Reentry    ::= "ignore" | "restart"

Stmt       ::= "skip"
             | Effect
             | "if" Expr "then" Stmt "else" Stmt
             | "seq" "[" Stmt+ "]"
             | "par" "[" Stmt+ "]"
             | "delay" Duration ";" Stmt
             | "wait_until" Expr ["timeout" Duration]
             | "repeat" NatPos "times" Stmt

Effect     ::= "set" StateRef "=" Expr
             | "start" TimerRef "after" Duration
             | "cancel" TimerRef
             | "call" ActionRef "(" ArgList ")"

Expr       ::= Literal | Ref | Unary Expr | Expr Binary Expr
             | "is_missing" "(" Ref ")"
Ref        ::= StateRef | SensorRef | DeviceStateRef | EventField
Duration   ::= NatPos TimeUnit
```

## Semantic constructors

- `seq` preserves explicit causal order.
- `par` evaluates children from one snapshot and merges compatible typed effects; AST child order has no semantic force.
- `delay` and `wait_until` create explicit residual control/timer state.
- `repeat n` is finite; `n` is a positive static integer.
- Absent `else` is not allowed: an explicit `else skip` preserves totality.

## Exclusions

No general host-language expression, nondeterministic choice, implicit priority, unbounded repeat, `queue` reentry, or same-tick recursive event emission is admitted.

