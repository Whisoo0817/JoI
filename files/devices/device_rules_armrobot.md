[Device Summary]
<Device "ArmRobot">
  <Service "ArmRobotType" type="value">Current status of the arm robot type. Enum values: mycobot280_pi.</Service>
  <Service "CurrentPosition" type="value">Current status of the arm robot position</Service>
  <Service "Hello" type="action">Send hello command to arm robot</Service>
  <Service "SendCommand" type="action">Send command to arm robot. List of string, separated by '|'</Service>
  <Service "SetPosition" type="action">Send position to arm robot</Service>
</Device>

# Rules

- A named position (home/hello/refuse) → `SetPosition`. A raw command string → `SendCommand`. Read current position/type → `CurrentPosition`/`ArmRobotType`.
- Gestures (greeting/waving, refusing/shaking) are handled by the `ArmRobotDetail` skill — use `ArmRobotDetail.GreetMotion` / `ArmRobotDetail.RefuseMotion`, NOT this device's `Hello`.
