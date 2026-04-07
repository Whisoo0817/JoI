[Device Summary]
<Device "ContactSensor">
  <Service "Contact" type="value">Contact state (true: closed, false: open). Typically attached to doors or windows — use this to detect if a door/window is open or closed.</Service>
</Device>

# ContactSensor Examples

[Command]
Is the front door closed? (Ask ContactSensor)
["ContactSensor.Contact"]

[Command]
Check if the window is open (Ask ContactSensor)
["ContactSensor.Contact"]
