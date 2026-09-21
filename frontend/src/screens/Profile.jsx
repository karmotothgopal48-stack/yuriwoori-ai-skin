import { Button, Eyebrow } from "../components/Button";
import { ScoreRing } from "../components/ScoreRing";

export default function Profile({ go, photo, analysis }) {
  const { concerns = [], profile } = analysis ?? {};
  if (!profile) return null;
  const overall = profile.overall ?? Math.round(concerns.reduce((a, c) => a + c.score, 0) / concerns.length);
  const byId = Object.fromEntries(concerns.map((c) => [c.id, c]));
  const strengths = concerns.filter((c) => c.status === "strength");

  return (
    <div className="yw-enter mx-auto max-w-5xl px-5 py-12 sm:px-10">
      <Eyebrow>My skin profile</Eyebrow>
      <h2 className="mt-3 text-3xl text-jade sm:text-4xl">Your skin, at a glance</h2>

      <div className="mt-8 grid grid-cols-1 gap-5 md:grid-cols-[1.2fr_1fr]">
        <div className="flex items-center gap-6 rounded-3xl bg-jade p-7 text-white">
          <div className="h-24 w-24 shrink-0 overflow-hidden rounded-full bg-white/20">
            {photo && <img src={photo} alt="" className="h-full w-full object-cover" />}
          </div>
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-jade-soft">Skin type</p>
            <p className="font-display text-3xl">{profile.skinType}</p>
            <p className="mt-2 text-sm leading-relaxed text-white/80">{profile.summary}</p>
          </div>
        </div>
        <div className="flex items-center gap-5 rounded-3xl bg-cream p-7">
          <ScoreRing value={overall} label="Overall skin score" />
          <div><p className="text-sm font-semibold">Overall balance</p><p className="text-xs text-ink-soft">Based on your scan</p></div>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-5 md:grid-cols-2">
        <div className="rounded-3xl border border-mist p-7">
          <h3 className="text-xl">Focus areas</h3>
          <ol className="mt-4 space-y-3">
            {profile.focus.map((f, i) => (
              <li key={f} className="flex items-center gap-3 text-sm">
                <span className="flex h-6 w-6 items-center justify-center rounded-full border border-jade text-xs text-jade">{i + 1}</span>
                {byId[f]?.label}
              </li>
            ))}
          </ol>
        </div>
        <div className="rounded-3xl border border-mist p-7">
          <h3 className="text-xl">Strengths</h3>
          <ul className="mt-4 space-y-3 text-sm">
            {strengths.map((s) => <li key={s.id} className="flex justify-between"><span>{s.label}</span><span className="text-jade">{s.score}</span></li>)}
          </ul>
        </div>
      </div>

      <div className="mt-10"><Button onClick={() => go("recommendations")}>See recommendations</Button></div>
    </div>
  );
}
