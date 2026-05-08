[Device Summary]
<Device "Valve">
  <Service "ValveState" type="value">Valve state (true: open, false: closed)</Service>
  <Service "Close" type="action">Close the valve</Service>
  <Service "Open" type="action">Open the valve</Service>
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

[Command]
When the valve opens, do something
["Valve.ValveState"]
