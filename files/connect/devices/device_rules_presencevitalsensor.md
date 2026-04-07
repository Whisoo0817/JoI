[Device Summary]
<Device "PresenceVitalSensor">
  <Service "Presence" type="value">Human presence detection (true/false)</Service>
  <Service "HeartRate" type="value">Heart rate measurement</Service>
  <Service "RespiratoryRate" type="value">Respiratory rate measurement</Service>
</Device>

# PresenceVitalSensor Examples

[Command]
Check the HeartRate on the PresenceVitalSensor
["PresenceVitalSensor.HeartRate"]

[Command]
Is anyone present? (Ask PresenceVitalSensor)
["PresenceVitalSensor.Presence"]
