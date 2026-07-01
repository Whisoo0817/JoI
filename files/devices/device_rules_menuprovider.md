[Device Summary]
<Device "MenuProvider">
  <Service "Menu" type="value">General menu information</Service>
  <Service "TodayMenu" type="value">Entire menu for today (no filtering)</Service>
  <Service "TodayPlace" type="value">Today's dining location</Service>
  <Service "GetMenu" type="action">Get menu filtered by date / location / meal</Service>
</Device>

# Selection Rule
If the command names a specific dining location (e.g. `301동`, `학생식당`, building/cafeteria name) **OR** a meal-time (`아침`/`점심`/`저녁`) **OR** a non-today date (`내일`) → pick `MenuProvider.GetMenu`. Otherwise (bare "today's menu") → `MenuProvider.TodayMenu`.

# GetMenu Argument (Korean string — exception)
`GetMenu(Command: STRING)` — Korean structured string, format:
```
[오늘|내일] [학생식당|수의대식당|전망대(3식당)|예술계식당(아름드리)|기숙사식당|아워홈|동원관식당(113동)|웰스토리(220동)|투굿(공대간이식당)|자하연식당|301동식당] [아침|점심|저녁]
```
- Use exact Korean tokens. No English. No paraphrase.
- Defaults if a slot is implicit: date→`오늘`, meal→`점심`, location→`학생식당`.
- Building numbers map to closest token: `301동`→`301동식당`, `113동`→`동원관식당(113동)`, `220동`→`웰스토리(220동)`.

- e.g. bare "오늘 메뉴" → `TodayMenu`; "내일 점심 메뉴" → `GetMenu` (Command="내일 학생식당 점심"); "301동 오늘 점심" → `GetMenu` (Command="오늘 301동식당 점심").
