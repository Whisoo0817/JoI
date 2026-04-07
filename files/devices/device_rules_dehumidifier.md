[Device Summary]
<Device "Dehumidifier">
  <Service "DehumidifierMode" type="value">Current mode</Service>
  <Service "SetDehumidifierMode" type="action">Set dehumidifier mode (cool, drying, refreshing, auto, etc.)</Service>
</Device>

# Dehumidifier Examples

[Command]
Set the Dehumidifier to auto mode
["Dehumidifier.SetDehumidifierMode"]

[Command]
Check the current mode of the Dehumidifier
["Dehumidifier.DehumidifierMode"]
