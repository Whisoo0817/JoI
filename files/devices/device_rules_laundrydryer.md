[Device Summary]
<Device "LaundryDryer">
  <Service "LaundryDryerMode" type="value">Current mode. Enum values: auto, quick, quiet, lownoise, lowenergy, vacation, min, max, night, day, normal, delicate, heavy, whites.</Service>
  <Service "SpinSpeed" type="value">Current spin speed (INTEGER)</Service>
  <Service "SetLaundryDryerMode" type="action">Set laundry dryer mode</Service>
  <Service "SetSpinSpeed" type="action">Set spin speed</Service>
</Device>

# LaundryDryer Examples

[Command]
Set the LaundryDryer to delicate mode
["LaundryDryer.SetLaundryDryerMode"]

[Command]
Read the current LaundryDryerMode
["LaundryDryer.LaundryDryerMode"]

[Command]
Set the LaundryDryer spin speed to 800
["LaundryDryer.SetSpinSpeed"]

[Command]
When the LaundryDryer finishes, do something
["LaundryDryer.LaundryDryerMode"]

[Command]
Increase the LaundryDryer spin speed by 100
["LaundryDryer.SpinSpeed", "LaundryDryer.SetSpinSpeed"]
