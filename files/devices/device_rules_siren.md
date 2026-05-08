[Device Summary]
<Device "Siren">
  <Service "SirenMode" type="value">Current siren mode. Enum values: emergency, fire, police, ambulance.</Service>
  <Service "SetSirenMode" type="action">Activate siren in specified mode</Service>
</Device>

WARNING: "Sound the siren" / "fire alarm" / "police siren" → ALWAYS use SetSirenMode (with the implied mode). The mode IS the activation — there is no separate on/off.

# Siren Examples

[Command]
Sound the Siren in emergency mode
["Siren.SetSirenMode"]

[Command]
Set the Siren to fire mode
["Siren.SetSirenMode"]

[Command]
Activate the police siren
["Siren.SetSirenMode"]

[Command]
What is the current SirenMode?
["Siren.SirenMode"]
