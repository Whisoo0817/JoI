[Device Summary]
<Device "ArmRobot">
  <Service "ArmRobotType" type="value">Robot type</Service>
  <Service "CurrentPosition" type="value">Current position status</Service>
  <Service "SendCommand" type="action">Send commands to the robot (multiple commands separated by '|')</Service>
  <Service "SetPosition" type="action">Set to a specific position (home, hello, refuse)</Service>
  <Service "Hello" type="action">Perform a greeting action</Service>
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
