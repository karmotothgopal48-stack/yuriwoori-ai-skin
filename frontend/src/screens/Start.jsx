import { Sparkles, Leaf, ShieldCheck, ScanFace } from "lucide-react";
import { Button, Eyebrow } from "../components/Button";
import { AnalysisPortrait } from "../components/AnalysisPortrait";
import { PORTRAITS } from "../theme/brand";
import { maskEmail } from "../services/contact";

const POINTS = [
  { icon: ScanFace, t: "Scan", b: "One clear selfie, checked for quality and a centred face." },
  { icon: Sparkles, t: "Understand", b: "Seven visible skin characteristics, each explained." },
  { icon: Leaf, t: "Personalise", b: "An AM/PM routine with YuriWoori products, and why each one." },
];

export default function Start({ go, user, signOut, serverUnreachable = false }) {
  return (
    <div className="yw-enter">
      <section className="relative">
        {/* Soft ivory with a faint sage wash behind the portrait */}
        <div aria-hidden="true" className="pointer-events-none absolute inset-y-0 left-1/2 w-screen -translate-x-1/2">
          <div className="absolute right-[-10%] top-1/2 h-[36rem] w-[36rem] -translate-y-1/2 rounded-full bg-mist blur-3xl opacity-80" />
        </div>

        <div className="relative mx-auto grid max-w-6xl grid-cols-1 items-center gap-6 px-5 pt-5 pb-8 sm:px-10 sm:py-8 md:grid-cols-[1.1fr_0.9fr] md:gap-12 md:py-10">
          <div className="text-center md:text-left">
            <Eyebrow className="text-jade">AI Skin Analysis</Eyebrow>
            <h1 className="mt-2 font-display text-[30px] leading-[1.08] text-jade-deep sm:text-[44px] lg:text-[52px]">
              See what one selfie says <br className="hidden md:block" />about your skin.
            </h1>
            <p className="mx-auto mt-4 max-w-md text-[15px] leading-relaxed text-ink-soft md:mx-0">
              A short guided scan measures visible skin characteristics and creates a personalised skincare routine with YuriWoori products.
            </p>

            <div className="mt-5 sm:mt-7 flex flex-col gap-2.5 sm:gap-3 sm:flex-row sm:justify-center md:justify-start">
              {/* Step 1 (gender + age) always comes first; name + email are asked just before the photo is uploaded */}
              <Button onClick={() => go("about")} disabled={user === undefined}>Start Skin Analysis</Button>
              <Button variant="secondary" icon={null} onClick={() => go("assistant")}>Ask Yuri</Button>
            </div>

            {/* Start waits until a saved session has been checked; say why instead of a silently disabled button */}
            {user === undefined && (
              <p className={`mt-4 text-xs ${serverUnreachable ? "text-danger-strong" : "text-ink-soft"}`} role="status">
                {serverUnreachable
                  ? "Can't reach the YuriWoori server, so your saved details can't be checked yet. Retrying automatically…"
                  : "Checking your saved details…"}
              </p>
            )}

            {user && (
              <p className="mt-4 text-xs text-ink-soft">
                {/* masked: on a shared device the next visitor sees this line */}
                Continuing as <span className="font-semibold text-ink">{user.name}</span> ({maskEmail(user.email)}) ·{" "}
                <button onClick={signOut} className="font-semibold text-jade underline-offset-2 hover:underline">Not you?</button>
              </p>
            )}

            <div className="mt-6 space-y-1 text-xs text-ink-soft">
              <p className="flex items-center justify-center gap-2 md:justify-start">
                <ShieldCheck size={14} className="shrink-0 text-jade" /> Your photo is sent to the YuriWoori server for analysis.
              </p>
              <p>This analysis is for skincare guidance and is not a medical diagnosis.</p>
            </div>
          </div>

          <div className="order-first flex justify-center md:order-none md:justify-end">
            <figure className="relative w-full max-w-[190px] sm:max-w-[320px] md:max-w-[360px] lg:max-w-[400px]">
              <div className="absolute -inset-2 sm:-inset-3 rounded-[1.75rem] sm:rounded-[2.25rem] border border-sage-light/70" aria-hidden="true" />
              <AnalysisPortrait portrait={PORTRAITS.hero} priority />
            </figure>
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl grid-cols-1 gap-3 px-5 pb-10 sm:grid-cols-3 sm:px-10">
        {POINTS.map((p) => (
          <div key={p.t} className="flex items-start gap-3 rounded-2xl border border-hairline bg-white/60 p-4">
            <p.icon size={20} className="mt-0.5 shrink-0 text-jade" strokeWidth={1.5} />
            <div>
              <h3 className="text-lg leading-tight">{p.t}</h3>
              <p className="mt-1 text-[13px] leading-relaxed text-ink-soft">{p.b}</p>
            </div>
          </div>
        ))}
      </section>
    </div>
  );
}
