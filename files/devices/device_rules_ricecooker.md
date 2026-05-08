[Device Summary]
<Device "RiceCooker">
  <Service "RiceCookerMode" type="value">Current operating mode. Enum values: cooking, keepWarm, reheating, autoClean, soakInnerPot.</Service>
  <Service "AddMoreTime" type="action">Add extra cooking time (in seconds)</Service>
  <Service "SetCookingParameters" type="action">Set mode and cooking time together</Service>
  <Service "SetRiceCookerMode" type="action">Set rice cooker mode</Service>
</Device>

# Selection Rules

- If the command specifies BOTH a mode AND a duration → pick `SetCookingParameters`.
- If the command specifies only a mode change (no duration) → pick `SetRiceCookerMode`.
- If the command says "add N more minutes" → pick `AddMoreTime`.
- If the command asks the current mode → pick `RiceCookerMode`.

# RiceCooker Examples

[Command]
Start cooking rice
["RiceCooker.SetRiceCookerMode"]

[Command]
Keep the rice warm
["RiceCooker.SetRiceCookerMode"]

[Command]
Cook rice for 30 more minutes
["RiceCooker.AddMoreTime"]

[Command]
Start cooking rice in reheating mode for 10 minutes
["RiceCooker.SetCookingParameters"]

[Command]
Check the current rice cooker mode
["RiceCooker.RiceCookerMode"]

[Command]
When the rice cooker finishes cooking, do something
["RiceCooker.RiceCookerMode"]
