[Device Summary]
<Device "WindowCovering">
  <Service "WindowCoveringType" type="value">Type (window, blind, shade, curtain)</Service>
  <Service "CurrentPosition" type="value">Current openness (0 = fully closed, 100 = fully open). "is closed" → CurrentPosition == 0; "is open" → > 0; "30% open" → 30.</Service>
  <Service "UpOrOpen" type="action">Open or Raise</Service>
  <Service "DownOrClose" type="action">Close or Lower</Service>
  <Service "Stop" type="action">Stop moving</Service>
  <Service "SetLevel" type="action">Set specific openness level (0-100)</Service>
</Device>

# WindowCovering Examples

[Command]
Open the WindowCovering
["WindowCovering.UpOrOpen"]

[Command]
Set the WindowCovering level to 50%
["WindowCovering.SetLevel"]

[Command]
Check the current position of the WindowCovering
["WindowCovering.CurrentPosition"]
