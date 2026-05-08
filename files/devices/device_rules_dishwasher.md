[Device Summary]
<Device "Dishwasher">
  <Service "DishwasherMode" type="value">Current mode. Enum values: eco, intense, auto, quick, rinse, dry.</Service>
  <Service "SetDishwasherMode" type="action">Set dishwasher mode</Service>
</Device>

# Dishwasher Examples

[Command]
Set the Dishwasher to eco mode
["Dishwasher.SetDishwasherMode"]

[Command]
What mode is the Dishwasher in?
["Dishwasher.DishwasherMode"]

[Command]
Switch the Dishwasher to quick mode
["Dishwasher.SetDishwasherMode"]

[Command]
When the Dishwasher finishes its cycle, do something
["Dishwasher.DishwasherMode"]
