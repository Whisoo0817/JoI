# Condition Pre-Filter

Analyze the command and determine if it requires complex event tracking (device condition checks or recurring time schedules).
If the command is just a simple action (e.g., Turn on the light, Set the temperature to 20, Close the door) or contains only a simple one-time time delay (e.g., 30 minutes later, tomorrow at 8 AM), it does NOT require complex event tracking.

## Rules
Output `true` IF the command contains ANY of the following:
1. **Device Condition Check**: Checking the state, sensor value, or activity of a device (e.g., "If it rains", "If the temperature is over 30 degrees", "Whenever the door opens", "If the room is currently dark").
2. **Recurring Schedule**: An action that repeats periodically (e.g., "Every morning at 7 AM", "Every 30 minutes", "Every weekend", "On Wednesdays").

Output `false` IF the command is simply:
1. **Direct Action**: A simple command to control a device without checking conditions or recurring (e.g., "Turn on the living room light", "Turn off the TV", "Set the AC temperature to 22 degrees").
2. **One-Time Delay**: A single event or delay without conditions (e.g., "Turn off the AC 30 minutes later", "Turn on the light after 1 hour").

## Output Format
Output ONLY `true` or `false`. Do not output any other text. `true` means the command needs condition extraction. `false` means it is a simple/direct command.

## Examples

[Command]
Turn on the living room light.
false

[Command]
Set the air conditioner temperature to 24 degrees.
false

[Command]
Output the current temperature through the speaker.
false

[Command]
In 30 seconds, lock all safes with odd tags in Sector B.
false

[Command]
Change the robot cleaner to manual mode after 30 minutes.
false

[Command]
Lock all doors at 11 PM.
true

[Command]
If it's raining, close the windows.
true

[Command]
When it rains, close the windows.
true

[Command]
When the bedroom shade button is pushed, lower the shade.
true

[Command]
If the current temperature is 30 degrees or higher, turn on the AC.
true

[Command]
Open the curtains every morning at 7 AM.
true

[Command]
Whenever the door opens, send a notification.
true

[Command]
At 1 PM, open all blinds.
true

[Command]
When the button is pushed 3 times, open the valve.
true

[Command]
At noon, announce the lunch menu of the cafeteria in Building 301 through the speaker.
true

[Command]
At 5 PM, turn on the light.
true