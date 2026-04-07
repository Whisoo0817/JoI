[Device Summary]
<Device "Dishwasher">
  <Service "DishwasherMode" type="value">Current mode</Service>
  <Service "SetDishwasherMode" type="action">Set dishwasher mode (eco, intense, auto, quick, rinse, dry)</Service>
</Device>

# Dishwasher Examples

[Command]
Set the Dishwasher to eco mode
["Dishwasher.SetDishwasherMode"]

[Command]
What mode is the Dishwasher in?
["Dishwasher.DishwasherMode"]
