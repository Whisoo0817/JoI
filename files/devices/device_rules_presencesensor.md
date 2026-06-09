[Device Summary]
<Device "PresenceSensor">
  <Service "Presence" type="value">Human presence detection (true: present, false: not present)</Service>
</Device>

# PresenceSensor Examples

[Command]
Is anyone in the room?
["PresenceSensor.Presence"]

[Command]
Check the presence status
["PresenceSensor.Presence"]

[Command]
When someone enters the room, turn on the light
# why: trigger reads presence (Presence), then acts (Switch.On)
["PresenceSensor.Presence", "Switch.On"]
