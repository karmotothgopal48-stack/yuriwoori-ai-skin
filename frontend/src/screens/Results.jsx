import { useState } from "react";
import { Button, Eyebrow } from "../components/Button";

const STATUS = {
  strength: { label: "Strength", cls: "bg-aqua text-jade" },
  balanced: { label: "Balanced", cls: "bg-mist text-ink-soft" },
  focus: { label: "Focus area", cls: "bg-jade text-white" },
};

export default function Results({ go, photo, analysis }) {
  const concerns = analysis?.concerns ?? [];
  const [id, setId] = useState(concerns[0]?.id);
  const cur = concerns.find((c) => c.id === id) ?? concerns[0];
  if (!cur) return null;

  return (
    <div className="yw-enter mx-auto max-w-6xl px-5 py-12 sm:px-10">
      <Eyebrow>Skin analysis results</Eyebrow>
      <h2 className="mt-3 text-3xl text-jade sm:text-4xl">Here's what we noticed</h2>

      <div className="mt-8 flex flex-wrap gap-2">
        {concerns.map((c) => (
          <button key={c.id} onClick={() => setId(c.id)} aria-pressed={c.id === cur.id}
            className={`rounded-full border px-4 py-2 text-xs font-semibold transition ${c.id === cur.id ? "border-jade bg-jade text-white" : "border-jade-line text-ink-soft hover:border-jade hover:text-jade"}`}>
            {c.label}
          </button>
        ))}
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-2">
        <div className="relative mx-auto aspect-[3/4] w-full max-w-md overflow-hidden rounded-3xl bg-mist">
          {photo && <img src={photo} alt="Your photo" className="h-full w-full object-cover" />}
          {cur.markers.map(([x, y], i) => (
            <span key={`${cur.id}-${i}`} className="absolute -translate-x-1/2 -translate-y-1/2" style={{ left: `${x}%`, top: `${y}%` }}>
              <span className="block h-4 w-4 rounded-full border-2 border-white bg-jade/70 shadow" />
            </span>
          ))}
        </div>

        <div className="flex flex-col justify-center rounded-3xl bg-cream p-7">
          <span className={`self-start rounded-full px-3 py-1 text-[11px] font-semibold ${STATUS[cur.status].cls}`}>{STATUS[cur.status].label}</span>
          <h3 className="mt-4 text-3xl">{cur.label}</h3>
          <p className="mt-2 text-sm leading-relaxed text-ink-soft">{cur.note}</p>
          <div className="mt-6 h-2 overflow-hidden rounded-full bg-white"><div className="h-full rounded-full bg-jade" style={{ width: `${cur.score}%` }} /></div>
          <p className="mt-2 text-xs text-ink-soft">Score {cur.score} / 100</p>
          <p className="mt-6 text-[11px] leading-relaxed text-ink-soft">Cosmetic reading of visible skin only. Not a medical diagnosis.</p>
        </div>
      </div>

      <div className="mt-10"><Button onClick={() => go("profile")}>View my skin profile</Button></div>
    </div>
  );
}
