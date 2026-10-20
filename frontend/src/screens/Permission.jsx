import { useState } from "react";
import { Camera, AlertCircle, ShieldCheck } from "lucide-react";
import { motion } from "framer-motion";
import { Button, Eyebrow } from "../components/Button";
import { AnalysisPortrait } from "../components/AnalysisPortrait";
import { PORTRAITS } from "../theme/brand";
import { describeCameraError, openCamera, stopStream } from "../services/camera";

function Portrait({ className = "" }) {
  return (
    <figure className={`relative w-full ${className}`}>
      <div aria-hidden="true" className="absolute -inset-2 sm:-inset-3 rounded-[1.75rem] sm:rounded-[2.25rem] border border-sage-light/70" />
      <AnalysisPortrait portrait={PORTRAITS.permission} priority>
        <span className="absolute bottom-4 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-pill bg-white/90 backdrop-blur-md px-4 py-2 shadow-soft border border-white text-[10px] font-semibold uppercase tracking-[0.16em] text-jade">
          AI Skin Analysis
        </span>
      </AnalysisPortrait>
    </figure>
  );
}

export default function Permission({ go }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const allow = async () => {
    setBusy(true);
    setError("");
    try {
      stopStream(await openCamera(true)); // only asks for permission; the Camera step opens it again
      go("tips");
    } catch (e) {
      console.warn("Camera could not be opened:", e);
      setError(describeCameraError(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="relative flex-1 w-full">
      {/* One faint sage wash behind the portrait */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-y-0 left-1/2 w-screen -translate-x-1/2 overflow-hidden">
        <div className="absolute left-[-8%] top-1/2 h-[34rem] w-[34rem] -translate-y-1/2 rounded-full bg-mist blur-3xl opacity-80" />
      </div>

      <div className="relative mx-auto grid max-w-5xl grid-cols-1 items-center gap-6 px-5 pt-5 pb-8 sm:px-8 md:grid-cols-[0.85fr_1fr] md:gap-14 md:py-8">
        {/* Desktop: portrait in the left column */}
        <div className="hidden md:flex justify-center">
          <Portrait className="max-w-[340px] lg:max-w-[380px]" />
        </div>

        <div className="w-full max-w-md mx-auto md:mx-0">
          <Eyebrow className="text-jade tracking-[0.14em]">Permission</Eyebrow>
          <h1 className="mt-2 font-display text-[32px] sm:text-[40px] leading-[1.1] text-jade-deep">
            Let&apos;s understand <br className="hidden md:block" />your skin
          </h1>
          <p className="mt-3 text-[15px] leading-relaxed text-ink-soft">
            We need access to your camera to capture a clear photo of your face. The photo is measured with image analysis to build your skin profile.
          </p>

          {/* Mobile: portrait after the explanation */}
          <div className="md:hidden mt-6 flex justify-center">
            <Portrait className="max-w-[205px]" />
          </div>

          {error && (
            <motion.p
              initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} role="alert"
              className="mt-5 flex items-start gap-2.5 rounded-card bg-danger-soft p-4 text-sm text-danger border border-danger-line"
            >
              <AlertCircle size={18} className="shrink-0 mt-0.5" />
              <span>{error}</span>
            </motion.p>
          )}

          <div className="mt-6 flex items-center gap-4">
            <span aria-hidden="true" className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-mist border border-jade-line">
              <Camera size={20} className="text-jade" strokeWidth={1.5} />
            </span>
            <Button full onClick={allow} loading={busy} className="flex-1">Allow Camera</Button>
          </div>

          <div className="mt-2 flex justify-center pl-16">
            <button type="button" onClick={() => go("start")}
              className="min-h-[44px] px-3 text-sm font-medium text-ink-soft underline-offset-4 hover:text-jade hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-jade rounded-sm">
              Maybe later
            </button>
          </div>

          {/* Verified behaviour: the photo is sent to the server, analysed in memory and discarded (never written to disk,
              the database or logs: backend endpoints/scans.py); the scan results are saved, linked to the name + email entered */}
          <p className="mt-3 flex items-start gap-2 text-xs leading-relaxed text-ink-soft">
            <ShieldCheck size={15} className="text-jade shrink-0 mt-0.5" strokeWidth={1.5} />
            <span>Your photo is sent to the YuriWoori server for analysis and then discarded — it is never saved. Your scan results are saved together with the name and email you entered.</span>
          </p>

        </div>
      </div>
    </div>
  );
}
