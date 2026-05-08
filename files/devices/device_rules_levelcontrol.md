[Device Summary]
<Device "LevelControl">
  <Service "CurrentLevel" type="value">Current level (DOUBLE)</Service>
  <Service "MaxLevel" type="value">Maximum level (DOUBLE)</Service>
  <Service "MinLevel" type="value">Minimum level (DOUBLE)</Service>
  <Service "MoveToLevel" type="action">Set specific level</Service>
</Device>

# LevelControl Examples

[Command]
Set the LevelControl level to 50
["LevelControl.MoveToLevel"]

[Command]
Read the current level of the LevelControl
["LevelControl.CurrentLevel"]

[Command]
What is the maximum level of the LevelControl?
["LevelControl.MaxLevel"]

[Command]
When the level reaches the minimum, do something
["LevelControl.CurrentLevel"]
