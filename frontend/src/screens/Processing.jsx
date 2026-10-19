import { useEffect, useRef, useState } from "react";
import { AlertCircle, RotateCcw, RefreshCcw, CircleCheck, Loader2, CircleDashed } from "lucide-react";
import { Button, Eyebrow } from "../components/Button";
import { analyzeSkin } from "../services/skinAnalysis";
import { createReportPhoto } from "../services/reportPhoto";
import { motion } from "framer-motion";

// These are the real backend steps, advanced by analyzeSkin()'s onStage callback.
const STAGES = [
  { key: "upload", label: "Uploading your photo" },
  { key: "quality", label: "Photo quality check" },
  { key: "analyze", label: "Finding your face and measuring skin", handLabel: "Finding your hand and measuring skin" },
  { key: "match", label: "Matching YuriWoori products" },
];
const ORDER = [...STAGES.map((s) => s.key), "done"];

// Advice per error kind (see scanError() in services/skinAnalysis.js).
const ERROR_HELP = {
  quality: { title: "Photo quality check failed", retake: true },
  face: { title: "We couldn't use this photo of your face", retake: true },
  hand: { title: "We couldn't find your hand", retake: true },
  photo: { title: "That photo couldn't be read", retake: true },
  network: { title: "Can't reach the YuriWoori server", retake: false },
  rate: { title: "The server is busy", retake: false },
  server: { title: "Analysis failed", retake: false },
  auth: { title: "Please enter your details again", retake: false, signup: true },
};

function StageRow({ stage, state }) {
  const Icon = state === "done" ? CircleCheck : state === "active" ? Loader2 : state === "failed" ? AlertCircle : CircleDashed;
  const tone = state === "done" ? "text-jade" : state === "active" ? "text-jade" : state === "failed" ? "text-danger" : "text-ink-soft/40";
  return (
    <li className="flex items-start gap-3 text-left">
      <Icon size={18} className={`${tone} shrink-0 mt-0.5 ${state === "active" ? "animate-spin" : ""}`} strokeWidth={2} />
      <div>
        <p className={`text-sm font-medium ${state === "pending" ? "text-ink-soft/60" : "text-jade-deep"}`}>{stage.label}</p>
      </div>
    </li>
  );
}

// Measured characteristics, named only (the real values appear on the next screen).
const CATEGORIES = [
  { label: "Hydration", pos: "left-0 top-[18%]" },
  { label: "Texture", pos: "right-0 top-[12%]" },
  { label: "Tone", pos: "left-[4%] bottom-[14%]" },
  { label: "Visible pores", pos: "right-0 bottom-[20%]" },
];

/* The user's own photo at the centre of quiet analysis rings: "your skin is being analysed". */
function AnalysisVisual({ photo, running }) {
  return (
    <div className="relative mx-auto mb-7 aspect-square w-full max-w-[300px]">
      <div aria-hidden="true" className="absolute inset-[6%] rounded-full bg-[radial-gradient(circle,#FFFFFF_0%,#E3ECEB_70%,transparent_72%)]" />
      <svg aria-hidden="true" viewBox="0 0 200 200" className="absolute inset-0 h-full w-full">
        <circle cx="100" cy="100" r="88" fill="none" stroke="#BDDCCD" strokeWidth="0.8" />
        <motion.g style={{ transformOrigin: "100px 100px" }} animate={running ? { rotate: 360 } : {}} transition={{ duration: 24, repeat: Infinity, ease: "linear" }}>
          <circle cx="100" cy="100" r="76" fill="none" stroke="#528778" strokeOpacity="0.45" strokeWidth="0.8" strokeDasharray="1.5 6" />
          <circle cx="100" cy="24" r="2.4" fill="#006968" />
          <circle cx="176" cy="100" r="1.8" fill="#9DD4CA" />
        </motion.g>
        <motion.g style={{ transformOrigin: "100px 100px" }} animate={running ? { rotate: -360 } : {}} transition={{ duration: 36, repeat: Infinity, ease: "linear" }}>
          <circle cx="100" cy="100" r="64" fill="none" stroke="#9DD4CA" strokeOpacity="0.8" strokeWidth="0.8" strokeDasharray="30 12 4 12" />
        </motion.g>
      </svg>
      <div className="absolute inset-[24%] overflow-hidden rounded-full bg-mist ring-4 ring-white shadow-float">
        {photo && <img src={photo} alt="Your photo being analysed" className="h-full w-full object-cover -scale-x-100" />}
        {running && (
          <motion.div aria-hidden="true"
            className="absolute inset-x-0 h-10 bg-gradient-to-b from-transparent via-white/35 to-transparent"
            animate={{ top: ["-20%", "100%"] }} transition={{ duration: 2.6, repeat: Infinity, ease: "easeInOut" }}
          />
        )}
      </div>
      {CATEGORIES.map((c, i) => (
        <motion.span key={c.label}
          className={`absolute ${c.pos} rounded-full bg-white/90 backdrop-blur px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-jade shadow-soft border border-hairline`}
          animate={running ? { opacity: [0.55, 1, 0.55] } : { opacity: 1 }}
          transition={{ duration: 2.4, repeat: Infinity, delay: i * 0.6 }}
        >
          {c.label}
        </motion.span>
      ))}
    </div>
  );
}

export default function Processing({ go, photo, setPhoto, bodyPart, setAnalysis, setReportPhoto, signOut }) {
  const [stage, setStage] = useState("upload");
  const [error, setError] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const started = useRef(-1);

  useEffect(() => {
    if (started.current === attempt || !photo) return;
    started.current = attempt;
    setError(null); setStage("upload");

    analyzeSkin(photo, setStage, bodyPart)
      .then((res) => {
        setAnalysis(res);
        // The server never kept the photo. For this scan's report it stays in this tab's memory only (an object URL
        // bound to res.scanId, released on a new scan, home or sign-out); the capture itself is let go of here.
        // After a failed analysis it stays in memory only, for "Try again".
        setReportPhoto?.(createReportPhoto(photo, res.scanId));
        setTimeout(() => { go("profile"); setPhoto?.(null); }, 900); // let the last tick render
      })
      .catch((e) => {
        // the technical cause stays visible to developers; the user gets the matching advice
        if (import.meta.env.DEV) console.warn("[skin analysis] failed", { status: e.status, reason: e.reason, kind: e.kind, message: e.message });
        setError({
          kind: e.kind ?? (e.status === 0 ? "network" : e.status === 401 ? "auth" : e.status === 429 ? "rate" : "server"),
          message: e.message || "Something went wrong analyzing your photo.",
        });
      });
  }, [photo, bodyPart, attempt, go, setAnalysis]);

  const current = ORDER.indexOf(stage);
  const stateOf = (i) => (error && i === current ? "failed" : i < current ? "done" : i === current ? "active" : "pending");

  const help = error ? ERROR_HELP[error.kind] ?? ERROR_HELP.server : null;

  return (
    <div className="flex-1 w-full max-w-4xl mx-auto flex flex-col items-center justify-center px-4 py-6 sm:py-8 text-center">
      <Eyebrow className="mb-2 text-jade tracking-[0.14em]">Skin analysis</Eyebrow>
      <h2 className="font-display text-3xl text-jade-deep mb-5">{error ? "Let's try that again" : stage === "done" ? "Your skin profile is ready" : "Analysing your skin"}</h2>

      <div className="grid w-full grid-cols-1 md:grid-cols-2 items-center gap-2 md:gap-10">
        <AnalysisVisual photo={photo} running={!error && stage !== "done"} />
        <div className="w-full max-w-md mx-auto">
          <ol className="w-full flex flex-col gap-4 bg-white/85 rounded-2xl border border-hairline shadow-soft p-5 mb-6" aria-live="polite">
            {STAGES.map((s, i) => <StageRow key={s.key} stage={bodyPart === "hand" && s.handLabel ? { ...s, label: s.handLabel } : s} state={stateOf(i)} />)}
          </ol>

      {stage === "done" && !error && <p className="text-sm font-medium text-jade">Done. Opening your skin profile…</p>}

      {error && (
        <div className="w-full">
          <div className="rounded-card bg-danger-soft border border-danger-line p-5 mb-5 text-left">
            <p className="font-display text-xl text-danger mb-1">{help.title}</p>
            <p className="text-sm leading-relaxed text-ink-soft">{error.message}</p>
          </div>
          <div className="flex flex-col w-full gap-3">
            {help.signup ? (
              <Button full icon={null} onClick={() => { signOut?.(); go("about"); }}>Enter my details again</Button>
            ) : help.retake ? (
              <>
                <Button full iconLeft={RotateCcw} icon={null} onClick={() => go("camera")}>Retake photo</Button>
                <Button variant="secondary" full onClick={() => go("tips")} icon={null}>See photo tips</Button>
              </>
            ) : (
              <>
                <Button full onClick={() => setAttempt((a) => a + 1)} icon={RefreshCcw}>Try again</Button>
                <Button variant="secondary" iconLeft={RotateCcw} icon={null} full onClick={() => go("camera")}>Retake photo</Button>
              </>
            )}
          </div>
        </div>
      )}
        </div>
      </div>
    </div>
  );
}
