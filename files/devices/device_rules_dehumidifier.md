[Device Summary]
<Device "Dehumidifier">
  <Service "DehumidifierMode" type="value">Current mode of the dehumidifier. Enum values: cooling, delayWash, drying, finished, refreshing, weightSensing, wrinklePrevent, dehumidifying, AIDrying, sanitizing, internalCare, freezeProtection, continuousDehumidifying, thawingFrozenInside.</Service>
  <Service "SetDehumidifierMode" type="action">Set the dehumidifier mode</Service>
</Device>

[Mode Mapping]
- "drying mode" / "dry mode" → Mode: "drying" (NOT "dehumidifying")
- "dehumidifying mode" / "active dehumidify" → Mode: "dehumidifying"
- "refresh mode" → Mode: "refreshing" (NOT "refresh")

# Dehumidifier Examples

[Command]
Set the Dehumidifier to dehumidifying mode
["Dehumidifier.SetDehumidifierMode"]

[Command]
Check the current mode of the Dehumidifier
["Dehumidifier.DehumidifierMode"]

[Command]
Switch the Dehumidifier to sanitizing mode
["Dehumidifier.SetDehumidifierMode"]

[Command]
When the Dehumidifier finishes its cycle, do something
["Dehumidifier.DehumidifierMode"]
