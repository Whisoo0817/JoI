# IR Pattern: STATE_CYCLE (D-4 phase, D-5 alternation)

A cycle that needs a **state variable** to remember progress across ticks. Two sub-patterns:

## D-4. Phase lifecycle (when X, thereafter every N)
**IR shape**: `wait(edge:"none", cond:X)` at top level, BEFORE a `cycle{ Y; delay(N) }`.

**Period rule**: `period = N` (the cycle's trailing delay).

**Idiom**: `phase` enum (0 = waiting for X, 1 = periodic).
```
phase := 0
if (phase == 0) {
    wait until(X)
    phase = 1
    Y
}
if (phase == 1) {
    Y
}
```

## D-5. Alternation (every N, A then B)
**IR shape**: `cycle{ A; delay(N); B; delay(N) }` — the cycle body has **two delays** with an action between each pair.

**Period rule**: `period = N` (each delay).

**Idiom**: `state` toggle.
```
state := "A"
if (state == "A") {
    A
    state = "B"
} else {
    B
    state = "A"
}
```

For 3-way or more alternations (rare), generalize the toggle to track which step is next.

## ⚠️ Distinguish from B-2 / D-3 / D-6
- B-2 (simple periodic): `cycle{ call; ONE delay }` — single state, no `phase`/`state` variable needed. NOT this bucket.
- D-3 (rising whenever): `cycle{ wait(rising); ... }`. NOT this bucket.
- D-6 (progressive break): `cycle{ ... if{break} }` — break logic. NOT this bucket.

## Examples

### Ex1 — D-4 phase lifecycle (when door opens, thereafter every 3 min)
[Timeline IR]
```
{"timeline":[{"op":"start_at","anchor":"now"},
 {"op":"wait","cond":"Door.DoorState == \"open\"","edge":"none"},
 {"op":"cycle","until":null,"body":[
   {"op":"call","target":"Light.On","args":{}},
   {"op":"delay","ms":180000}]}]}
```
[Precision Selectors] `(#Door)` / `(#Light)`
<Reasoning>
Phase lifecycle: wait once, then periodic action; phase 0 → 1 transition.
</Reasoning>
{"cron":"","period":180000,"script":"phase := 0\nif (phase == 0) {\n    wait until((#Door).DoorState == \"open\")\n    phase = 1\n    (#Light).On()\n}\nif (phase == 1) {\n    (#Light).On()\n}"}

### Ex2 — D-5 alternation (every 10s, blue then red)
[Timeline IR]
```
{"timeline":[{"op":"start_at","anchor":"now"},
 {"op":"cycle","until":null,"body":[
   {"op":"call","target":"Light.MoveToColor","args":{"X":0.167,"Y":0.040,"TransitionTime":0.0}},
   {"op":"delay","ms":10000},
   {"op":"call","target":"Light.MoveToColor","args":{"X":0.675,"Y":0.322,"TransitionTime":0.0}},
   {"op":"delay","ms":10000}]}]}
```
[Precision Selectors] `(#Light)`
<Reasoning>
Two-state alternation; period = 10000; xy values already resolved by extractor — pass through positional.
</Reasoning>
{"cron":"","period":10000,"script":"color := \"red\"\nif (color == \"red\") {\n    (#Light).MoveToColor(0.167, 0.040, 0.0)\n    color = \"blue\"\n} else {\n    (#Light).MoveToColor(0.675, 0.322, 0.0)\n    color = \"red\"\n}"}
