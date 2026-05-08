[Device Summary]
<Device "ArmRobot">
  <Service "ArmRobotType" type="value">Current status of the arm robot type. Enum values: mycobot280_pi.</Service>
  <Service "CurrentPosition" type="value">Current status of the arm robot position</Service>
  <Service "Hello" type="action">Send hello command to arm robot</Service>
  <Service "SendCommand" type="action">Send command to arm robot. List of string, separated by '|'</Service>
  <Service "SetPosition" type="action">Send position to arm robot</Service>
</Device>

# ArmRobot Examples

[Command]
Set the ArmRobot to home position
["ArmRobot.SetPosition"]

[Command]
Make the ArmRobot say hello
["ArmRobot.Hello"]

[Command]
What is the ArmRobot's current position?
["ArmRobot.CurrentPosition"]

[Command]
Check the ArmRobot type
["ArmRobot.ArmRobotType"]
