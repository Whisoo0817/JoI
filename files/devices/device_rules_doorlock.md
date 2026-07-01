[Device Summary]
<Device "DoorLock">
  <Service "DoorLockState" type="value">Current lock state. Enum values: closed, closing, open, opening, unknown.</Service>
  <Service "Lock" type="action">Lock the door</Service>
  <Service "Unlock" type="action">Unlock the door</Service>
</Device>

# @enum_resolve
DoorLockState enum semantic mapping (catalog uses door-state vocabulary for lock-state):
- "locked / is locked / 잠긴 / 잠겨있는 / shut / secured" → `closed`
- "unlocked / is unlocked / open / 열린 / 열려있는" → `open`
- "closing" / "opening" — mid-transition; only when command explicitly describes movement.
- "unknown" — state ambiguous; do not pick unless command literally says so.
