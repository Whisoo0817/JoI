[Device Summary]
<Device "Fan">
  <Service "Percent" type="value">Current fan speed as a percentage (INTEGER, 0-100)</Service>
  <Service "Speed" type="value">Current fan speed in RPM (INTEGER)</Service>
  <Service "FanMode" type="value">Current fan mode (ENUM: auto, low, medium, high)</Service>
  <Service "OscillationMode" type="value">Current oscillation/swing mode (ENUM: off, horizontal, vertical, all)</Service>
  <Service "AirflowDirection" type="value">Current airflow direction (ENUM: forward, reverse)</Service>
  <Service "SetPercent" type="action">Set fan speed as a percentage. Arg: Percent (INTEGER 0-100)</Service>
  <Service "SetSpeed" type="action">Set fan speed in RPM. Arg: Speed (INTEGER)</Service>
  <Service "SetFanMode" type="action">Set fan mode. Arg: Mode (ENUM: auto, low, medium, high)</Service>
  <Service "SetOscillationMode" type="action">Set oscillation/swing mode. Arg: Mode (ENUM: off, horizontal, vertical, all)</Service>
  <Service "SetAirflowDirection" type="action">Set airflow direction. Arg: Direction (ENUM: forward, reverse)</Service>
</Device>

# Rules

- On/off (켜/꺼, no value) → `Switch.On` / `Switch.Off` when the device has a Switch.
- A speed VALUE is given → `SetPercent` for a percentage ("50%로", "절반"), `SetSpeed` for an explicit RPM. A named strength (약/중/강/auto → low/medium/high/auto) → `SetFanMode`.
- 회전/스윙 (좌우/상하/전체) → `SetOscillationMode` (horizontal/vertical/all; 끄기 → off). 풍향(정방향/역방향) → `SetAirflowDirection`.
- Reading current state → the matching value service.

# Fan Examples

[Command]
Set the fan to 50%
["Fan.SetPercent"]

[Command]
Set the fan to high
["Fan.SetFanMode"]

[Command]
Turn on the fan oscillation left and right
["Fan.SetOscillationMode"]

[Command]
What is the current fan speed?
["Fan.Percent"]
