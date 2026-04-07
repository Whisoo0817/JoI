[Device Summary]
<Device "AirQualitySensor">
  <Service "DustLevel" type="value">Indoor dust (PM10) concentration</Service>
  <Service "FineDustLevel" type="value">Indoor fine dust (PM2.5) concentration</Service>
  <Service "VeryFineDustLevel" type="value">Indoor very fine dust (PM1.0) concentration</Service>
  <Service "CarbonDioxide" type="value">Indoor carbon dioxide (CO2) concentration</Service>
  <Service "Temperature" type="value">Temperature measured by the air quality sensor</Service>
  <Service "Humidity" type="value">Humidity measured by the air quality sensor</Service>
  <Service "TvocLevel" type="value">Total Volatile Organic Compounds (TVOC) concentration</Service>
</Device>

# AirQualitySensor Examples

[Command]
Check the DustLevel of the AirQualitySensor
["AirQualitySensor.DustLevel"]

[Command]
What is the PM2.5 concentration of the AirQualitySensor?
["AirQualitySensor.FineDustLevel"]
