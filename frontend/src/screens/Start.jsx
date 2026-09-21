import { Sparkles, Leaf, ShieldCheck, ScanFace } from "lucide-react";
import { Button, Eyebrow } from "../components/Button";
import { IMAGES } from "../theme/brand";

export default function Start({ go }) {
  const points = [
    { icon: ScanFace, t: "Scan", b: "A guided face capture reads visible skin characteristics." },
    { icon: Sparkles, t: "Understand", b: "Seven skin areas explained clearly and gently." },
    { icon: Leaf, t: "Personalize", b: "A routine and products matched to your profile." },
  ];
  return (
    <div className="yw-enter">
      <section className="bg-gradient-to-br from-cream via-aqua to-sage-light/60">
        <div className="mx-auto grid grid-cols-1 max-w-6xl items-center gap-10 px-5 py-14 sm:px-10 md:grid-cols-2 md:py-20">
          <div>
            <Eyebrow>AI Skin Analysis</Eyebrow>
            <h1 className="mt-4 text-4xl leading-[1.1] text-jade sm:text-5xl">Understand your skin better with AI.</h1>
            <p className="mt-5 max-w-md text-[15px] leading-relaxed text-ink-soft">
              Take a short skin analysis to get a personalized skincare routine, built around YuriWoori's Korean elixirs.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button onClick={() => go("permission")}>Start Skin Analysis</Button>
              <Button variant="ghost" icon={null} onClick={() => go("assistant")}>Ask Yuri</Button>
            </div>
            <p className="mt-5 flex items-center gap-2 text-xs text-ink-soft">
              <ShieldCheck size={14} className="text-jade" /> Your photo is sent to the YuriWoori server for analysis.
            </p>
          </div>
          <div className="flex justify-center">
            <img src={IMAGES.analysisFace} alt="AI skin analysis illustration" className="w-full max-w-sm rounded-[2rem] object-cover shadow-xl shadow-jade/10" />
          </div>
        </div>
      </section>
      <section className="mx-auto grid grid-cols-1 max-w-6xl gap-5 px-5 py-14 sm:px-10 md:grid-cols-3">
        {points.map((p) => (
          <div key={p.t} className="rounded-2xl border border-mist p-6">
            <p.icon size={22} className="text-jade" />
            <h3 className="mt-4 text-xl">{p.t}</h3>
            <p className="mt-2 text-sm leading-relaxed text-ink-soft">{p.b}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
