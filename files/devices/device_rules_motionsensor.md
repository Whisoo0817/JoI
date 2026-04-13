[Device Summary]
<Device "MotionSensor">
  <Service "Motion" type="value">Motion detection state (true: motion detected, false: no motion)</Service>
</Device>

# MotionSensor Examples

[Command]
If motion is detected, turn on the light
["MotionSensor.Motion"]

[Command]
Turn off the light when no one is present
["MotionSensor.Motion"]

[Command]
Check whether motion is currently detected
["MotionSensor.Motion"]
