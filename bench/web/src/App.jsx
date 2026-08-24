import { useEffect, useMemo, useState } from 'react';
import Floorplan from './Floorplan.jsx';
import { callEffects, readable, tintOf } from './effects.js';

const SPACE = 'HOME06';                 // 지금은 한 공간만. 나중에 페이지로 나눈다.
const VERDICT = { execute: '실행', ask: '되묻기', refuse: '거절' };
const WHY = {
  no_device: '그런 기기가 없다', no_service: '그 일을 할 서비스가 없다',
  no_channel: '답할 길이 없다', no_context: '알 수 없는 바깥 사정',
};

function useJson(url) {
  const [v, set] = useState(null);
  useEffect(() => { fetch(url).then((r) => r.json()).then(set); }, [url]);
  return v;
}

export default function App() {
  const [theme, setTheme] = useState(
    () => localStorage.getItem('joi-theme') || 'light');
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('joi-theme', theme);
  }, [theme]);

  const space = useJson(`/data/space.${SPACE}.json`);
  const cmds = useJson(`/data/cmds.${SPACE}.json`);
  const EF = useJson('/data/effects.json');

  const [sel, setSel] = useState(null);      // 고른 명령
  const [q, setQ] = useState('');
  const [filt, setFilt] = useState('all');
  const [hoverDev, setHoverDev] = useState(null);
  const [flash, setFlash] = useState(null);  // IR 한 줄에 마우스 → 그 기기들

  const byId = useMemo(() => {
    const m = new Map();
    space?.devices.forEach((d) => m.set(d.id, d));
    return m;
  }, [space]);

  const list = useMemo(() => {
    if (!cmds) return [];
    const s = q.trim().toLowerCase();
    return cmds.filter((c) =>
      (filt === 'all' || c.expect === filt) &&
      (!s || c.text.toLowerCase().includes(s)));
  }, [cmds, q, filt]);

  // 고른 명령의 정답 기기
  const hits = useMemo(
    () => new Set(sel?.targets?.filter((t) => byId.has(t)) || []), [sel, byId]);

  // 시스템 기기가 답하는 명령인가 (알림·조회)
  const sysOn = useMemo(() => {
    const s = new Set();
    if (!sel?.ir) return s;
    for (const st of sel.ir.timeline || []) {
      if (st.op !== 'call' || !st.target) continue;
      const cat = st.target.split('.')[0];
      space?.system.forEach((y) => { if (y.cat === cat) s.add(y.id); });
    }
    return s;
  }, [sel, space]);

  // call 한 줄 → 그 카테고리를 가진 정답 기기들
  const devsOfTarget = (target) => {
    const cat = target?.split('.')[0];
    return [...hits].filter((id) => byId.get(id)?.cats.includes(cat));
  };

  // 방 물들이기 + 소리 파동
  const { tints, pings } = useMemo(() => {
    const t = {}, p = new Set();
    if (!sel?.ir || !EF) return { tints: t, pings: p };
    for (const st of sel.ir.timeline || []) {
      if (st.op !== 'call' || !st.target) continue;
      for (const id of devsOfTarget(st.target)) {
        const d = byId.get(id);
        const codes = callEffects(EF, st.target, st.args, d.cats);
        const tint = tintOf(codes);
        if (tint) t[d.room] = tint;
        if (codes.some((c) => c.startsWith('sound') || c.startsWith('audio_signal')))
          p.add(id);
      }
    }
    return { tints: t, pings: p };
  }, [sel, EF, hits, byId]);

  // 효과 딱지 (겹치는 것은 하나로)
  const efxList = useMemo(() => {
    if (!sel?.ir || !EF) return [];
    const seen = new Map();
    for (const st of sel.ir.timeline || []) {
      if (st.op !== 'call' || !st.target) continue;
      const cats = devsOfTarget(st.target).map((id) => byId.get(id).cats).flat();
      for (const c of callEffects(EF, st.target, st.args, cats))
        if (!seen.has(c)) seen.set(c, readable(EF, c));
    }
    return [...seen.values()];
  }, [sel, EF, hits, byId]);

  if (!space || !cmds) return <div className="empty">불러오는 중…</div>;

  return (
    <div className="app">
      <header className="hd">
        <span className="brand">JoI 벤치마크</span>
        <span className="sep" />
        <span className="space-name">{space.name}</span>
        <span className="space-meta">
          {space.id} · 방 {space.rooms.length} · 기기 {space.devices.length} ·
          명령 {cmds.length}
        </span>
        <span className="grow" />
        <button className="iconbtn"
                onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}>
          {theme === 'light' ? '🌙' : '☀️'}
          {theme === 'light' ? '어둡게' : '밝게'}
        </button>
      </header>

      <div className="body">
        <main className="stage">
          <div className="plan-wrap">
            <Floorplan
              space={space} hits={hits} missed={null} wrong={null}
              muted={!!sel} tints={tints} pings={pings}
              flash={flash} onHover={setHoverDev} onPick={() => {}} />
          </div>
          <div className="systray">
            <span className="cap">집 전체</span>
            {space.system.map((s) => (
              <span key={s.id} className={'chip' + (sysOn.has(s.id) ? ' on' : '')}>
                <span className="g">{s.icon}</span>{s.ko}
              </span>
            ))}
            <span className="grow" style={{ flex: 1 }} />
            <span className="cap">
              {hoverDev ? `${hoverDev.ko} · ${hoverDev.id}`
                        : sel ? `골라진 기기 ${hits.size}개` : ''}
            </span>
          </div>
        </main>

        <aside className="side">
          {!sel ? (
            <>
              <div className="search">
                <input placeholder="명령어 찾기…" value={q}
                       onChange={(e) => setQ(e.target.value)} />
                <div className="filters">
                  {['all', 'execute', 'ask', 'refuse'].map((f) => (
                    <button key={f} className={'fbtn' + (filt === f ? ' on' : '')}
                            onClick={() => setFilt(f)}>
                      {f === 'all' ? `전체 ${cmds.length}` : VERDICT[f]}
                    </button>
                  ))}
                </div>
              </div>
              <div className="cmdlist">
                {list.map((c) => (
                  <div key={c.id} className="cmd" onClick={() => setSel(c)}>
                    <div className="t">{c.text}</div>
                    <div className="m">
                      <span className={'tag ' + c.expect}>{VERDICT[c.expect]}</span>
                      <span className="tag">{c.tier}</span>
                      <span>{c.targets.length ? `기기 ${c.targets.length}` : '기기 없음'}</span>
                      <span style={{ marginLeft: 'auto' }}>{c.id}</span>
                    </div>
                  </div>
                ))}
                {!list.length && <div className="empty">찾은 명령이 없습니다.</div>}
              </div>
            </>
          ) : (
            <div className="detail">
              <button className="iconbtn" style={{ marginBottom: 14 }}
                      onClick={() => { setSel(null); setFlash(null); }}>
                ← 목록으로
              </button>

              <section>
                <h4>명령</h4>
                <div className="quote">{sel.text}</div>
                <div className="kv" style={{ marginTop: 9 }}>
                  <span className={'tag ' + sel.expect}>{VERDICT[sel.expect]}</span>
                  <span className="tag">{sel.tier}</span>
                  <span className="tag">{sel.d}</span>
                  <span className="tag">{sel.id}</span>
                  {sel.why && <span className="tag refuse">{WHY[sel.why] || sel.why}</span>}
                </div>
              </section>

              {sel.ir && (
                <section>
                  <h4>정답 코드 (Timeline IR)</h4>
                  <div className="ir">
                    {sel.ir.timeline.map((st, i) => {
                      const on = st.op === 'call' && st.target;
                      return (
                        <div key={i} className={'step' + (on ? ' callable' : '')}
                             onMouseEnter={() => on &&
                               setFlash(new Set(devsOfTarget(st.target)))}
                             onMouseLeave={() => setFlash(null)}>
                          <span className="n">{i + 1}</span>
                          <span className="op">{st.op}</span>
                          <span className="arg">
                            {st.target || st.cond || st.anchor || st.dur || ''}
                            {st.args && Object.keys(st.args).length
                              ? ' ' + JSON.stringify(st.args) : ''}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </section>
              )}

              {!!efxList.length && (
                <section>
                  <h4>실제로 무엇이 바뀌나</h4>
                  <div className="efx">
                    {efxList.map((e) => (
                      <span key={e.code} className="e" title={e.full}>
                        <b>{e.ko}</b> {e.dir}
                      </span>
                    ))}
                  </div>
                </section>
              )}

              <section>
                <h4>골라야 하는 기기 {hits.size}개</h4>
                {hits.size ? (
                  <div className="tlist">
                    {[...hits].map((id) => {
                      const d = byId.get(id);
                      return (
                        <div key={id} className="trow"
                             onMouseEnter={() => setFlash(new Set([id]))}
                             onMouseLeave={() => setFlash(null)}>
                          <span className="g">{d.icon}</span>
                          <span>{d.ko} {d.label.split('_').pop()}</span>
                          <span className="rm">
                            {space.rooms.find((r) => r.id === d.room)?.ko}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div style={{ color: 'var(--faint)', fontSize: 12.5 }}>
                    지목할 기기가 없다 — 알림·조회처럼 시스템이 답하거나, 거절이다.
                  </div>
                )}
              </section>

              <section>
                <h4>표시 규칙</h4>
                <div className="legend">
                  {[['hit', '모델이 골랐고 정답'], ['wrong', '모델이 골랐는데 오답'],
                    ['missed', '정답인데 놓침'], ['mute', '이 명령과 무관']].map(
                    ([k, label]) => (
                      <div key={k} className="lg">
                        <svg width="30" height="30" style={{ flex: '0 0 30px' }}>
                          <g className={'dev ' + k}>
                            <circle className="disc" cx="15" cy="15" r="10" />
                            <text className="glyph" x="15" y="15.5">💡</text>
                          </g>
                        </svg>
                        {label}
                      </div>
                    ))}
                </div>
                <div style={{ color: 'var(--faint)', fontSize: 11.5, marginTop: 8,
                              lineHeight: 1.6 }}>
                  지금은 모델을 안 붙였으므로 <b>정답</b>만 파랑으로 보입니다.
                  모델 결과를 붙이면 오답·놓침이 함께 칠해집니다.
                </div>
              </section>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
