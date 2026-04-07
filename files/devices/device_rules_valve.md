[Device Summary]
<Device "Valve">
  <Service "ValveState" type="value">Valve state (true: open, false: closed)</Service>
  <Service "Open" type="action">Open Valve</Service>
  <Service "Close" type="action">Close Valve</Service>
</Device>

# Valve Examples

[Command]
Open the water Valve
["Valve.Open"]

[Command]
Close the Valve
["Valve.Close"]

[Command]
Check if the Valve is open
["Valve.ValveState"]
