[Device Summary]
<Device "RiceCooker">
  <Service "RiceCookerMode" type="value">Current operating mode (cooking / keepWarm / reheating / autoClean / soakInnerPot)</Service>
  <Service "SetRiceCookerMode" type="action">Set rice cooker mode (cooking / keepWarm / reheating / autoClean / soakInnerPot)</Service>
  <Service "SetCookingParameters" type="action">Set mode and additional cooking time together</Service>
  <Service "AddMoreTime" type="action">Add extra cooking time (in seconds)</Service>
</Device>

# RiceCooker Examples

[Command]
Start cooking rice
["RiceCooker.SetRiceCookerMode"]

[Command]
Keep the rice warm
["RiceCooker.SetRiceCookerMode"]

[Command]
Reheat the rice
["RiceCooker.SetRiceCookerMode"]

[Command]
Cook rice for 30 more minutes
["RiceCooker.AddMoreTime"]

[Command]
Start cooking rice with keep-warm mode for 40 minutes
["RiceCooker.SetCookingParameters"]

[Command]
Check the current rice cooker mode
["RiceCooker.RiceCookerMode"]

[Command]
Run the auto-clean cycle
["RiceCooker.SetRiceCookerMode"]
