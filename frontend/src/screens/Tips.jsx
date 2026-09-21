import { Sun, Glasses, ScanFace } from "lucide-react";
import { Button, Eyebrow } from "../components/Button";
import { IMAGES } from "../theme/brand";

const TIPS = [
  { n: 1, icon: Glasses, t: "Take a natural picture", b: "Remove make-up and glasses. Pull your hair back and tie it." },
  { n: 2, icon: Sun, t: "Ensure it's a well-lit face", b: "Face a window or soft light. Avoid strong shadows and backlight." },
  { n: 3, icon: ScanFace, t: "Align your face", b: "Place your face inside the outline and look straight ahead." },
];

export default function Tips({ go }) {
  return (
    <div className="yw-enter mx-auto max-w-5xl px-5 py-14 sm:px-10">
      <Eyebrow>Before you begin</Eyebrow>
      <h2 className="mt-3 text-3xl text-jade sm:text-4xl">How to take your picture</h2>
      <div className="mt-10 grid grid-cols-1 items-start gap-8 md:grid-cols-[minmax(0,320px)_1fr]">
        <img src={IMAGES.analysisFace} alt="Face centred and evenly lit" className="mx-auto w-full max-w-xs rounded-3xl object-cover md:max-w-none" />
        <div className="space-y-4">
        {TIPS.map((t) => (
          <div key={t.n} className="rounded-2xl bg-cream p-6">
            <div className="flex items-center justify-between">
              <span className="font-display text-5xl leading-none text-jade-soft">{t.n}</span>
              <div className="flex h-11 w-11 items-center justify-center rounded-full bg-white"><t.icon size={20} className="text-jade" /></div>
            </div>
            <h3 className="mt-6 text-xl">{t.t}</h3>
            <p className="mt-2 text-sm leading-relaxed text-ink-soft">{t.b}</p>
          </div>
        ))}
        </div>
      </div>
      <div className="mt-10 flex flex-col items-start gap-3">
        <Button onClick={() => go("camera")}>I'm ready — open camera</Button>
        <p className="text-xs text-ink-soft">
          By continuing you agree to the YuriWoori privacy policy. This is a cosmetic skin reading, not a medical diagnosis.
        </p>
      </div>
    </div>
  );
}
