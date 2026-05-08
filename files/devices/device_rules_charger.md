[Device Summary]
<Device "Charger">
  <Service "ChargingState" type="value">The current charging state of the device. Enum values: charging, discharging, stopped, fullyCharged, error.</Service>
  <Service "Current" type="value">The current flowing into or out of the battery in amperes</Service>
  <Service "Power" type="value">The power consumption of the device in watts</Service>
  <Service "Voltage" type="value">The voltage of the battery in millivolts</Service>
</Device>

# Charger Examples

[Command]
What is the current ChargingState of the Charger?
["Charger.ChargingState"]

[Command]
Check the voltage of the Charger
["Charger.Voltage"]

[Command]
Read the current draw on the Charger
["Charger.Current"]

[Command]
How much power is the Charger consuming?
["Charger.Power"]

[Command]
When the battery is fully charged, do something
["Charger.ChargingState"]
