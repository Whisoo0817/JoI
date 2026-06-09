[Device Summary]
<Device "AirQualitySensor">
  <Service "DustLevel" type="value">Indoor dust (PM10) concentration, µg/m³</Service>
  <Service "FineDustLevel" type="value">Indoor fine dust (PM2.5) concentration, µg/m³</Service>
  <Service "VeryFineDustLevel" type="value">Indoor very fine dust (PM1.0) concentration, µg/m³</Service>
  <Service "CarbonDioxide" type="value">Indoor carbon dioxide (CO2) concentration, ppm</Service>
  <Service "Temperature" type="value">Temperature measured by the air quality sensor, °C</Service>
  <Service "Humidity" type="value">Relative humidity measured by the air quality sensor, %</Service>
  <Service "TvocLevel" type="value">Total Volatile Organic Compounds (TVOC) concentration, ppb</Service>
</Device>

# Rules

This is a multi-value air monitor — pick the service matching the quantity asked:
- dust / 미세먼지: PM10 → `DustLevel`, PM2.5 (fine) → `FineDustLevel`, PM1.0 (ultrafine) → `VeryFineDustLevel`
- CO2 / 이산화탄소 → `CarbonDioxide`; TVOC / 휘발성 유기화합물 → `TvocLevel`
- temperature / 온도 → `Temperature`; humidity / 습도 → `Humidity`
- a bare "air quality / 공기질" with no specific quantity: read the pollutant the command implies; if truly generic, `FineDustLevel` (PM2.5) is the conventional headline metric.

# AirQualitySensor Examples

[Command]
Check the PM10 dust level
["AirQualitySensor.DustLevel"]

[Command]
What is the PM2.5 concentration of the AirQualitySensor?
["AirQualitySensor.FineDustLevel"]

[Command]
Read the CO2 level
["AirQualitySensor.CarbonDioxide"]

[Command]
Tell me the TVOC concentration
["AirQualitySensor.TvocLevel"]

[Command]
When the CO2 level exceeds 1000 ppm, send a notification
["AirQualitySensor.CarbonDioxide", "ToastPublisher.Publish"]
