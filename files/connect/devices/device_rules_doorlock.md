[Device Summary]
<Device "DoorLock">
  <Service "DoorLockState" type="value">Door lock state (unlocked, locked)</Service>
  <Service "Lock" type="action">Lock/Close</Service>
  <Service "Unlock" type="action">Unlock/Open</Service>
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
