/* Small abstract "skin swatch" medallions, one per measurement, drawn in SVG with the brand palette
   (theme/brand.js) — no photos or external images. Each is a soft skin-toned disc with a quiet motif:
   hydration droplets, texture ripples, an oil-shine highlight, a blush, a two-tone complexion, a pore
   dot field, and a clear disc with three faint spots. Decorative: the measurement name sits beside it. */
import { BRAND } from "../theme/brand";

const SKIN = "#F6EDE6";      // warm skin tone base
const SKIN_EDGE = "#EADBD0";
const BLUSH = "#E7C3B6";
const ROSE = "#C99A8C";

function Disc({ id, children }) {
  return (
    <>
      <defs>
        <radialGradient id={`${id}-skin`} cx="38%" cy="32%" r="75%">
          <stop offset="0" stopColor="#FFFFFF" />
          <stop offset="0.55" stopColor={SKIN} />
          <stop offset="1" stopColor={SKIN_EDGE} />
        </radialGradient>
        <clipPath id={`${id}-clip`}><circle cx="24" cy="24" r="19" /></clipPath>
      </defs>
      <circle cx="24" cy="24" r="23" fill="none" stroke={BRAND.jadeLine} strokeWidth="0.75" />
      <circle cx="24" cy="24" r="19" fill={`url(#${id}-skin)`} />
      <g clipPath={`url(#${id}-clip)`}>{children}</g>
    </>
  );
}

const MOTIFS = {
  hydration: (id) => (
    <Disc id={id}>
      <path d="M24 12c4.5 5.6 7 9.6 7 13a7 7 0 0 1-14 0c0-3.4 2.5-7.4 7-13Z" fill={BRAND.softJade} fillOpacity="0.55" stroke={BRAND.deepJade} strokeOpacity="0.55" strokeWidth="0.9" />
      <path d="M21 25.5a3.4 3.4 0 0 0 2.6 3.4" fill="none" stroke="#FFFFFF" strokeWidth="1.2" strokeLinecap="round" />
      <circle cx="33.5" cy="17" r="1.6" fill={BRAND.softJade} fillOpacity="0.6" />
      <circle cx="15" cy="31" r="1.1" fill={BRAND.softJade} fillOpacity="0.55" />
    </Disc>
  ),
  texture: (id) => (
    <Disc id={id}>
      {[15, 20, 25, 30, 35].map((y, i) => (
        <path key={y} d={`M4 ${y} q5 ${i % 2 ? -2 : 2} 10 0 t10 0 t10 0 t10 0 t10 0`} fill="none" stroke={BRAND.sage} strokeOpacity={0.45 - i * 0.04} strokeWidth="0.8" />
      ))}
    </Disc>
  ),
  oiliness: (id) => (
    <Disc id={id}>
      <defs>
        <radialGradient id={`${id}-shine`} cx="50%" cy="50%" r="50%">
          <stop offset="0" stopColor="#FFFFFF" stopOpacity="0.95" />
          <stop offset="1" stopColor="#FFFFFF" stopOpacity="0" />
        </radialGradient>
      </defs>
      <ellipse cx="20" cy="19" rx="9" ry="6" fill={`url(#${id}-shine)`} transform="rotate(-25 20 19)" />
      <path d="M31 27l1 2.6 2.6 1-2.6 1-1 2.6-1-2.6-2.6-1 2.6-1Z" fill={BRAND.sage} fillOpacity="0.55" />
      <circle cx="17" cy="31" r="0.9" fill={BRAND.sage} fillOpacity="0.45" />
    </Disc>
  ),
  redness: (id) => (
    <Disc id={id}>
      <defs>
        <radialGradient id={`${id}-blush`} cx="50%" cy="50%" r="50%">
          <stop offset="0" stopColor={BLUSH} stopOpacity="0.95" />
          <stop offset="1" stopColor={BLUSH} stopOpacity="0" />
        </radialGradient>
      </defs>
      <circle cx="18" cy="27" r="10" fill={`url(#${id}-blush)`} />
      <circle cx="31" cy="20" r="7" fill={`url(#${id}-blush)`} opacity="0.7" />
    </Disc>
  ),
  pigmentation: (id) => (
    <Disc id={id}>
      <defs>
        <linearGradient id={`${id}-tone`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#FFFFFF" stopOpacity="0.6" />
          <stop offset="1" stopColor="#D9C2B2" stopOpacity="0.9" />
        </linearGradient>
      </defs>
      <path d="M5 5h38v38z" fill={`url(#${id}-tone)`} />
      <path d="M5 43 43 5" stroke="#FFFFFF" strokeOpacity="0.8" strokeWidth="0.8" />
      <circle cx="30" cy="30" r="3" fill="#CFB4A2" fillOpacity="0.55" />
    </Disc>
  ),
  pores: (id) => (
    <Disc id={id}>
      {Array.from({ length: 6 }, (_, r) => Array.from({ length: 6 }, (_, c) => (
        <circle key={`${r}-${c}`} cx={9 + c * 6 + (r % 2) * 3} cy={9 + r * 6} r={0.7 + ((r + c) % 3) * 0.15} fill={BRAND.sage} fillOpacity="0.38" />
      )))}
    </Disc>
  ),
  acne: (id) => (
    <Disc id={id}>
      <circle cx="24" cy="24" r="12" fill="#FFFFFF" fillOpacity="0.35" />
      <circle cx="18.5" cy="20" r="1.5" fill={ROSE} fillOpacity="0.55" />
      <circle cx="29" cy="27.5" r="1.2" fill={ROSE} fillOpacity="0.45" />
      <circle cx="22" cy="31" r="0.9" fill={ROSE} fillOpacity="0.4" />
    </Disc>
  ),
};

/** Medallion for a measurement id (hydration, texture, oiliness, redness, pigmentation, pores, acne). */
export function SkinVisual({ metric, className = "" }) {
  const motif = MOTIFS[metric];
  if (!motif) return null;
  return (
    <svg viewBox="0 0 48 48" className={className} aria-hidden="true" focusable="false">
      {motif(`skin-${metric}`)}
    </svg>
  );
}
