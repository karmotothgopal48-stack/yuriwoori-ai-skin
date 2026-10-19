/* Shared building blocks for the result pages (Skin profile, Routine) so they read as
   one product: the same type scale, card treatment, status language, bars, score dial and actions.
   Everything here only presents values it is given; nothing is computed from the scan. */
import { useEffect, useRef, useState } from "react";
import { animate, motion, useInView, useReducedMotion } from "framer-motion";
import { Info } from "lucide-react";

// ---- motion (fast and quiet; MotionConfig in App honours prefers-reduced-motion) ----
export const fadeUp = { hidden: { opacity: 0, y: 12 }, show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1] } } };
export const stagger = { hidden: {}, show: { transition: { staggerChildren: 0.06 } } };

// ---- layout + type ----
export const PAGE = "flex-1 w-full max-w-6xl mx-auto px-4 sm:px-8 py-8 sm:py-10";
export const CARD = "rounded-[24px] bg-white/90 border border-hairline shadow-soft";
export const SOFT = "rounded-2xl bg-cream/70 border border-sage-light/60";

export function Kicker({ children, className = "" }) {
  return <p className={`text-[11px] font-semibold uppercase tracking-[0.16em] text-sage ${className}`}>{children}</p>;
}

export function SectionHeading({ kicker, title, sub, center = false, className = "" }) {
  return (
    <div className={`mb-6 ${center ? "text-center" : ""} ${className}`}>
      {kicker && <Kicker>{kicker}</Kicker>}
      {title && <h2 className="mt-1 font-display text-[26px] sm:text-[32px] leading-tight text-jade-deep">{title}</h2>}
      {sub && <p className={`mt-2 max-w-2xl text-sm leading-relaxed text-ink-soft ${center ? "mx-auto" : ""}`}>{sub}</p>}
    </div>
  );
}

/** Page hero: text column + optional visual column. Stacks on mobile (text first). */
export function ResultHero({ eyebrow, title, children, aside, className = "" }) {
  return (
    <motion.section initial="hidden" animate="show" variants={stagger}
      className={`grid grid-cols-1 items-center gap-8 ${aside ? "md:grid-cols-[1.1fr_0.9fr] md:gap-12" : ""} mb-10 sm:mb-12 ${className}`}>
      <motion.div variants={fadeUp} className={aside ? "text-center md:text-left" : "text-center"}>
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-jade">{eyebrow}</p>
        <h1 className="mt-3 font-display text-[34px] leading-[1.06] text-jade-deep sm:text-[46px] lg:text-[52px]">{title}</h1>
        {children && <div className={`mt-4 text-[15px] leading-relaxed text-ink-soft ${aside ? "mx-auto max-w-md md:mx-0" : "mx-auto max-w-2xl"}`}>{children}</div>}
      </motion.div>
      {aside && <motion.div variants={fadeUp}>{aside}</motion.div>}
    </motion.section>
  );
}

// ---- Typical / Benchmark vs Your Result ----
// The benchmark is a fixed internal YuriWoori value per metric, sent by the backend with every analysis;
// it is for comparison only and is never a medical or population norm. Higher/lower is stated neutrally:
// whether higher is better depends on the metric ("Higher is better" / "Higher means more of this trait").
export const BENCHMARK_NOTE = "Typical values are YuriWoori internal skincare-analysis benchmarks for comparison only. They are not medical or population norms.";
export const NO_BENCHMARK_NOTE = "No typical benchmark is configured for hand scans yet, so only your result is shown.";

// ---- Typical / Benchmark vs Your Result: shared comparison pieces ----
const EASE = [0.22, 1, 0.36, 1];

/** Difference between your result and the typical benchmark, stated neutrally (+7 / −30 / Same):
    whether higher is better depends on the measurement, so no good/bad colour is used. */
export function BenchmarkDelta({ c, delay = 0, className = "" }) {
  if (c.typicalBenchmark == null) return null;
  const diff = c.yourResult - c.typicalBenchmark;
  const text = diff === 0 ? "Same" : `${diff > 0 ? "+" : "\u2212"}${Math.abs(diff)}`;
  const spoken = diff === 0 ? "same as typical" : `${Math.abs(diff)} ${diff > 0 ? "above" : "below"} typical`;
  return (
    <motion.span initial={{ opacity: 0, y: 3 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.35, delay, ease: EASE }}
      className={`inline-flex items-center rounded-full border border-jade-line bg-white px-2 py-0.5 text-[11px] font-semibold leading-4 tracking-wide text-jade-deep tabular-nums shadow-[0_1px_2px_rgba(0,70,71,0.06)] ${className}`}
      title={`Your result is ${spoken}`}>
      <span aria-hidden="true">{text}</span><span className="sr-only">Difference: {spoken}</span>
    </motion.span>
  );
}

/** A 0–100 track: the typical benchmark is a slim sage marker (with a short cap), your result is the
    main line ending in a ringed dot, and a faint band spans the gap between them. Shape, not only colour,
    tells the two apart (line marker vs dot), and the legend names them. */
export function ComparisonTrack({ c }) {
  const value = Math.max(0, Math.min(100, c.yourResult));
  const typical = c.typicalBenchmark;
  const gapFrom = typical == null ? null : Math.min(typical, value), gapTo = typical == null ? null : Math.max(typical, value);
  return (
    <div className="relative pt-1" role="img"
      aria-label={`${c.label}: your result ${c.yourResult} out of 100${typical != null ? `, typical ${typical} out of 100` : ", no typical benchmark"}`}>
      <div className="relative h-5">
        <div className="absolute inset-x-0 top-1/2 h-[6px] -translate-y-1/2 rounded-full bg-[linear-gradient(90deg,#EEF3EE,#E3ECEB)]" />
        {typical != null && (
          <motion.div aria-hidden="true" className="absolute top-1/2 h-[6px] -translate-y-1/2 rounded-full bg-[#9DD4CA]/35"
            style={{ left: `${gapFrom}%`, width: `${gapTo - gapFrom}%` }}
            initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }} transition={{ duration: 0.5, delay: 0.9 }} />
        )}
        <motion.div aria-hidden="true" className="absolute left-0 top-1/2 h-[6px] -translate-y-1/2 rounded-full bg-[linear-gradient(90deg,#BDDCCD,#528778_60%,#006968)]"
          initial={{ width: 0 }} whileInView={{ width: `${value}%` }} viewport={{ once: true }} transition={{ duration: 0.9, delay: 0.35, ease: EASE }} />
        {typical != null && (
          <motion.span aria-hidden="true" className="absolute top-0 flex h-5 -translate-x-1/2 flex-col items-center" style={{ left: `${typical}%` }}
            initial={{ opacity: 0, scaleY: 0.4 }} whileInView={{ opacity: 1, scaleY: 1 }} viewport={{ once: true }} transition={{ duration: 0.35, delay: 0.15, ease: EASE }}>
            <span className="h-[3px] w-[7px] rounded-full bg-sage" />
            <span className="w-[2px] flex-1 rounded-full bg-sage/85" />
          </motion.span>
        )}
        <motion.span aria-hidden="true" className="absolute top-1/2 h-[14px] w-[14px] -translate-x-1/2 -translate-y-1/2 rounded-full border-[3px] border-white bg-jade shadow-[0_0_0_1px_rgba(0,92,93,0.25),0_2px_6px_rgba(0,70,71,0.25)]"
          initial={{ left: "0%", opacity: 0 }} whileInView={{ left: `${value}%`, opacity: 1 }} viewport={{ once: true }} transition={{ duration: 0.9, delay: 0.35, ease: EASE }} />
      </div>
      <div className="mt-1 flex justify-between text-[9px] font-medium uppercase tracking-[0.14em] text-ink-soft/50" aria-hidden="true">
        <span>0</span><span>100</span>
      </div>
    </div>
  );
}

/** Key for the track: the line marker is the typical benchmark, the ringed dot is your result. */
export function ComparisonLegend() {
  return (
    <p className="flex shrink-0 items-center gap-5 whitespace-nowrap text-[11px] text-ink-soft" aria-hidden="true">
      <span className="flex items-center gap-1.5">
        <span className="flex h-3.5 flex-col items-center"><span className="h-[3px] w-[7px] rounded-full bg-sage" /><span className="w-[2px] flex-1 rounded-full bg-sage/85" /></span>
        Typical
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-3 w-3 rounded-full border-[3px] border-white bg-jade shadow-[0_0_0_1px_rgba(0,92,93,0.25)]" />
        Your result
      </span>
    </p>
  );
}

/** A number that counts up from 0 once it scrolls into view (instant with reduced motion). */
export function CountUp({ value, duration = 1.4, className = "" }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true });
  const reduce = useReducedMotion();
  const [shown, setShown] = useState(reduce ? value : 0);
  useEffect(() => {
    if (!inView) return;
    if (reduce) { setShown(value); return; }
    const a = animate(0, value, { duration, ease: [0.22, 1, 0.36, 1], onUpdate: (v) => setShown(Math.round(v)) });
    return () => a.stop();
  }, [inView, value, reduce, duration]);
  return <span ref={ref} className={className}>{shown}</span>;
}

// ---- actions ----
const BTN = "inline-flex min-h-[48px] w-full sm:w-auto items-center justify-center gap-2 rounded-pill px-7 text-sm font-semibold tracking-wide transition-colors duration-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-jade";
export const BTN_PRIMARY = `${BTN} bg-jade text-cream hover:bg-jade-deep`;
export const BTN_SECONDARY = `${BTN} border border-jade text-jade hover:bg-mist`;
export const BTN_QUIET = "inline-flex min-h-[44px] items-center justify-center gap-1.5 rounded-sm px-3 text-sm font-medium text-ink-soft transition-colors hover:text-jade focus-visible:outline-2 focus-visible:outline-jade";

/** Bottom navigation for result pages: quiet back link on the left, secondary + primary on the right. */
export function ResultNav({ back, secondary = [], primary }) {
  return (
    <nav aria-label="Result navigation" className="mt-4 flex flex-col-reverse items-stretch gap-4 border-t border-sage-light/70 pt-7 sm:flex-row sm:items-center sm:justify-between">
      {back ? <button type="button" onClick={back.onClick} className={BTN_SECONDARY}>{back.icon && <back.icon size={16} aria-hidden="true" />}{back.label}</button> : <span />}
      <div className="flex flex-col gap-3 sm:flex-row">
        {secondary.map((s) => (
          <button key={s.label} type="button" onClick={s.onClick} className={BTN_SECONDARY}>{s.icon && <s.icon size={16} aria-hidden="true" />}{s.label}</button>
        ))}
        {primary && <button type="button" onClick={primary.onClick} className={BTN_PRIMARY}>{primary.label}{primary.icon && <primary.icon size={16} aria-hidden="true" />}</button>}
      </div>
    </nav>
  );
}

export function Disclaimer({ className = "" }) {
  return (
    <p className={`flex items-start justify-center gap-2 text-center text-xs leading-relaxed text-ink-soft/80 ${className}`}>
      <Info size={14} className="mt-0.5 shrink-0 text-sage" aria-hidden="true" />
      <span>This analysis is for skincare guidance and is not a medical diagnosis. It does not detect skin conditions or diseases.</span>
    </p>
  );
}

