[Device Summary]
<Device "Siren">
  <Service "SirenMode" type="value">Current siren mode. Enum values: emergency, fire, police, ambulance. NOTE: no "off" / "normal" / "stop" value exists in this enum.</Service>
  <Service "SetSirenMode" type="action">Activate siren in specified mode (sounds the siren).</Service>
</Device>

Siren devices in this catalog ALSO carry `Switch` in their category. That means:
- **Sounding / activating** the siren (any "sound", "fire alarm", "police siren", mode change) → `Siren.SetSirenMode` with the implied mode argument.
- **Stopping / turning off / silencing** the siren → `Switch.Off` (the Switch capability). Do NOT pass `Mode=off|normal|stop` to `SetSirenMode` — the enum has no such value.
- **Checking current state** (whether the siren is sounding) → `Switch.Switch` (boolean).
- **Reading what mode it is in** → `Siren.SirenMode`.
