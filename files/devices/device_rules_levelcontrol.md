[Device Summary]
<Device "LevelControl">
  <Service "CurrentLevel" type="value">Current level (DOUBLE)</Service>
  <Service "MaxLevel" type="value">Maximum level (DOUBLE)</Service>
  <Service "MinLevel" type="value">Minimum level (DOUBLE)</Service>
  <Service "MoveToLevel" type="action">Set specific level</Service>
</Device>

# Rules

- A level/dimming VALUE ("50으로", "밝기 30") → `MoveToLevel` (Level 0-100; Level 0 turns the device off if it supports on/off). Read current level → `CurrentLevel`.
- Bare on/off → `Switch.On`/`Switch.Off` if the device has a Switch; otherwise `MoveToLevel` (ON→100, OFF→0).
- A relative change ("10 올려") reads `CurrentLevel` then `MoveToLevel`.
