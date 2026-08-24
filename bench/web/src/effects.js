/* 서비스 하나를 부르면 세상에서 무엇이 바뀌나.
   effects.json 은 bench/effects.py 를 그대로 옮긴 것이다. 어휘는 35개뿐이라
   화면 쪽은 그 35개에만 그림을 붙이면 된다. */

const SIGN = { '+': '올라감', '-': '내려감', '=': '맞춰짐', '~': '바뀜' };

/** 값이 배열이면 그대로, enum 별로 갈리면 인자에 맞는 것을 고른다. */
function pick(entry, args) {
  if (!entry) return [];
  if (Array.isArray(entry)) return entry;
  const vals = Object.values(args || {}).map((v) => String(v));
  for (const v of vals) if (entry[v]) return entry[v];
  if (entry['*']) return entry['*'];
  return Object.values(entry).flat();
}

/** call 한 줄 → 효과 코드 목록. Switch 면 그 스위치에 달린 기기 효과를 얹는다. */
export function callEffects(EF, target, args, deviceCats = []) {
  if (!EF || !target || !target.includes('.')) return [];
  const [cat, method] = target.split('.');
  const out = [...pick(EF.effects?.[cat]?.[method], args)];
  if (cat === 'Switch') {
    for (const c of deviceCats) {
      const extra = EF.switch_carries?.[c]?.[method];
      if (extra) out.push(...extra);
    }
  }
  return out;
}

/** 효과 코드를 사람 말로. "illuminance+" → {양: "밝기", 방향: "올라감"} */
export function readable(EF, code) {
  const sign = code.slice(-1);
  const key = SIGN[sign] ? code.slice(0, -1) : code;
  return {
    code,
    key,
    ko: EF?.vocab?.[key]?.split(' ')[0] || key,
    full: EF?.vocab?.[key] || key,
    dir: SIGN[sign] || '',
  };
}

/** 방을 어떤 색으로 물들일까. 없으면 안 물들인다. */
const TINT = {
  'illuminance+': 'warm',
  'illuminance-': 'dim',
  'temperature-': 'cool',
  'thermal_comfort-': 'cool',
  'temperature+': 'hot',
  'thermal_comfort+': 'hot',
};

export function tintOf(codes) {
  for (const c of codes) if (TINT[c]) return TINT[c];
  return null;
}
