[Device Summary]
<Device "Battery">
  <Service "Level" type="value">Remaining battery level as a percentage (0-100)</Service>
  <Service "IsCharging" type="value">Whether the battery is currently charging (BOOL)</Service>
  <Service "Capacity" type="value">Nominal full-charge capacity in mAh (INTEGER)</Service>
  <Service "TimeRemaining" type="value">Estimated seconds until discharged at current usage (INTEGER)</Service>
  <Service "Voltage" type="value">Battery voltage in millivolts (DOUBLE)</Service>
</Device>

# Rules

- Battery is a **read-only** capability — there are NO actions. Pick a value service for the quantity asked.
- "배터리 (잔량)/충전 상태/battery (level)" → `Level`. "충전 중인지" → `IsCharging`. Default a bare "배터리" to `Level`.

# Battery Examples

[Command]
What's the battery level?
["Battery.Level"]

[Command]
When the battery drops below 20%, notify me
["Battery.Level", "ToastPublisher.Publish"]

[Command]
Is the device charging?
["Battery.IsCharging"]
