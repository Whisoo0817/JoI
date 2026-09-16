# TODO — depth execution of the remaining 72 IN_SCOPE requests

Decision (whisoo, 2026-09-14): encode and execute all 92 IN_SCOPE requests, not only the 20 depth cases. Deferred;
E2 comes first.

The 20 completed depth cases are unchanged (`../E1_SUMMARY.md`). Before starting:
- update protocol §6 (depth subset = all 92 IN_SCOPE) and §9, and state how the 20 already done are reported
  alongside the 72 (they were selected for variation, the 72 are the rest, not a random sample);
- keep the same freeze discipline per case: interpretation, assumptions, histories and expected ACTION trace
  hashed before any IR; author semantic audit; reference execution; JoI fallback only for partial/impossible;
  Explorer auxiliary;
- ask the author one plain-language behavior question per case where the text leaves a choice open.

Source types: official 22, research 16, elicited 17, community 17.

| Corpus ID | Source type | R/B (author) | Requirement |
|---|---|---|---|
| E1-013 | elicited | R1, R3 | the smart stove should automatically shut off if it detects no pot or anything for more than 5 minutes |
| E1-014 | elicited | R1, R3 | the refridgerator should alarm if the door is open for longer than 5 minutes |
| E1-016 | elicited | R1 | My smart vacuum should always return to its base to charge when low on power. |
| E1-019 | elicited | R1 | Pause dishwasher if other devices need hot water. |
| E1-020 | elicited | R1, R6 | Never run the washing machine and the dish washer at the same time. |
| E1-021 | elicited | R9 | Start to mow the lawn at 8 am once a week. |
| E1-022 | elicited | R9 | Give the pets their food at 6am every day and at 6pm. |
| E1-023 | elicited | R1, B3 | smart sprinkler should never activate when it has recently rained |
| E1-024 | elicited | R3 | My smart sprinkler should never be on more than 10 minutes every 2 days. |
| E1-025 | elicited | R2, R9 | Never test the CO detector after 10 PM |
| E1-026 | elicited | R1, R6 | A smart light should only come on when it is a certain brightness in the room or a user activates it manually. |
| E1-029 | elicited | R2, B3 | the lock should lock 10 seconds after you close the door |
| E1-030 | elicited | R1 | Smart tv should always turn off when idle for 1 hour. |
| E1-031 | elicited | R1, R6 | The Smart TV in the children's room should never turn on whenever the toothbrush has not been used at least twice that day |
| E1-032 | elicited | R6 | My smart window should never be opened while the AC is on. |
| E1-033 | elicited | R9 | My smart garage door should always be opened on weekdays from 5pm to 6pm. |
| E1-035 | elicited | R1, R3 | My smart TV should turn off whenever it has been empty of people for more than 10 minutes. |
| E1-038 | research | R1, R6 | If I receive an email from JohnDoe@gmail.com then blink lights to notify me. |
| E1-039 | research | R1 | Turn on the lights when the sun sets. |
| E1-040 | research | R1, R6, R9 | If it is 7:00PM then turn on the lights in my bedroom. |
| E1-041 | research | R1 | Blink the lights if someone is at my front door. |
| E1-042 | research | R1 | The lighting in my bedroom should be on when I am there and off when I am not there. |
| E1-043 | research | R1, R6 | If it begins to rain then change the light colors to blue. |
| E1-044 | research | R1 | When I close the kitchen door, lock the door and turn off the kitchen light. |
| E1-045 | research | R1 | If I get less than 5 hours of sleep, put on a pot o’ coffee |
| E1-046 | research | R9 | You want the lights to turn on at 6:00 pm every day |
| E1-047 | research | R1, R6, R9 | You want to be notified, via email, should a person be detected in the house while everyone’s at work (9:00 am - 5:00 pm every day) |
| E1-048 | research | R5, R6 | You want the thermostat to be off as much as possible, unless the temperature outside is below 40 degrees, in which case the thermostat should be set to 72 degrees. |
| E1-049 | research | R1, R6, R9 | You want a pot of coffee to be brewed when it’s below 40 degrees outside, but only before 10:00 am every day. |
| E1-050 | research | R9 | If the time is 6:00 pm, then turn the lights on |
| E1-051 | research | R1, R6, R9 | If I arrive at home and the time is between 6:00 - 11:00 pm, then turn the lights on |
| E1-052 | research | R1, R6 | If it is snowing, then turn the thermostat to 75 degrees F |
| E1-053 | research | R1, R5, R6, R9 | If the time is between 7:00 am and 10:00 am and the outside temperature is below 40 degrees, then brew a pot of coffee |
| E1-054 | official | R1 | When a switch is moved to the on position, turn on a light. |
| E1-055 | official | R9 | At 10pm, dim the lights and close the blinds. |
| E1-056 | official | R1 | When the first person comes home, turn off cameras. |
| E1-057 | official | R1 | When the home is unoccupied, run the vacuum; when someone is home, stop the vacuum. |
| E1-058 | official | R1, R9 | After dark, when the TV is on, dim the light and lower the blinds. |
| E1-059 | official | R1 | If it is cool, open blinds, turn on fans, and adjust thermostats. |
| E1-060 | official | R1 | If it is warm, close blinds, turn on fans, and adjust thermostats. |
| E1-062 | official | R1, R6 | If one light is turned on, turn the other on, and if one light is turned off, turn the other off. |
| E1-063 | official | R1 | When smoke is detected, flash lights red and blue. |
| E1-064 | official | R1 | When indoor air quality is poor turn on air purifier at high speed. |
| E1-065 | official | R1, R9 | At night, when a lock is unlocked, turn on the light at full brightness. |
| E1-066 | official | R1 | When carbon monoxide is detected, flash the lights. |
| E1-067 | official | R1, R2, R6 | When motion is detected, turn on the lights, then turn them off after five minutes of stillness. |
| E1-068 | official | R1, R2, R6 | When an occupant is detected, turn on the lights, then turn them off after five minutes. |
| E1-069 | official | R1 | Once the home is unoccupied, turn on cameras. |
| E1-070 | official | R1 | When someone rings the doorbell, blink the lights in occupied room. |
| E1-072 | official | R1, R9 | After dark, when someone arrives home, turn on lights, and turn off all lights when the home is unoccupied. |
| E1-073 | official | R1 | When a package is delivered, send a notification. |
| E1-074 | official | R1, R2, R9 | Open blinds in the morning after motion is detected; suppress the trigger for 20 hours. |
| E1-075 | official | R1, R9 | Send a notification when movement is detected at home on a weekday between 09:00 and 18:00. |
| E1-076 | official | R1 | Send a notification to a device when a person leaves a specific zone. |
| E1-077 | official | R1 | Turn on exterior lighting when the sun elevation falls below -4.0 degrees. |
| E1-078 | community | R1 | Turn light ON when motion detected, turn off in 5 min; turn light ON when Lux drops below X lux, turn off in 5 min; should not turn ON light when light OFF by HA. |
| E1-079 | community | R1, R5, R7 | If there are no new sensor values, trigger the automation once every minute; normal sensor values arrive every 10 seconds. |
| E1-080 | community | R1 | Arm an alarm to away when all people are away. |
| E1-081 | community | R3, R7, R8 | Keep nagging me every 5 minutes, up to 3 times, as long as the presence binary sensor remains TRUE. |
| E1-082 | community | R1, R3 | Get a notification if a door that was open for more than 5 minutes was closed. |
| E1-084 | community | R9 | Turn lights on from 6 pm to 9 pm Sunday to Thursday and from 7 pm to 11 pm Friday and Saturday. |
| E1-085 | community | R1, R5 | When temperature drops below 19°C, turn heater on; when temperature raises above 19.5°C, turn heater off. |
| E1-087 | community | R1, R3, R6, B1 | Pressing a button turns on a light for exactly ten minutes, then turns it off; pressing again within the window restarts the ten-minute timer. |
| E1-088 | community | R1, R9 | Between sunset minus two hours and sunset, turn den lights on if the weather becomes very overcast or rainy. |
| E1-089 | community | R2, R9, B1 | Turn on a light just before sunset and turn it off just before sunrise; also handle missed events after Home Assistant restart. |
| E1-090 | community | R2, R6 | Given some trigger and conditions, turn something on for a set time and then off half an hour later. |
| E1-093 | community | R1, R2, B2 | When the doorbell triggers, run three scripts that display the door camera on a phone, tablet, and PC; delays in one script should not postpone the others. |
| E1-094 | community | R2, R6, B2 | In parallel, control multiple lights while preserving each light’s own fade, delay, and turn-off sequence. |
| E1-096 | community | R5 | At a chosen time and day, identify selected battery sensors below a warning threshold or unavailable/unknown and notify selected devices. |
| E1-097 | community | R1, R6, B2 | On a doorbell button, play sound, flash lights, and send notifications, with presence or zone conditions; run enabled actions at the same time. |
| E1-098 | community | R1, R2, R3, R4, R5 | Detect that the washing machine started when power rises above a running threshold; after power stays below a finish threshold for a configured time, notify and reset for the next cycle. |
| E1-100 | community | R1 | When the final resident leaves so occupancy becomes zero, if the door is unlocked, send a notification. |
