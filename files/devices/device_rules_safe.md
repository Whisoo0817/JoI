[Device Summary]
<Device "Safe">
  <Service "SafeState" type="value">Safe status (locked, unlocked)</Service>
  <Service "Lock" type="action">Lock/Close</Service>
  <Service "Unlock" type="action">Unlock/Open</Service>
</Device>

# Safe Examples

[Command]
Lock the Safe
["Safe.Lock"]

[Command]
Unlock the Safe
["Safe.Unlock"]

[Command]
Is the Safe currently locked?
["Safe.SafeState"]
