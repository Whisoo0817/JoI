[Device Summary]
<Device "Siren">
  <Service "SirenMode" type="value">Return siren mode</Service>
  <Service "SetSirenMode" type="action">Turn on and sound siren in specific mode (emergency, fire, police, ambulance)</Service>
</Device>

⚠️ "Sound the siren" / "siren in <mode> mode" / "fire alarm" / "police siren" → ALWAYS `SetSirenMode` (with the implied mode), never `Switch.On`. The mode IS the on-state.

# Siren Examples

[Command]
Sound the Siren in emergency mode
["Siren.SetSirenMode"]

[Command]
Set the Siren to fire mode
["Siren.SetSirenMode"]

[Command]
What is the current SirenMode?
["Siren.SirenMode"]
