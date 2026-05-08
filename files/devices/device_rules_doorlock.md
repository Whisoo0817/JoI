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
