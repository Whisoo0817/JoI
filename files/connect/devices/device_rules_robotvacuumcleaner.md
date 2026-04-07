[Device Summary]
<Device "RobotVacuumCleaner">
  <Service "RobotVacuumCleanerRunMode" type="value">Run mode (auto, spot, repeat, manual, stop, map)</Service>
  <Service "SetRobotVacuumCleanerRunMode" type="action">Set robot vacuum run mode</Service>
  <Service "RobotVacuumCleanerCleaningMode" type="value">Cleaning mode</Service>
  <Service "SetRobotVacuumCleanerCleaningMode" type="action">Set robot vacuum cleaning mode</Service>
</Device>

# RobotVacuumCleaner Examples

[Command]
Set the RobotVacuumCleaner to auto mode
["RobotVacuumCleaner.SetRobotVacuumCleanerRunMode"]

[Command]
What is the current cleaning mode of the RobotVacuumCleaner?
["RobotVacuumCleaner.RobotVacuumCleanerCleaningMode"]
