[Device Summary]
<Device "MotionSensor">
  <Service "Motion" type="value">Motion detection state (true: motion detected, false: no motion)</Service>
</Device>

# MotionSensor Examples

[Command]
Check whether motion is currently detected
["MotionSensor.Motion"]

[Command]
When motion is detected, do something
["MotionSensor.Motion"]

[Command]
When there is no motion for a while, do something
["MotionSensor.Motion"]
