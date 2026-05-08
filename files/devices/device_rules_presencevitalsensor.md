[Device Summary]
<Device "PresenceVitalSensor">
  <Service "Awakeness" type="value">Awakeness level (DOUBLE)</Service>
  <Service "Distance" type="value">Distance to the detected person (DOUBLE)</Service>
  <Service "DwellTime" type="value">Duration of presence (DOUBLE)</Service>
  <Service "HeartRate" type="value">Heart rate measurement (DOUBLE)</Service>
  <Service "MovementIndex" type="value">Movement intensity index (DOUBLE)</Service>
  <Service "Presence" type="value">Human presence detection (true/false)</Service>
  <Service "RespiratoryRate" type="value">Respiratory rate measurement (DOUBLE)</Service>
</Device>

# PresenceVitalSensor Examples

[Command]
Check the HeartRate on the PresenceVitalSensor
["PresenceVitalSensor.HeartRate"]

[Command]
Is anyone present?
["PresenceVitalSensor.Presence"]

[Command]
Read the respiratory rate
["PresenceVitalSensor.RespiratoryRate"]

[Command]
When someone is detected, do something
["PresenceVitalSensor.Presence"]
