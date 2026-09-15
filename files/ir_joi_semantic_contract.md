# Confirmed IR–JoI semantic contract

This is the normative cross-stage contract used by confirmed Timeline IR,
confirmed binding, JoI lowering, and Explorer.  The executable constants for
period handling live in `timeline_ir/semantic_contract.py`.

## Polling and edge triggers

- An unspecified re-arming edge-trigger period defaults to `1 SEC`.
- An explicit `cycle.period` is authoritative and is preserved exactly by
  lowering.  Lowering must not replace an explicit period merely because the
  cycle contains an edge wait.
- Dataset reference IR uses explicit periods.  Consequently, old edge rows
  carrying the former implicit `100 MSEC` convention are repaired to `1 SEC`.

## Binding cardinality

- A return-valued function whose result is assigned to one scalar variable
  requires exactly one bound provider for that occurrence.
- A property `read` assigned to one scalar variable has the same requirement.
- A condition over several Boolean providers requires an explicit `any` or
  `all` binding.  A bare multi-provider Boolean binding has no default
  quantifier.
- An effect-only action may fan out to every device in its confirmed binding.

## Effectful returns and value flow

- A catalog function may both emit an observable action and return a value.
  Assignment is represented by `call.var` only when a later IR expression uses
  that returned value.
- An unused return is not assigned.  The call remains observable regardless of
  whether its return is assigned.
- A value property such as `Speaker.Volume` is read with `read`; it is not
  represented as the return of `Speaker.SetVolume`.

## Numeric boundaries

- Numeric arguments must remain inside the catalog-declared argument domain for
  every modeled input.  The contract never assumes device-side wraparound or
  acceptance of an invalid argument.
- When the catalog provides an exact relative operation for the requested step
  (for example `Television.ChannelDown` for one channel), that operation is used.
- Otherwise a benchmark interpretation that saturates at a catalog boundary
  must encode the saturation explicitly with `min`/`max` (or an equivalent
  guard).  If neither an authoritative input domain nor a boundary behavior is
  available, Explorer retains an explicit unsupported-domain outcome.

## Window-end and grouped Boolean semantics

- “From A to B, if X never occurred, do Y” is evaluated at B over the whole
  interval.  When B is a clock anchor, it may be encoded as one wait for
  `X or Clock >= B`, followed by a B-guarded action; observing X completes the
  automation without Y.
- “No monitored sensor observed X” means `not any(sensor.X == true)`,
  equivalently `all(sensor.X == false)`.  The corresponding multi-device
  binding must carry `any` or `all` explicitly.
