[Device Summary]
<Device "MultiButton">
  <Service "Button1" type="value">State of button1 (pushed, held, etc.)</Service>
  <Service "Button2" type="value">State of button2</Service>
  <Service "Button3" type="value">State of button3</Service>
  <Service "Button4" type="value">State of button4</Service>
</Device>

# MultiButton Examples

[Command]
If the first button of the MultiButton is pushed
["MultiButton.Button1"]

[Command]
Check if MultiButton button 3 is held
["MultiButton.Button3"]
