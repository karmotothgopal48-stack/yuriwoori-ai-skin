import { useState } from "react";
import { Camera, AlertCircle, Sun, User, Move, ShieldCheck } from "lucide-react";
import { Button, Eyebrow } from "../components/Button";
import { IMAGES } from "../theme/brand";
import { motion } from "framer-motion";

const BEFORE_SCAN = [
  { icon: Sun, text: "Good lighting" },
  { icon: User, text: "Bare face" },
  { icon: Move, text: "Steady hold" },
];

export default function Permission({ go }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const allow = async () => {
    setBusy(true); 
    setError("");
    try {
      const s = await navigator.mediaDevices.getUserMedia({ video: true });
      s.getTracks().forEach((t) => t.stop());
      go("tips");
    } catch (e) {
      setError(e.name === "NotAllowedError"
        ? "Camera access was blocked. Please allow it in your browser settings to continue."
        : "No camera could be opened on this device.");
    } finally { 
      setBusy(false); 
    }
  };

  return (
    <div className="flex-1 flex flex-col md:flex-row items-center w-full px-4 sm:px-8 py-6 sm:py-12 gap-8 md:gap-16">
      
      {/* Left: Visual (50%) */}
      <div className="w-full md:w-1/2 flex justify-center items-center relative min-h-[35vh] md:min-h-0 h-full">
        {/* Soft radial glow */}
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,var(--color-jade-soft)_0%,transparent_60%)] opacity-20 blur-3xl" />
        
        <motion.div 
          className="relative w-full max-w-sm overflow-hidden rounded-hero shadow-float border border-hairline bg-white/50"
          animate={{ y: [-4, 4, -4], scale: [0.99, 1, 0.99] }}
          transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
        >
          <img
            src={IMAGES.analysisFace} 
            alt="AI skin analysis"
            className="w-full h-auto object-cover object-top aspect-[4/5] sm:aspect-auto"
          />
          {/* Decorative Chip */}
          <div className="absolute bottom-6 left-1/2 -translate-x-1/2 rounded-pill bg-white/90 backdrop-blur-md px-5 py-2.5 shadow-soft border border-white">
            <p className="text-[10px] font-bold uppercase tracking-widest text-jade">AI Skin Analysis</p>
          </div>
        </motion.div>
      </div>

      {/* Right: Content (50%) */}
      <div className="w-full md:w-1/2 max-w-md mx-auto md:mx-0 flex flex-col justify-center">
        <Eyebrow className="mb-4">Step 1 &middot; Permission</Eyebrow>
        
        <h1 className="font-display text-4xl sm:text-5xl leading-tight mb-4 text-[#004647]">
          Let&apos;s understand your skin
        </h1>
        
        <p className="text-base text-ink-soft mb-8 leading-relaxed">
          We need access to your camera to capture a clear photo of your face. This helps our AI analyze your unique skin profile.
        </p>

        {error && (
          <motion.p 
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-6 flex items-start gap-2.5 rounded-card bg-[#fcf4f3] p-4 text-sm text-[#8a2e2e] border border-[#f0dedd]"
          >
            <AlertCircle size={18} className="shrink-0 mt-0.5" /> 
            <span>{error}</span>
          </motion.p>
        )}

        <div className="flex items-center gap-6 mb-8">
          <div className="relative flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-jade/10">
            <div className="absolute inset-0 rounded-full border-2 border-jade/30 animate-[pulse-ring_2.5s_cubic-bezier(0.215,0.61,0.355,1)_infinite]" />
            <Camera size={24} className="text-jade" strokeWidth={1.5} />
          </div>
          <Button full onClick={allow} loading={busy} className="flex-1">Allow Camera</Button>
        </div>
        
        <div className="flex justify-center mb-8">
          <Button variant="tertiary" onClick={() => go("start")}>Maybe later</Button>
        </div>

        <p className="flex items-center justify-center gap-2 text-xs font-medium text-ink-soft mb-10">
          <ShieldCheck size={16} className="text-jade shrink-0" strokeWidth={1.5} />
          Your privacy is protected. Photos are never stored.
        </p>

        {/* Before you scan cards */}
        <div className="border-t border-hairline pt-8">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-ink-soft mb-4 text-center sm:text-left">
            Before you scan
          </p>
          <div className="flex justify-between sm:justify-start gap-3 sm:gap-6">
            {BEFORE_SCAN.map(({ icon: Icon, text }) => (
              <div key={text} className="flex flex-col items-center sm:items-start gap-2">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white shadow-soft border border-mist">
                  <Icon size={18} className="text-jade" strokeWidth={1.5} />
                </div>
                <span className="text-[11px] font-semibold text-ink-soft text-center sm:text-left leading-tight w-16 sm:w-auto">{text}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
      
    </div>
  );
}
