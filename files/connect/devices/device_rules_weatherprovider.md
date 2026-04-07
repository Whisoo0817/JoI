[Device Summary]
<Device "WeatherProvider">
  <Service "CurrentWeather" type="value">Current weather state (sunny, cloudy, rain, snow)</Service>
  <Service "Temperature" type="value">Current outdoor temperature</Service>
  <Service "Humidity" type="value">Current outdoor humidity</Service>
  <Service "GetForecast" type="action">Get weather forecast for a specific location or date</Service>
</Device>

# WeatherProvider Examples

[Command]
What's the weather like today? (Ask WeatherProvider)
["WeatherProvider.CurrentWeather"]

[Command]
Check the outdoor temperature on the WeatherProvider
["WeatherProvider.Temperature"]
