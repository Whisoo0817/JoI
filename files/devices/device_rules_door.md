[Device Summary]
<Device "Door">
  <Service "DoorState" type="value">Current door state. Enum values: closed, closing, open, opening, unknown.</Service>
  <Service "Close" type="action">Close the door</Service>
  <Service "Open" type="action">Open the door</Service>
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

[Command]
When the door opens, do something
["Door.DoorState"]
