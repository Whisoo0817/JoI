[Device Summary]
<Device "Plug">
  <Service "Current" type="value">Current draw (DOUBLE, amperes)</Service>
  <Service "Power" type="value">Power consumption (DOUBLE, watts)</Service>
  <Service "Voltage" type="value">Voltage (DOUBLE, millivolts)</Service>
</Device>

# Plug Examples

[Command]
Check the current power usage of the Plug
["Plug.Power"]

[Command]
What is the voltage on the Plug?
["Plug.Voltage"]

[Command]
Read the current draw on the Plug
["Plug.Current"]

[Command]
When the power exceeds 2000 watts, do something
["Plug.Power"]
