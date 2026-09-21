import { BRAND } from "../theme/brand";

export function ScoreRing({ value, size = 88, stroke = 7, label }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  return (
    <svg width={size} height={size} className="shrink-0" role="img" aria-label={`${label || "Score"} ${value}`}>
      <circle cx={size / 2} cy={size / 2} r={r} stroke={BRAND.mist} strokeWidth={stroke} fill="none" />
      <circle
        cx={size / 2} cy={size / 2} r={r} fill="none" stroke={BRAND.deepJade} strokeWidth={stroke}
        strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c - (value / 100) * c}
        transform={`rotate(-90 ${size / 2} ${size / 2})`} style={{ transition: "stroke-dashoffset .8s ease" }}
      />
      <text x="50%" y="52%" textAnchor="middle" dominantBaseline="middle" fill={BRAND.deepJade}
        style={{ fontFamily: "var(--font-display)", fontSize: size * 0.32 }}>
        {value}
      </text>
    </svg>
  );
}
