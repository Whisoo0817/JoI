[Device Summary]
<Device "Siren">
  <Service "SirenMode" type="value">Return siren mode</Service>
  <Service "SetSirenMode" type="action">Turn on and sound siren in specific mode (emergency, fire, police, ambulance)</Service>
</Device>

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
