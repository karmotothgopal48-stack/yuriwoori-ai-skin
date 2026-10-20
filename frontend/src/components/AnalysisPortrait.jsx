/* Campaign portrait with the shared, deliberately quiet skin-analysis overlay used on every
   AI Skin Analysis screen: a few glowing points, faint dotted contour lines and small labels.
   Labels only name what the analysis measures; no scores are shown. `portrait` comes from
   PORTRAITS in theme/brand.js (image + point/label positions for that crop). */
export function AnalysisPortrait({ portrait, className = "", rounded = "rounded-[1.5rem] sm:rounded-[2rem]", children, priority = false }) {
  const [a, b, c, d] = portrait.points;
  return (
    <div className={`relative aspect-[4/5] overflow-hidden bg-mist shadow-float ${rounded} ${className}`}>
      <img
        src={portrait.src} alt={portrait.alt} width={portrait.width} height={portrait.height}
        className="h-full w-full object-cover" fetchpriority={priority ? "high" : undefined} draggable={false}
      />
      <div aria-hidden="true" className="pointer-events-none absolute inset-0">
        <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none">
          <polyline points={`${a.x},${a.y} ${b.x},${b.y} ${d.x},${d.y}`} fill="none" stroke="white" strokeOpacity="0.55" strokeWidth="1" vectorEffect="non-scaling-stroke" strokeDasharray="2 4" />
          <line x1={a.x} y1={a.y} x2={c.x} y2={c.y} stroke="white" strokeOpacity="0.4" strokeWidth="1" vectorEffect="non-scaling-stroke" strokeDasharray="2 4" />
        </svg>
        {portrait.points.map((p, i) => (
          <span key={i} className="absolute -translate-x-1/2 -translate-y-1/2" style={{ left: `${p.x}%`, top: `${p.y}%` }}>
            <span className="absolute inset-0 -m-1.5 rounded-full bg-white/40 motion-safe:animate-ping [animation-duration:2.8s]" style={{ animationDelay: `${i * 0.5}s` }} />
            <span className="relative block h-2 w-2 rounded-full bg-white ring-2 ring-white/40 shadow-[0_0_10px_rgba(255,255,255,0.9)]" />
          </span>
        ))}
        {portrait.labels.map((l) => (
          <span key={l.text} style={l.pos}
            className="absolute hidden sm:inline rounded-full bg-white/85 backdrop-blur px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-jade shadow-soft">
            {l.text}
          </span>
        ))}
      </div>
      {children}
    </div>
  );
}
