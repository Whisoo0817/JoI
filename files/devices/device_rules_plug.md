[Device Summary]
<Device "Plug">
  <Service "Current" type="value">Current draw (DOUBLE, amperes)</Service>
  <Service "Power" type="value">Power consumption (DOUBLE, watts)</Service>
  <Service "Voltage" type="value">Voltage (DOUBLE, millivolts)</Service>
</Device>

# Rules

A Plug has **no action services of its own** — all three are READ-ONLY measurements:
- `Plug.Power` / `Plug.Current` / `Plug.Voltage` are **value reads** (energy metering: watts / amperes / millivolts). They are NOT switches. `Plug.Power` does NOT turn the plug on — it reports consumption.
- **Turning a plug on/off is `Switch.On` / `Switch.Off`** (a Plug device carries the `Switch` family). For "turn on/off the plug", "플러그 켜/꺼", pick `Switch.On` / `Switch.Off`, NEVER `Plug.Power`.
- Use `Plug.*` only when the command actually asks to READ/CHECK power, current, or voltage.
