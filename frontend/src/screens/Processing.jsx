import { useEffect, useRef, useState } from "react";
import { Check, AlertCircle } from "lucide-react";
import { Button } from "../components/Button";
import { ScoreRing } from "../components/ScoreRing";
import { ANALYSIS_STAGES } from "../data/mock";
import { analyzeSkin } from "../services/skinAnalysis";

export default function Processing({ go, photo, setAnalysis }) {
  const [stage, setStage] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const started = useRef(-1); // one backend scan per attempt, even under StrictMode's double effect

  useEffect(() => {
    if (started.current === attempt) return;
    started.current = attempt;
    setError(""); setResult(null); setStage(0);
    analyzeSkin(photo).then(setResult).catch((e) => setError(e.message || "Something went wrong analyzing your photo."));
  }, [photo, attempt]);

  useEffect(() => {
    if (error) return;
    const last = ANALYSIS_STAGES.length;
    if (stage < last) { const t = setTimeout(() => setStage((s) => s + 1), 900); return () => clearTimeout(t); }
    if (result) { setAnalysis(result); const t = setTimeout(() => go("results"), 500); return () => clearTimeout(t); }
  }, [stage, result, error]); // eslint-disable-line react-hooks/exhaustive-deps

  if (error) {
    return (
      <div className="yw-enter mx-auto flex max-w-sm flex-col items-center px-5 py-20 text-center">
        <AlertCircle size={32} className="text-jade" />
        <h2 className="mt-5 text-3xl text-jade">We couldn't analyze that</h2>
        <p className="mt-3 text-sm leading-relaxed text-ink-soft">{error}</p>
        <div className="mt-8 flex w-full gap-3">
          <Button variant="ghost" icon={null} full onClick={() => go("camera")}>Retake</Button>
          <Button icon={null} full onClick={() => setAttempt((a) => a + 1)}>Try again</Button>
        </div>
      </div>
    );
  }

  const pct = Math.round((Math.min(stage, ANALYSIS_STAGES.length) / ANALYSIS_STAGES.length) * 100);
  return (
    <div className="yw-enter mx-auto flex max-w-sm flex-col items-center px-5 py-20 text-center">
      <div className="relative h-40 w-32 overflow-hidden rounded-[2rem] bg-mist">
        {photo && <img src={photo} alt="" className="h-full w-full object-cover" />}
        <div className="absolute inset-0 bg-jade/10" />
        <div className="absolute inset-x-3 rounded-full bg-jade-soft" style={{ height: 2, animation: "yw-scan 2.2s ease-in-out infinite" }} />
      </div>
      <div className="mt-5"><ScoreRing value={pct} size={64} stroke={5} label="Progress" /></div>
      <h2 className="mt-6 text-3xl text-jade">Analyzing your skin</h2>
      <ul className="mt-7 w-full space-y-3 text-left">
        {ANALYSIS_STAGES.map((s, i) => (
          <li key={s} className={`flex items-center gap-3 text-sm ${i <= stage ? "text-ink" : "text-ink-soft/50"}`}>
            <span className={`flex h-5 w-5 items-center justify-center rounded-full ${i < stage ? "bg-jade" : i === stage ? "bg-jade-soft" : "bg-mist"}`}>
              {i < stage && <Check size={12} className="text-white" />}
            </span>
            {s}
          </li>
        ))}
      </ul>
    </div>
  );
}
