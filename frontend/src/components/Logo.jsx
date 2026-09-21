import { LOGO } from "../theme/brand";

/* Header logo: the exact client-supplied file, unmodified. The file has built-in padding,
   so it is cropped with CSS (overflow) to its artwork bounds (x 9–131, y 29–130 of 170×157). */
const CROP = { x: 9, y: 29, w: 122, h: 101, natW: 170 };
export function ProvidedLogo({ height = 64 }) {
  const k = height / CROP.h;
  return (
    <span className="block overflow-hidden" style={{ width: CROP.w * k, height }}>
      <img
        src={LOGO.provided} alt="yuri.woori — Luxury Elixirs, Straight from Korea" draggable={false}
        style={{ width: CROP.natW * k, maxWidth: "none", marginLeft: -CROP.x * k, marginTop: -CROP.y * k }}
      />
    </span>
  );
}

/* Official YuriWoori artwork only — scaled proportionally (Brand Book §2.8). */
export function Wordmark({ className = "h-9" }) {
  return <img src={LOGO.wordmarkGreen} alt="yuri.woori" className={`${className} w-auto`} draggable={false} />;
}

export function HeartMark({ reversed = false, className = "h-8" }) {
  return <img src={reversed ? LOGO.heartWhite : LOGO.heartGreen} alt="" className={`${className} w-auto`} draggable={false} />;
}

export function FullLockup({ reversed = false, className = "h-40" }) {
  return (
    <img
      src={reversed ? LOGO.lockupWhite : LOGO.lockupGreen}
      alt="yuri.woori — Luxury Elixirs, Straight from Korea"
      className={`${className} w-auto`}
      draggable={false}
    />
  );
}
