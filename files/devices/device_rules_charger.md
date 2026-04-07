[Device Summary]
<Device "Charger">
  <Service "ChargingState" type="value">Charging state</Service>
  <Service "Current" type="value">Charge/Discharge current (A)</Service>
  <Service "Voltage" type="value">Battery voltage (mV)</Service>
  <Service "Power" type="value">Power consumption (W)</Service>
</Device>

# Charger Examples

[Command]
What is the current ChargingState of the Charger?
["Charger.ChargingState"]

[Command]
Check the voltage of the Charger
["Charger.Voltage"]
