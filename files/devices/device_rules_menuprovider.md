[Device Summary]
<Device "MenuProvider">
  <Service "TodayMenu" type="value">Entire menu for today</Service>
  <Service "TodayPlace" type="value">Today's dining location</Service>
  <Service "GetMenu" type="action">Get menu for a specific date or meal time</Service>
</Device>

# MenuProvider Examples

[Command]
Show me today's menu from the MenuProvider
["MenuProvider.TodayMenu"]

[Command]
What is the lunch menu for tomorrow?
["MenuProvider.GetMenu"]
