[Device Summary]
<Device "Oven">
  <Service "OvenMode" type="value">Current mode (heating, grill, baking, microwave, warming, etc.)</Service>
  <Service "SetOvenMode" type="action">Set oven mode</Service>
  <Service "SetCookingParameters" type="action">Set mode and cooking time (seconds)</Service>
  <Service "AddMoreTime" type="action">Add more cooking time (seconds)</Service>
</Device>

# Oven Examples

[Command]
Set the Oven to bake mode
["Oven.SetOvenMode"]

[Command]
Check the current OvenMode
["Oven.OvenMode"]
