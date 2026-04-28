[Device Summary]
<Device "RobotVacuumCleaner">
  <Service "RobotVacuumCleanerRunMode" type="value">Run mode (auto, spot, repeat, manual, stop, map)</Service>
  <Service "SetRobotVacuumCleanerRunMode" type="action">Set robot vacuum run mode (auto/spot/repeat/manual/stop/map)</Service>
  <Service "RobotVacuumCleanerCleaningMode" type="value">Cleaning mode (different enum from RunMode)</Service>
  <Service "SetRobotVacuumCleanerCleaningMode" type="action">Set robot vacuum cleaning mode</Service>
</Device>

# Rules — RunMode vs CleaningMode (CRITICAL)

The two `Set...Mode` services accept **different enum sets**. Pick by the user's intent word:

| User intent | Service | Enum value |
|---|---|---|
| "stop", "halt", "turn off" (when about playback/operation) | **RunMode** | `"stop"` |
| "auto mode", "automatic" | **RunMode** | `"auto"` |
| "spot", "repeat", "manual", "map" | **RunMode** | matching enum |
| Any cleaning-style adjective ("intensive cleaning", "quiet cleaning", etc. — phrasings about HOW to clean rather than WHEN/WHETHER to run) | **CleaningMode** | from CleaningMode enum |

⚠️ **"stop" is a RunMode value, NOT a CleaningMode value.** Never call `SetRobotVacuumCleanerCleaningMode("stop")` — it's invalid.

# RobotVacuumCleaner Examples

[Command]
Set the robot vacuum to auto mode
<Reasoning>
"auto" is in the RunMode enum → use SetRobotVacuumCleanerRunMode.
</Reasoning>
["RobotVacuumCleaner.SetRobotVacuumCleanerRunMode"]

[Command]
Stop the robot vacuum
<Reasoning>
"stop" is in the RunMode enum → use SetRobotVacuumCleanerRunMode (Mode="stop"). NOT CleaningMode.
</Reasoning>
["RobotVacuumCleaner.SetRobotVacuumCleanerRunMode"]

[Command]
What is the current cleaning mode of the RobotVacuumCleaner?
<Reasoning>
Asking about cleaning mode value → read CleaningMode.
</Reasoning>
["RobotVacuumCleaner.RobotVacuumCleanerCleaningMode"]
