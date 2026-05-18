[Device Summary]
<Device "Safe">
  <Service "SafeState" type="value">Current state. Enum values: closed, closing, open, opening, unknown.</Service>
  <Service "Lock" type="action">Lock the safe</Service>
  <Service "Unlock" type="action">Unlock the safe</Service>
</Device>

# Safe Examples

[Command]
Lock the Safe
["Safe.Lock"]

[Command]
Unlock the Safe
["Safe.Unlock"]

[Command]
Is the Safe currently open or closed?
["Safe.SafeState"]

[Command]
When the safe is opened, do something
["Safe.SafeState"]

# @enum_resolve
SafeState enum semantic mapping (catalog uses door-state vocabulary for lock-state):
- "locked / is locked / 잠긴 / 잠겨있는 / shut / secured" → `closed`
- "unlocked / is unlocked / open / 열린 / 열려있는" → `open`
- "closing" / "opening" — mid-transition; only when command explicitly describes movement.
- "unknown" — state ambiguous; do not pick unless command literally says so.
