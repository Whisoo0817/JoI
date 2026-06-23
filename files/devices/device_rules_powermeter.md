[Device Summary]
<Device "PowerMeter">
  <Service "Power" type="value">Instantaneous real (active) power in watts (W). Positive = import, negative = export (DOUBLE)</Service>
  <Service "Voltage" type="value">RMS voltage at the device terminals in volts (V) (DOUBLE)</Service>
  <Service "Current" type="value">RMS current through the device in amperes (A) (DOUBLE)</Service>
  <Service "PowerMode" type="value">Electrical power mode (ENUM: unknown, dc, ac)</Service>
</Device>

# Rules

- PowerMeter is **read-only** (instantaneous electrical metrics) — no actions.
- "전력/소비전력/W/와트" → `Power`. "전압/V" → `Voltage`. "전류/A" → `Current`. Default a bare "전력" to `Power`.
- This is INSTANTANEOUS power (W). For accumulated energy over time (kWh) use the `EnergyMeter` skill instead.

# PowerMeter Examples

[Command]
How much power is the plug drawing right now?
["PowerMeter.Power"]

[Command]
When the power draw exceeds 2000W, send an alert
["PowerMeter.Power", "ToastPublisher.Publish"]
