[Device Summary]
<Device "DoorLock">
  <Service "DoorLockState" type="value">Current lock state. Enum values: closed, closing, open, opening, unknown.</Service>
  <Service "Lock" type="action">Lock the door</Service>
  <Service "Unlock" type="action">Unlock the door</Service>
</Device>

# DoorLock Examples

[Command]
Lock the front door
["DoorLock.Lock"]

[Command]
Unlock the DoorLock
["DoorLock.Unlock"]

[Command]
Is the DoorLock currently locked?
["DoorLock.DoorLockState"]

[Command]
When the door is unlocked, do something
["DoorLock.DoorLockState"]

# @enum_resolve
DoorLockState enum semantic mapping (catalog uses door-state vocabulary for lock-state):
- "locked / is locked / 잠긴 / 잠겨있는 / shut / secured" → `closed`
- "unlocked / is unlocked / open / 열린 / 열려있는" → `open`
- "closing" / "opening" — mid-transition; only when command explicitly describes movement.
- "unknown" — state ambiguous; do not pick unless command literally says so.
