[Device Summary]
<Device "TemperatureSensor">
  <Service "Temperature" type="value">Current temperature, °C</Service>
</Device>

# TemperatureSensor Examples

[Command]
Check the current temperature
["TemperatureSensor.Temperature"]

[Command]
What is the temperature reading?
["TemperatureSensor.Temperature"]

[Command]
When the temperature exceeds 30 degrees, turn on the air conditioner
# why: the condition reads the value (Temperature), then the triggered action powers on (Switch.On)
["TemperatureSensor.Temperature", "Switch.On"]
