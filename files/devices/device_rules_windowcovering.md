[Device Summary]
<Device "WindowCovering">
  <Service "CurrentPosition" type="value">Current openness level (INTEGER, 0=fully closed, 100=fully open). "is closed" → CurrentPosition == 0; "is open" → > 0; "30% open" → 30.</Service>
  <Service "WindowCoveringType" type="value">Type. Enum values: window, blind, shade.</Service>
  <Service "DownOrClose" type="action">Close or lower</Service>
  <Service "SetLevel" type="action">Set specific openness level (0-100)</Service>
  <Service "Stop" type="action">Stop moving</Service>
  <Service "UpOrOpen" type="action">Open or raise</Service>
</Device>

# WindowCovering Examples

[Command]
Open the WindowCovering
["WindowCovering.UpOrOpen"]

[Command]
Close the WindowCovering
["WindowCovering.DownOrClose"]

[Command]
Set the WindowCovering level to 50%
["WindowCovering.SetLevel"]

[Command]
Check the current position of the WindowCovering
["WindowCovering.CurrentPosition"]

[Command]
When the WindowCovering is fully closed, do something
["WindowCovering.CurrentPosition"]

[Command]
Lower the WindowCovering by 20%
["WindowCovering.CurrentPosition", "WindowCovering.SetLevel"]
