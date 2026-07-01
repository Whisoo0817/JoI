[Device Summary]
<Device "Charger">
  <Service "ChargingState" type="value">The current charging state of the device. Enum values: charging, discharging, stopped, fullyCharged, error.</Service>
  <Service "Current" type="value">The current flowing into or out of the battery in amperes</Service>
  <Service "Power" type="value">The power consumption of the device in watts</Service>
  <Service "Voltage" type="value">The voltage of the battery in millivolts</Service>
</Device>

# Rules

All Charger services are **read-only measurements** — `Power` / `Current` / `Voltage` / `ChargingState` report metering, they are NOT switches. `Charger.Power` does NOT turn anything on. To power a charger on/off use the `Switch` family (`Switch.On` / `Switch.Off`), never `Charger.Power`. Use `Charger.*` only to READ power/current/voltage/charging state.
