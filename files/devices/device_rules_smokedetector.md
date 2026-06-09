[Device Summary]
<Device "SmokeDetector">
  <Service "Smoke" type="value">Smoke detection status (true: smoke detected, false: not detected)</Service>
</Device>

# SmokeDetector Examples

[Command]
Check if there is any smoke
["SmokeDetector.Smoke"]

[Command]
Read the smoke detection status
["SmokeDetector.Smoke"]

[Command]
When smoke is detected, send a danger notification
# why: condition reads the sensor (Smoke), then the action publishes the alert (ToastPublisher.Publish)
["SmokeDetector.Smoke", "ToastPublisher.Publish"]
