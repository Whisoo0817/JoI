/* 평면도 — 방은 네모, 기기는 동그라미. 위에서 곧게 내려다본 그림이라
   벽에 가려 안 보이는 기기가 없다. */

const TINT_VAR = { warm: 'var(--warm)', cool: 'var(--cool)',
                   hot: 'var(--hot)', dim: 'var(--dim)' };

export default function Floorplan({ space, hits, missed, wrong, muted,
                                    tints, pings, flash, onHover, onPick }) {
  const { w, h } = space.canvas;
  const pad = 18;

  const cls = (d) => {
    const c = ['dev'];
    if (hits.has(d.id)) c.push('hit');
    else if (wrong?.has(d.id)) c.push('wrong');
    else if (missed?.has(d.id)) c.push('missed');
    else if (muted) c.push('mute');
    if (flash === d.id || flash?.has?.(d.id)) c.push('flash');
    return c.join(' ');
  };

  return (
    <svg viewBox={`${-pad} ${-pad} ${w + pad * 2} ${h + pad * 2}`}
         preserveAspectRatio="xMidYMid meet">
      {/* 방 */}
      {space.rooms.map((r) => (
        <g key={r.id}>
          <rect className={'room-rect' + (r.outdoor ? ' outdoor' : '')}
                x={r.x} y={r.y} width={r.w} height={r.h} rx="7" />
          {tints[r.id] && (
            <rect className="room-tint" x={r.x} y={r.y} width={r.w} height={r.h}
                  rx="7" fill={TINT_VAR[tints[r.id]]} />
          )}
          <text className="room-label" x={r.x + 11} y={r.y + 17}>
            {r.ko}
            <tspan className="room-count" dx="6">{r.n}</tspan>
          </text>
        </g>
      ))}

      {/* 기기 */}
      {space.devices.map((d) => (
        <g key={d.id} className={cls(d)}
           onMouseEnter={() => onHover?.(d)}
           onMouseLeave={() => onHover?.(null)}
           onClick={() => onPick?.(d)}>
          {pings.has(d.id) && (
            <circle className="ping" cx={d.x} cy={d.y} r={d.r}
                    fill="none" stroke="var(--blue)" strokeWidth="1.5"
                    style={{ '--r0': `${d.r}px` }} />
          )}
          {hits.has(d.id) && (
            <circle className="halo" cx={d.x} cy={d.y} r={d.r + 3.5} />
          )}
          <circle className="disc" cx={d.x} cy={d.y} r={d.r} />
          <text className="glyph" x={d.x} y={d.y + 0.5}
                style={{ fontSize: Math.max(11, d.r * 0.85) }}>{d.icon}</text>
          <title>{`${d.ko} · ${d.label}\n${d.id}`}</title>
        </g>
      ))}
    </svg>
  );
}
