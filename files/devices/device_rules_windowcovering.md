[Device Summary]
<Device "WindowCovering">
  <Service "WindowCoveringType" type="value">Type (window, blind, shade, curtain)</Service>
  <Service "CurrentPosition" type="value">Current openness level (0-100)</Service>
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
