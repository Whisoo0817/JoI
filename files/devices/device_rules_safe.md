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
