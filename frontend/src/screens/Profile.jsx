import { ArrowRight, Check, ChevronDown, Leaf } from "lucide-react";
import { motion } from "framer-motion";
import {
  BENCHMARK_NOTE, BenchmarkDelta, ComparisonLegend, ComparisonTrack, CountUp, Disclaimer, Kicker, NO_BENCHMARK_NOTE,
  fadeUp, stagger,
} from "../components/result";
import { SkinVisual } from "../components/SkinVisual";
import { BotanicalSprig, Ripple } from "../components/Botanical";

// Step 7: the complete skin-analysis result, shown once — hero, summary, the seven measurements
// (each with its own "What was measured" detail), and one way forward: the routine.
// Every value comes from `analysis` (services/skinAnalysis.js) as the backend returned it; the benchmark
// is the fixed internal YuriWoori benchmark (backend benchmark.py). Differences (your result − typical)
// are computed here and stated neutrally, because whether higher is better depends on the measurement.

const EASE = [0.22, 1, 0.36, 1];
const ORDER = ["hydration", "texture", "oiliness", "redness", "pigmentation", "pores", "acne"];
const rank = (c) => (ORDER.includes(c.id) ? ORDER.indexOf(c.id) : ORDER.length);
const list = (items) => (items.length < 2 ? items.join("") : `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`);
const signed = (d) => (d === 0 ? "the same as" : `${Math.abs(d)} point${Math.abs(d) === 1 ? "" : "s"} ${d > 0 ? "above" : "below"}`);

function SectionHeading({ id, kicker, title, children, aside }) {
  return (
    <motion.header initial="hidden" whileInView="show" viewport={{ once: true, margin: "-60px" }} variants={fadeUp}
      className="mb-8 flex flex-col gap-5 md:mb-10 lg:flex-row lg:items-end lg:justify-between">
      <div className="max-w-2xl">
        <Kicker>{kicker}</Kicker>
        <h2 id={id} className="mt-3 font-display text-[30px] leading-[1.1] text-[#004647] sm:text-[38px]">{title}</h2>
        {children && <p className="mt-3 text-[15px] leading-relaxed text-ink-soft">{children}</p>}
      </div>
      {aside}
    </motion.header>
  );
}

/* ---------- 1. Hero ---------- */
function SkinProfileHero({ photo, profile, count, hand }) {
  return (
    <section aria-labelledby="profile-title" className="relative mb-16 grid items-center gap-10 md:mb-24 md:grid-cols-[1.05fr_0.95fr] md:gap-14">
      <div aria-hidden="true" className="pointer-events-none absolute left-1/2 top-1/2 -z-10 h-[34rem] w-[min(60rem,100vw)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-mist/70 blur-3xl" />
      <motion.div initial="hidden" animate="show" variants={stagger} className="order-2 text-center md:order-1 md:text-left">
        <motion.div variants={fadeUp} className="flex items-center justify-center gap-2 md:justify-start">
          <img src="/assets/yuriwoori-heart-green.png" alt="" aria-hidden="true" className="h-4 w-auto opacity-80" />
          <Kicker>Your skin profile</Kicker>
        </motion.div>
        <motion.h1 id="profile-title" variants={fadeUp} className="mt-4 font-display text-[42px] leading-[1.02] text-[#004647] sm:text-[56px] lg:text-[64px]">
          Your skin,<br />beautifully understood.
        </motion.h1>
        <motion.p variants={fadeUp} className="mx-auto mt-5 max-w-md text-[15px] leading-relaxed text-ink-soft md:mx-0">
          Your personalised skin profile is based on the measurements from your YuriWoori skin analysis{hand ? " of your hand" : ""}.
        </motion.p>
        <motion.dl variants={fadeUp} className="mt-8 inline-grid grid-cols-2 items-end gap-x-10 border-t border-sage-light/70 pt-6 text-left">
          <div>
            <dt className="text-[10px] font-semibold uppercase tracking-[0.18em] text-sage">Skin type</dt>
            <dd className="mt-2 font-display text-[30px] leading-none text-[#004647]">{profile.skinType}</dd>
          </div>
          {profile.overall != null && (
            <div>
              <dt className="text-[10px] font-semibold uppercase tracking-[0.18em] text-sage">Overall skin score</dt>
              <dd className="mt-1 font-display text-[56px] leading-none text-[#004647] tabular-nums">
                <CountUp value={profile.overall} /><span className="font-sans text-[14px] text-ink-soft/60">/100</span>
              </dd>
            </div>
          )}
        </motion.dl>
        {profile.overall != null && (
          <motion.p variants={fadeUp} className="mx-auto mt-3 max-w-md text-[12px] leading-relaxed text-ink-soft/80 md:mx-0">
            {hand
              ? "The overall score blends hydration, texture, redness and uneven tone; higher is better. Skin type is based on your measured hydration."
              : "The overall score blends hydration, texture, redness, uneven tone, blemishes and pores; higher is better. Skin type is based on your measured hydration and oiliness."}
          </motion.p>
        )}
      </motion.div>

      <motion.figure initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, ease: EASE }}
        className="relative order-1 mx-auto w-full max-w-[280px] sm:max-w-[340px] md:order-2">
        <BotanicalSprig className="absolute -left-14 bottom-2 hidden h-60 w-auto sm:block" />
        <Ripple className="absolute -right-10 -top-8 h-28 w-28" />
        <div aria-hidden="true" className="absolute -inset-3 rounded-t-[999px] rounded-b-[2.4rem] border border-jade-line/80" />
        <div className="relative aspect-[4/5] overflow-hidden rounded-t-[999px] rounded-b-[2rem] bg-mist shadow-float">
          {photo
            ? <img src={photo} alt="Your photo used for this analysis" className="h-full w-full object-cover -scale-x-100" />
            : <div className="flex h-full flex-col items-center justify-center gap-3 text-sm text-ink-soft"><Ripple className="h-20 w-20" />Photo deleted after analysis</div>}
          <div aria-hidden="true" className="absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-[#004647]/35 to-transparent" />
          <figcaption className="absolute bottom-4 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full bg-white/90 px-4 py-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-jade shadow-soft backdrop-blur">
            YuriWoori scan · {count} characteristics
          </figcaption>
        </div>
      </motion.figure>
    </section>
  );
}

/* ---------- 2. Summary (one statement, not a second list of measurements) ---------- */
function SkinSummary({ profile, activeConcerns, flagged }) {
  let title, body;
  if (activeConcerns == null) {
    title = `Your skin type reads as ${profile.skinType.toLowerCase()}`;
    body = "We couldn't load which measurements crossed the levels used to choose products. Your measured values are below.";
  } else if (flagged.length === 0) {
    title = "Your skin reads as balanced";
    body = `Your skin type reads as ${profile.skinType.toLowerCase()}, and no measurement crossed the levels YuriWoori uses to choose targeted products.`;
  } else {
    const phrases = [...new Set(flagged.map((c) => c.phrase).filter(Boolean))];
    title = `${flagged.length === 1 ? "One measurement stands" : `${flagged.length} measurements stand`} out in this scan`;
    body = `Your skin type reads as ${profile.skinType.toLowerCase()}. ${list(flagged.map((c) => c.label))} crossed the level${flagged.length === 1 ? "" : "s"} used to choose products${phrases.length ? `, so your routine focuses on helping ${list(phrases)}` : ""}.`;
  }
  return (
    <motion.section initial="hidden" whileInView="show" viewport={{ once: true, margin: "-60px" }} variants={fadeUp} aria-labelledby="summary-title"
      className="relative mb-16 overflow-hidden rounded-[32px] border border-hairline bg-[linear-gradient(135deg,#FFFFFF_0%,#F1F5EB_100%)] px-6 py-8 sm:px-10 sm:py-10 md:mb-24">
      <BotanicalSprig className="pointer-events-none absolute -right-4 -bottom-16 h-56 w-auto" stroke="#BDDCCD" />
      <div className="relative flex flex-col items-start gap-5 sm:flex-row sm:items-center sm:gap-7">
        <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full border border-jade-line bg-white">
          <Leaf size={22} className="text-jade" strokeWidth={1.5} aria-hidden="true" />
        </span>
        <div className="max-w-3xl">
          <Kicker>Your skin at a glance</Kicker>
          <h2 id="summary-title" className="mt-2 font-display text-[26px] leading-tight text-[#004647] sm:text-[32px]">{title}</h2>
          <p className="mt-2 text-[15px] leading-relaxed text-ink-soft">{body}</p>
        </div>
      </div>
    </motion.section>
  );
}

/* ---------- 3. The seven measurements (the only place they are shown) ---------- */
function MeasurementRow({ c, index }) {
  return (
    <motion.li initial={{ opacity: 0, y: 14 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-40px" }}
      transition={{ duration: 0.5, ease: EASE }}
      className="border-t border-sage-light/50 py-7 sm:py-8">
      <div className="grid gap-6 lg:grid-cols-[minmax(0,15rem)_minmax(0,17rem)_minmax(0,1fr)] lg:items-center lg:gap-10">
        <div className="flex items-center gap-4">
          <SkinVisual metric={c.id} className="h-14 w-14 shrink-0 drop-shadow-[0_3px_6px_rgba(0,70,71,0.08)]" />
          <div className="min-w-0">
            <p className="text-[10px] font-semibold tracking-[0.2em] text-sage/80">{String(index + 1).padStart(2, "0")}</p>
            <h3 className="font-display text-[24px] leading-tight text-[#004647]">{c.label}</h3>
            <p className="mt-0.5 text-[12px] text-ink-soft/75">{c.higherIsBetter ? "Higher is better" : "Higher means more of this trait"}</p>
          </div>
        </div>

        <div className="grid grid-cols-[auto_minmax(0,1fr)] items-end gap-x-6">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-ink-soft/70">Typical</p>
            <p className="mt-1.5 font-display text-[26px] leading-none text-ink-soft/70 tabular-nums">
              {c.typicalBenchmark ?? "—"}{c.typicalBenchmark != null && <span className="font-sans text-[11px] text-ink-soft/50">/100</span>}
            </p>
          </div>
          <div className="border-l border-sage-light/70 pl-6">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#004647]">Your result</p>
            <p className="mt-1.5 flex items-center gap-2.5">
              <span className="font-display text-[44px] leading-none text-[#004647] tabular-nums">{c.yourResult}<span className="font-sans text-[12px] text-ink-soft/60">/100</span></span>
              <BenchmarkDelta c={c} delay={1.05} />
            </p>
          </div>
        </div>

        <ComparisonTrack c={c} />
      </div>

      <details className="group mt-4 lg:ml-[4.5rem]">
        <summary className="inline-flex min-h-[32px] cursor-pointer list-none items-center gap-1.5 rounded-sm text-[12px] font-semibold text-jade hover:text-[#004647] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-jade [&::-webkit-details-marker]:hidden">
          What was measured
          <ChevronDown size={14} className="transition-transform group-open:rotate-180" aria-hidden="true" />
        </summary>
        <div className="mt-2 max-w-2xl text-[13px] leading-relaxed text-ink-soft">
          <p>{c.measures}</p>
          {c.typicalBenchmark != null && <p className="mt-1">Your result is {signed(c.yourResult - c.typicalBenchmark)} the YuriWoori typical benchmark.</p>}
          {!c.matchable && <p className="mt-1 text-ink-soft/80">This measurement is not used to choose products.</p>}
        </div>
      </details>
    </motion.li>
  );
}

function MeasurementComparison({ metrics, hasBenchmark, countWord }) {
  return (
    <section aria-labelledby="compare-title" className="mb-16 md:mb-24">
      <SectionHeading id="compare-title" kicker="Measured values"
        title={hasBenchmark ? "Your skin compared with the YuriWoori typical benchmark" : "Your hand skin, measured"}
        aside={hasBenchmark ? <ComparisonLegend /> : null}>
        {countWord} visible skin characteristics, measured on a 0–100 scale.
      </SectionHeading>
      <ol className="border-b border-sage-light/50">
        {metrics.map((c, i) => <MeasurementRow key={c.id} c={c} index={i} />)}
      </ol>
      <p className="mt-5 text-[11px] leading-relaxed text-ink-soft/65">{hasBenchmark ? BENCHMARK_NOTE : NO_BENCHMARK_NOTE}</p>
    </section>
  );
}

/* ---------- 6. The one next step: the routine (products + cart live there) ---------- */
const JOURNEY = [{ label: "Analysis complete", done: true }, { label: "Routine ready", done: true }, { label: "Continue", done: false }];

function RoutineCTA({ go }) {
  return (
    <motion.section initial="hidden" whileInView="show" viewport={{ once: true, margin: "-60px" }} variants={fadeUp} aria-labelledby="routine-title"
      className="relative mb-10 overflow-hidden rounded-[36px] bg-[#004647] px-6 py-14 text-center text-cream sm:px-12 sm:py-20">
      <BotanicalSprig className="pointer-events-none absolute -right-10 -bottom-12 h-72 w-auto sm:-right-4 sm:h-80" stroke="#9DD4CA" opacity={0.35} />
      <div className="relative mx-auto max-w-2xl">
        <ol className="mx-auto flex max-w-md flex-wrap items-center justify-center gap-x-4 gap-y-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-jade-soft sm:flex-nowrap sm:gap-3 sm:text-[11px]"
          aria-label="Your progress">
          {JOURNEY.map((s, i) => (
            <li key={s.label} className="flex items-center gap-2 sm:gap-3">
              {i > 0 && <span aria-hidden="true" className="hidden h-px w-8 bg-jade-soft/50 sm:block" />}
              <span className="flex items-center gap-1.5 whitespace-nowrap">
                <span aria-hidden="true" className={`flex h-4 w-4 items-center justify-center rounded-full border ${s.done ? "border-jade-soft bg-jade-soft text-[#004647]" : "border-jade-soft/70"}`}>
                  {s.done && <Check size={10} strokeWidth={3} />}
                </span>
                {s.label}
              </span>
            </li>
          ))}
        </ol>

        <p className="mt-10 text-[11px] font-semibold uppercase tracking-[0.2em] text-jade-soft">Your routine starts here</p>
        <h2 id="routine-title" className="mt-4 font-display text-[34px] leading-[1.08] text-white sm:text-[50px]">Your personalised routine is ready.</h2>
        <p className="mx-auto mt-5 max-w-lg text-[15px] leading-relaxed text-cream/80">
          Based on your skin analysis, discover the YuriWoori products selected for your skincare routine.
        </p>
        <button type="button" onClick={() => go("routine")}
          className="mt-9 inline-flex min-h-[52px] w-full items-center justify-center gap-2 whitespace-nowrap rounded-pill bg-cream px-10 text-[15px] font-semibold tracking-wide text-[#004647] shadow-[0_10px_30px_-10px_rgba(0,0,0,0.35)] transition-colors hover:bg-white focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-white sm:w-auto">
          See my routine <ArrowRight size={17} aria-hidden="true" />
        </button>
      </div>
    </motion.section>
  );
}

export default function Profile({ go, photo, analysis }) {
  const { concerns = [], profile, activeConcerns } = analysis ?? {};
  if (!profile) return null;
  const hand = analysis?.bodyPart === "hand"; // hand scans measure 4 characteristics (no pores, blemishes or oil)
  const metrics = [...concerns].sort((a, b) => rank(a) - rank(b));
  const hasBenchmark = metrics.some((c) => c.typicalBenchmark != null);
  const countWord = { 4: "Four", 7: "Seven" }[metrics.length] ?? String(metrics.length);

  return (
    <div className="flex-1 w-full max-w-6xl mx-auto px-4 sm:px-8 py-8 sm:py-12">
      <SkinProfileHero photo={photo} profile={profile} count={metrics.length} hand={hand} />
      <SkinSummary profile={profile} activeConcerns={activeConcerns} flagged={metrics.filter((c) => c.flagged)} />
      <MeasurementComparison metrics={metrics} hasBenchmark={hasBenchmark} countWord={countWord} />
      <RoutineCTA go={go} />
      <Disclaimer className="mt-8" />
    </div>
  );
}
