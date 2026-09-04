# @ArgResolve

`MoveSingleAxis` — `Axis` INTEGER 1-6, `Angle` DOUBLE -180..180 (deg), `Speed` INTEGER 1-100.
`MoveToAngles` — `Angles` STRING, six pipe-separated degree values in axis order
`shoulder_pan|shoulder_lift|elbow_flex|wrist_flex|wrist_roll|gripper` (e.g. `0|-15|-15|-15|-90|0`); `Speed` 1-100.
`MoveToHome` / `SetSpeed` — `Speed` INTEGER 1-100.
`GreetMotion` / `RefuseMotion` — `Speed` INTEGER 1-100, `RepeatCount` INTEGER 1-10.
`AddMotion` — `Name` STRING, `Waypoints` STRING (JSON list of `{"positions": {motor: deg}, "speed": 0-1023, "delay": sec}`).
`PlayMotion` / `GetMotion` — `Name` STRING.

Default when unspeced: `Speed` = 50, `RepeatCount` = 2.

```
[Command] Wave hello twice.
[Selected Services] ["ArmRobotDetail.GreetMotion"]
Output:
{"ArmRobotDetail.GreetMotion": {"Speed": 50, "RepeatCount": 2}}
```

```
[Command] Move the elbow joint to 45 degrees.
[Selected Services] ["ArmRobotDetail.MoveSingleAxis"]
Output:
{"ArmRobotDetail.MoveSingleAxis": {"Axis": 3, "Angle": 45, "Speed": 50}}
```
