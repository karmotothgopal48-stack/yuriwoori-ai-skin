import { Sun, Glasses, ScanFace, Camera, Focus } from "lucide-react";
import { Button, Eyebrow } from "../components/Button";
import { motion } from "framer-motion";

// Each tip maps to a real check: lighting and sharpness are scored by the server's quality check,
// and the server only analyzes a face it finds near the middle of the photo.
const TIPS = [
  { icon: Sun, t: "Soft, even light", b: "Face a window or a soft lamp. Very dark or very bright photos can't be analysed." },
  { icon: ScanFace, t: "One face, centred", b: "Only you, in the middle of the oval — the analysis looks for one face near the centre." },
  { icon: Focus, t: "Fill the oval", b: "Hold the camera at arm's length so your face fills the oval — too far away and the face may not be found." },
  { icon: Glasses, t: "Bare face, no glare", b: "Remove glasses if you can; lens glare can hide your face. Skip heavy makeup for a truer reading." },
  { icon: Camera, t: "Hold still", b: "Keep the camera steady and look straight ahead. Blurry photos fail the sharpness check." },
];

const containerVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.08 }
  }
};

const itemVariants = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 300, damping: 24 } }
};

/* Positioning illustration (no photograph: the campaign's only usable model photo is already used on the
   Start and Permission screens). A soft, featureless silhouette sits inside the same guide oval the camera shows,
   lit from one side, to say "face the light, centre your face, fill the oval". */
function PrepVisual() {
  return (
    <figure className="relative w-full max-w-[460px] aspect-[16/9] overflow-hidden rounded-[1.75rem] border border-hairline bg-[linear-gradient(135deg,#F7F8F3_0%,#EEF3EE_55%,#E3ECEB_100%)] shadow-float">
      {/* window light from the left */}
      <div aria-hidden="true" className="absolute -left-16 -top-10 h-[140%] w-1/2 rotate-12 bg-[linear-gradient(90deg,rgba(255,255,255,0.95),rgba(255,255,255,0))] blur-2xl" />
      <svg viewBox="0 0 320 180" className="absolute inset-0 h-full w-full" role="img" aria-label="A face centred inside the scan oval, lit by soft light from the side">
        <defs>
          <linearGradient id="prep-skin" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor="#FFFFFF" />
            <stop offset="1" stopColor="#D5E4DF" />
          </linearGradient>
          <linearGradient id="prep-hair" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#528778" stopOpacity="0.55" />
            <stop offset="1" stopColor="#004E4D" stopOpacity="0.75" />
          </linearGradient>
        </defs>
        {/* shoulders + neck */}
        <path d="M96 180 C100 150 128 138 148 134 L148 118 L172 118 L172 134 C192 138 220 150 224 180 Z" fill="url(#prep-skin)" />
        {/* head */}
        <ellipse cx="160" cy="84" rx="31" ry="39" fill="url(#prep-skin)" />
        {/* hair, tied back */}
        <path d="M128 86 C124 52 146 38 162 40 C184 41 196 58 192 86 C190 70 180 58 160 58 C142 58 132 70 128 86 Z" fill="url(#prep-hair)" />
        {/* guide oval (same shape language as the camera screen) */}
        <ellipse cx="160" cy="86" rx="46" ry="58" fill="none" stroke="#006968" strokeOpacity="0.55" strokeWidth="1.2" strokeDasharray="3 5" />
        <g stroke="#006968" strokeOpacity="0.5" strokeWidth="1.6" fill="none" strokeLinecap="round">
          <path d="M104 30 q-8 0 -8 8" /><path d="M216 30 q8 0 8 8" /><path d="M96 134 q0 8 8 8" /><path d="M224 134 q0 8 -8 8" />
        </g>
        {/* a few quiet analysis points (forehead, cheeks, chin) */}
        {[[160, 62], [176, 92], [146, 96], [160, 112]].map(([x, y]) => (
          <circle key={`${x}-${y}`} cx={x} cy={y} r="1.8" fill="#FFFFFF" stroke="#9DD4CA" strokeWidth="1" />
        ))}
      </svg>
      <span className="absolute left-4 top-4 inline-flex items-center gap-1.5 rounded-full bg-white/85 backdrop-blur px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-jade shadow-soft">
        <span className="h-1.5 w-1.5 rounded-full bg-jade" aria-hidden="true" /> Soft, even light
      </span>
      <span className="absolute bottom-4 right-4 rounded-full bg-white/85 backdrop-blur px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-jade shadow-soft">
        Face fills the oval
      </span>
    </figure>
  );
}

export default function Tips({ go }) {
  return (
    <div className="flex-1 w-full max-w-5xl mx-auto px-4 sm:px-8 py-6 sm:py-8 flex flex-col">
      <div className="flex flex-col items-center text-center mb-8">
        <Eyebrow className="mb-2 text-jade tracking-[0.14em]">Tips</Eyebrow>
        <h2 className="font-display text-3xl sm:text-4xl text-jade-deep mb-5">How to get the best scan</h2>
        
        <PrepVisual />
      </div>

      <motion.div 
        variants={containerVariants}
        initial="hidden"
        animate="show"
        className="flex flex-wrap justify-center gap-3 sm:gap-4 mb-8"
      >
        {TIPS.map((t, i) => (
          <motion.div 
            key={i} 
            variants={itemVariants}
            className="flex items-start gap-4 bg-white/80 rounded-2xl p-5 shadow-soft border border-hairline w-full sm:w-[calc(50%-0.5rem)] lg:w-[calc(33.333%-0.7rem)]"
          >
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-mist border border-jade-line/60">
              <t.icon size={18} className="text-jade" strokeWidth={1.5} aria-hidden="true" />
            </div>
            <div>
              <h3 className="font-semibold text-jade-deep mb-1 text-[15px]" style={{ fontFamily: "var(--font-sans)", letterSpacing: "normal" }}>{t.t}</h3>
              <p className="text-[13px] leading-relaxed text-ink-soft">{t.b}</p>
            </div>
          </motion.div>
        ))}
      </motion.div>

      <div className="flex flex-col-reverse sm:flex-row items-center justify-center gap-3 sm:gap-4 mt-auto">
        <Button variant="secondary" onClick={() => go("permission")} full className="sm:w-auto">
          Back
        </Button>
        <Button onClick={() => go("camera")} full className="sm:w-auto">
          Continue to Camera
        </Button>
      </div>
    </div>
  );
}
