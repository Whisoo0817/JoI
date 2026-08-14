[Device Summary]
<Device "ArmRobotDetail">
  <Service "MoveToHome" type="action">Move all axes to the home (origin) pose (arg: Speed 1-100)</Service>
  <Service "MoveSingleAxis" type="action">Move one joint axis to an absolute angle (args: Axis 1-6, Angle -180..180 deg, Speed 1-100)</Service>
  <Service "MoveToAngles" type="action">Move all six axes to absolute angles (args: Angles "a1|a2|a3|a4|a5|a6" deg, Speed 1-100)</Service>
  <Service "SetSpeed" type="action">Set the default movement speed for subsequent motions (arg: Speed 1-100)</Service>
  <Service "GreetMotion" type="action">Perform a greeting (wave) gesture (args: Speed 1-100, RepeatCount 1-10)</Service>
  <Service "RefuseMotion" type="action">Perform a refusal (shake) gesture (args: Speed 1-100, RepeatCount 1-10)</Service>
  <Service "AddMotion" type="action">Save a named motion trajectory for later replay (args: Name, Waypoints JSON string)</Service>
  <Service "PlayMotion" type="action">Play a saved motion trajectory by name (arg: Name)</Service>
  <Service "GetMotion" type="value">Return a saved trajectory's waypoints by name, as JSON</Service>
  <Service "ListMotions" type="value">List the names of all saved trajectories, as JSON</Service>
</Device>

# ArmRobotDetail Rules

Fine-grained motion control for the arm robot (6-axis, mycobot280-class). This is
the low-level counterpart to the `ArmRobot` skill: prefer these services whenever
the command specifies joint angles, gestures, speed, or named trajectories.

- **Greeting / waving → `GreetMotion`** ("인사해", "손 흔들어", "say hello", "wave"). Use this, NOT `ArmRobot.Hello`.
- **Refusing / shaking → `RefuseMotion`** ("거절해", "고개 저어", "shake", "refuse").
- **Home / origin pose → `MoveToHome`** ("홈으로", "원점으로", "go home", "reset pose").
- **One joint to an angle → `MoveSingleAxis`** ("3번 축을 45도로", "move axis 2 to -30 degrees"). Axis is 1-6 (1=shoulder_pan, 2=shoulder_lift, 3=elbow_flex, 4=wrist_flex, 5=wrist_roll, 6=gripper).
- **All six joints at once → `MoveToAngles`** (a full pose given as six angles, e.g. "0, -15, -15, -15, -90, 0").
- **Default speed only → `SetSpeed`** ("천천히 움직여", "속도 50으로") when the command sets a speed without also commanding a move. If a move is commanded with a speed, pass Speed to that move instead.
- **Save a trajectory → `AddMotion`; replay → `PlayMotion`; inspect → `GetMotion`; list → `ListMotions`** ("이 동작을 hello로 저장", "hello 재생해", "저장된 동작 목록").
- Speed is always 1-100. RepeatCount (greet/refuse) is 1-10. Angles are degrees in [-180, 180].

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
