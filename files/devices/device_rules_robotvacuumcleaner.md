[Device Summary]
<Device "RobotVacuumCleaner">
  <Service "RobotVacuumCleanerCleaningMode" type="value">Cleaning mode. Enum values: auto, part, repeat, manual, stop, map.</Service>
  <Service "RobotVacuumCleanerRunMode" type="value">Run mode. Enum values: homing, idle, charging, alarm, powerOff, reserve, point, after, cleaning, pause, washingMop.</Service>
  <Service "RobotVacuumCleanerOperatingState" type="value">Read-only operational state. Enum values: stopped, running, paused, seekingCharger, charging, docked, stuck, dustBinFull, waterTankEmpty, ... (use to CHECK status, e.g. "is it stuck / docked / cleaning"; there is NO setter for it).</Service>
  <Service "SetRobotVacuumCleanerCleaningMode" type="action">Set cleaning mode</Service>
  <Service "SetRobotVacuumCleanerRunMode" type="action">Set run mode</Service>
</Device>

# Rules — RunMode vs CleaningMode (CRITICAL)

The two `Set...Mode` services accept **different enum sets**:

| User intent | Service | Example enum values |
|---|---|---|
| "go home", "dock", "charge" | **RunMode** | `homing`, `charging` |
| "pause", "idle", "power off" | **RunMode** | `pause`, `idle`, `powerOff` |
| "auto", "part", "repeat", "manual", "map" (how to clean) | **CleaningMode** | matching enum |
| "stop cleaning" | **CleaningMode** | `stop` |

NOTE: `stop` is a **CleaningMode** value. `homing`, `pause`, `idle` are **RunMode** values.

# RobotVacuumCleaner Examples

[Command]
Start automatic cleaning
["RobotVacuumCleaner.SetRobotVacuumCleanerCleaningMode"]

[Command]
Stop the robot vacuum
["RobotVacuumCleaner.SetRobotVacuumCleanerCleaningMode"]

[Command]
Send the robot vacuum home to charge
["RobotVacuumCleaner.SetRobotVacuumCleanerRunMode"]

[Command]
Pause the robot vacuum
["RobotVacuumCleaner.SetRobotVacuumCleanerRunMode"]

[Command]
What is the current run mode of the RobotVacuumCleaner?
["RobotVacuumCleaner.RobotVacuumCleanerRunMode"]

[Command]
What is the current cleaning mode of the RobotVacuumCleaner?
["RobotVacuumCleaner.RobotVacuumCleanerCleaningMode"]
