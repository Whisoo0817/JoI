[Device Summary]
<Device "LevelControl">
  <Service "Level" type="value">Current level (0-100%)</Service>
  <Service "MoveToLevel" type="action">Set specific level</Service>
</Device>

# LevelControl Examples

[Command]
Set the LevelControl level to 50
["LevelControl.MoveToLevel"]

[Command]
Read the LevelControl level
["LevelControl.Level"]
