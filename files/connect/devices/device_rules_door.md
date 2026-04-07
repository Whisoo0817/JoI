[Device Summary]
<Device "Door">
  <Service "DoorState" type="value">Door state (open, closed, opening, closing)</Service>
  <Service "Open" type="action">Open the door</Service>
  <Service "Close" type="action">Close the door</Service>
</Device>

# Door Examples

[Command]
Open the front door
["Door.Open"]

[Command]
Close the door
["Door.Close"]

[Command]
Is the door currently open or closed?
["Door.DoorState"]
