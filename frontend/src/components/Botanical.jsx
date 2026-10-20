/* Original fine-line botanical sprigs (a stem with paired leaves and a single droplet) used as quiet
   decoration on the results page. Drawn for YuriWoori in SVG with the brand palette; purely decorative. */
export function BotanicalSprig({ className = "", stroke = "#9DD4CA", opacity = 1 }) {
  return (
    <svg viewBox="0 0 120 220" className={className} aria-hidden="true" focusable="false" style={{ opacity }}>
      <g fill="none" stroke={stroke} strokeWidth="1" strokeLinecap="round" strokeLinejoin="round">
        <path d="M62 216C58 170 60 120 70 64C74 42 80 24 88 8" />
        {[[66, 176, -1], [64, 146, 1], [65, 116, -1], [68, 88, 1], [74, 60, -1], [81, 36, 1]].map(([x, y, side], i) => {
          const len = 30 - i * 3.2;
          const tipX = x + side * len, tipY = y - len * 0.55;
          const c1 = `${x + side * len * 0.2},${y - len * 0.6}`, c2 = `${x + side * len * 0.8},${y - len * 0.1}`;
          return (
            <g key={i}>
              <path d={`M${x} ${y}Q${c1} ${tipX} ${tipY}Q${c2} ${x} ${y}Z`} fill={stroke} fillOpacity="0.12" />
              <path d={`M${x} ${y}L${x + side * len * 0.7} ${y - len * 0.42}`} strokeOpacity="0.6" />
            </g>
          );
        })}
      </g>
      <path d="M96 150c3 4 4.5 6.6 4.5 8.6a4.5 4.5 0 0 1-9 0c0-2 1.5-4.6 4.5-8.6Z" fill={stroke} fillOpacity="0.25" stroke={stroke} strokeWidth="0.8" />
    </svg>
  );
}

/** A soft concentric "ripple" mark — water rings — for section accents. */
export function Ripple({ className = "", stroke = "#BDDCCD" }) {
  return (
    <svg viewBox="0 0 120 120" className={className} aria-hidden="true" focusable="false">
      {[54, 42, 30, 18].map((r, i) => (
        <circle key={r} cx="60" cy="60" r={r} fill="none" stroke={stroke} strokeOpacity={0.35 + i * 0.15} strokeWidth="0.8" strokeDasharray={i % 2 ? "2 5" : undefined} />
      ))}
      <circle cx="60" cy="60" r="4" fill={stroke} fillOpacity="0.6" />
    </svg>
  );
}
