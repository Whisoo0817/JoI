[Device Summary]
<Device "Oven">
  <Service "OvenMode" type="value">Current mode. Enum values: heating, grill, warming, defrosting, Conventional, Bake, BottomHeat, ConvectionBake, ConvectionRoast, Broil, ConvectionBroil, SteamCook, SteamBake, SteamRoast, SteamBottomHeatplusConvection, Microwave, MWplusGrill, MWplusConvection, MWplusHotBlast, MWplusHotBlast2, SlimMiddle, SlimStrong, SlowCook, Proof, Dehydrate, Others, StrongSteam, Descale, Rinse.</Service>
  <Service "AddMoreTime" type="action">Add more cooking time (in seconds)</Service>
  <Service "SetCookingParameters" type="action">Set mode and cooking time together</Service>
  <Service "SetOvenMode" type="action">Set oven mode</Service>
</Device>

# Oven Examples

[Command]
Set the Oven to bake mode
["Oven.SetOvenMode"]

[Command]
Check the current OvenMode
["Oven.OvenMode"]

[Command]
Set the oven to convection bake for 30 minutes
["Oven.SetCookingParameters"]

[Command]
Add 10 more minutes to the oven timer
["Oven.AddMoreTime"]

[Command]
When the oven finishes, do something
["Oven.OvenMode"]
