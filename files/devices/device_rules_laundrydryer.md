[Device Summary]
<Device "LaundryDryer">
  <Service "LaundryDryerMode" type="value">Current mode (auto, quick, quiet, lowNoise, lowPower, vacation, minimum, maximum, night, day, normal, delicate, strong, whites)</Service>
  <Service "SpinSpeed" type="value">Current spin speed (0-100)</Service>
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
