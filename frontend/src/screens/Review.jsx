import { RotateCcw, Check, Sparkles, User, ShieldCheck } from "lucide-react";
import { Button, Eyebrow } from "../components/Button";
import { motion } from "framer-motion";

const CHECKS = {
  face: ["One face, near the centre", "Lighting is soft and even", "Photo is sharp, not blurry"],
  hand: ["One hand, filling most of the photo", "Lighting is soft and even", "Photo is sharp, not blurry"],
};

export default function Review({ go, photo, bodyPart = "face" }) {
  const hand = bodyPart === "hand";
  return (
    <div className="flex-1 w-full max-w-4xl mx-auto px-4 sm:px-8 py-6 sm:py-10">
      <div className="text-center mb-6 sm:mb-8">
        <Eyebrow className="mb-2 text-jade tracking-[0.14em]">Step 4 &middot; Review</Eyebrow>
        <h2 className="font-display text-3xl sm:text-4xl text-[#004647]">Review your scan</h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-[auto_1fr] items-center gap-6 md:gap-10 justify-items-center md:justify-items-stretch">
        {/* The user's own capture, shown exactly as taken (only mirrored like the live preview) */}
        <motion.figure
          initial={{ opacity: 0, scale: 0.97, y: 8 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          className="w-full max-w-[300px] sm:max-w-[320px] rounded-[2rem] bg-white p-3 pb-4 shadow-float border border-hairline"
        >
          <div className="relative aspect-[3/4] w-full overflow-hidden rounded-[1.5rem] bg-mist">
            {photo ? (
              <img src={photo} alt="Your captured photo" className="h-full w-full object-cover -scale-x-100" />
            ) : (
              <div className="flex h-full w-full items-center justify-center text-sm text-ink-soft">No photo found</div>
            )}
            {photo && (
              <span className="absolute left-3 top-3 inline-flex items-center gap-1.5 rounded-full bg-white/90 backdrop-blur px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-jade shadow-soft">
                <User size={11} strokeWidth={2} aria-hidden="true" /> Your photo
              </span>
            )}
          </div>
          <figcaption className="mt-3 flex items-center justify-center gap-2 text-[10px] font-semibold uppercase tracking-[0.2em] text-sage">
            <span className="h-px w-6 bg-sage-light" aria-hidden="true" /> YuriWoori Scan <span className="h-px w-6 bg-sage-light" aria-hidden="true" />
          </figcaption>
        </motion.figure>

        <div className="w-full max-w-[380px] md:max-w-none">
          <div className="rounded-2xl bg-white/80 border border-hairline shadow-soft p-5">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-sage mb-3">Check for clarity</p>
            <ul className="flex flex-col gap-2.5">
              {CHECKS[hand ? "hand" : "face"].map((text) => (
                <li key={text} className="flex items-center gap-3 text-sm text-ink">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-mist border border-jade-line/60">
                    <Check size={13} className="text-jade" strokeWidth={2} aria-hidden="true" />
                  </span>
                  {text}
                </li>
              ))}
            </ul>
            <p className="mt-4 pt-4 border-t border-sage-light/70 text-[12px] leading-relaxed text-ink-soft">
              Next, your photo is checked for sharpness, lighting and {hand ? "your hand" : "one centred face"}.
            </p>
          </div>

          <p className="mt-4 flex items-start gap-2 rounded-xl bg-mist/60 border border-jade-line/50 px-3.5 py-2.5 text-[13px] leading-relaxed text-[#004647]">
            <ShieldCheck size={16} className="mt-0.5 shrink-0" strokeWidth={1.75} aria-hidden="true" />
            <span>Your photo is not stored and is deleted after analysis.</span>
          </p>

          <div className="mt-5 flex flex-col-reverse sm:flex-row gap-3">
            <Button variant="secondary" iconLeft={RotateCcw} icon={null} full onClick={() => go("camera")}>
              Retake
            </Button>
            <Button full icon={Sparkles} onClick={() => go("processing")} disabled={!photo}>
              Analyze My Skin
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
