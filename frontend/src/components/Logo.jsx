import { LOGO } from "../theme/brand";

const ALT = "yuri.woori — Luxury Elixirs, Straight from Korea";
const pct = (n) => `${(n * 100).toFixed(3)}%`;

/* Shows an unmodified logo file cropped with CSS (overflow) to its artwork bounds, scaled proportionally.
   Pass `width` (any CSS length, e.g. a clamp()) to scale fluidly — the crop is then expressed in percentages
   of the box width (percentage margins resolve against width too) — or a pixel `height`. */
function CroppedLogo({ src, crop, width, height }) {
  if (width) {
    return (
      <span className="block overflow-hidden" style={{ width, aspectRatio: `${crop.w} / ${crop.h}` }}>
        <img src={src} alt={ALT} draggable={false}
          style={{ width: pct(crop.natW / crop.w), maxWidth: "none", marginLeft: `-${pct(crop.x / crop.w)}`, marginTop: `-${pct(crop.y / crop.w)}` }} />
      </span>
    );
  }
  const k = height / crop.h;
  return (
    <span className="block overflow-hidden" style={{ width: crop.w * k, height }}>
      <img src={src} alt={ALT} draggable={false}
        style={{ width: crop.natW * k, maxWidth: "none", marginLeft: -crop.x * k, marginTop: -crop.y * k }} />
    </span>
  );
}

/* The client-supplied file (170×157, opaque white background: use on white only); artwork x 9–131, y 29–130. */
export function ProvidedLogo({ height = 64, width }) {
  return <CroppedLogo src={LOGO.provided} crop={{ x: 9, y: 29, w: 122, h: 101, natW: 170 }} width={width} height={height} />;
}

/* The official website logo (yuriwoori.com/cdn/shop/files/GREEN_LOGO.png, byte-identical to
   public/assets/yuriwoori-logo-green.png): 812×812, transparent; artwork x 26–800, y 32–670. */
export const OFFICIAL_LOGO_RATIO = 774 / 638;
export function OfficialLogo({ height = 64, width }) {
  return <CroppedLogo src={LOGO.lockupGreen} crop={{ x: 26, y: 32, w: 774, h: 638, natW: 812 }} width={width} height={height} />;
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
      alt={ALT}
      className={`${className} w-auto`}
      draggable={false}
    />
  );
}
