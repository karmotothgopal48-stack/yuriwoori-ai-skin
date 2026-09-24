import { useEffect, useRef, useState } from "react";
import { AlertCircle, RotateCcw, RefreshCcw } from "lucide-react";
import { Button } from "../components/Button";
import { analyzeSkin } from "../services/skinAnalysis";
import { motion, AnimatePresence } from "framer-motion";

const STATUS_TEXTS = [
  "Analyzing your skin...",
  "Checking skin characteristics...",
  "Preparing your personalized insights..."
];

export default function Processing({ go, photo, setAnalysis }) {
  const [statusIndex, setStatusIndex] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const started = useRef(-1); 

  useEffect(() => {
    if (started.current === attempt || !photo) return;
    started.current = attempt;
    setError(""); setResult(null); setStatusIndex(0);
    
    // Begin API call
    analyzeSkin(photo)
      .then((res) => {
        setResult(res);
        setAnalysis(res);
        setTimeout(() => go("results"), 1500); // Small delay to let animations finish gracefully
      })
      .catch((e) => setError(e.message || "Something went wrong analyzing your photo."));
  }, [photo, attempt, go, setAnalysis]);

  useEffect(() => {
    if (error || result) return;
    const interval = setInterval(() => {
      setStatusIndex((prev) => (prev + 1) % STATUS_TEXTS.length);
    }, 2500);
    return () => clearInterval(interval);
  }, [error, result]);

  if (error) {
    return (
      <div className="flex-1 w-full max-w-sm mx-auto flex flex-col items-center justify-center px-4 py-8 text-center">
        <div className="w-16 h-16 bg-[#fcf4f3] rounded-full flex items-center justify-center border border-[#f0dedd] mb-6 shadow-sm">
          <AlertCircle size={28} className="text-[#8a2e2e]" />
        </div>
        <h2 className="font-display text-3xl text-ink mb-3">Analysis failed</h2>
        <p className="text-sm leading-relaxed text-ink-soft mb-8">{error}</p>
        <div className="flex flex-col w-full gap-3">
          <Button full onClick={() => setAttempt((a) => a + 1)} icon={RefreshCcw}>Try again</Button>
          <Button variant="secondary" iconLeft={RotateCcw} icon={null} full onClick={() => go("camera")}>Retake photo</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 w-full max-w-sm mx-auto flex flex-col items-center justify-center px-4 py-8 text-center">
      
      {/* Scanning Image Container */}
      <div className="relative w-48 aspect-[3/4] overflow-hidden rounded-hero bg-mist shadow-float border border-hairline mb-10">
        {photo && <img src={photo} alt="" className="w-full h-full object-cover -scale-x-100" />}
        
        {/* Soft green overlay */}
        <div className="absolute inset-0 bg-jade/10 mix-blend-multiply" />
        
        {/* Grid/Mesh Shimmer */}
        <div 
          className="absolute inset-0 opacity-20 pointer-events-none mix-blend-overlay"
          style={{ 
            backgroundImage: "linear-gradient(rgba(255,255,255,.5) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.5) 1px, transparent 1px)",
            backgroundSize: "20px 20px" 
          }} 
        />

        {/* Sweeping scan line */}
        <motion.div 
          className="absolute left-0 right-0 h-[2px] bg-jade-soft shadow-[0_0_15px_rgba(157,212,202,0.8)] z-10"
          animate={{ top: ["5%", "95%", "5%"] }}
          transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
        />
        
        {/* Glowing corner brackets */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none z-20">
          <motion.g 
            stroke="rgba(255,255,255,0.7)" 
            strokeWidth="3" 
            fill="none" 
            strokeLinecap="round"
            animate={{ opacity: [0.3, 0.8, 0.3] }}
            transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
          >
            <path d="M 20 40 L 20 20 L 40 20" />
            <path d="M 172 20 L 172 40 L 152 20" transform="translate(192, 0) scale(-1, 1)" />
            <path d="M 20 216 L 20 236 L 40 236" transform="translate(0, 256) scale(1, -1)" />
            <path d="M 172 236 L 172 216 L 152 236" transform="translate(192, 256) scale(-1, -1)" />
          </motion.g>
        </svg>
      </div>

      {/* Indeterminate Loader Ring */}
      <div className="relative w-12 h-12 mb-6">
        <svg className="animate-spin w-full h-full" viewBox="0 0 50 50">
          <circle className="stroke-mist" cx="25" cy="25" r="20" fill="none" strokeWidth="4" />
          <circle className="stroke-jade" cx="25" cy="25" r="20" fill="none" strokeWidth="4" strokeLinecap="round" strokeDasharray="90 150" />
        </svg>
      </div>

      {/* Rotating Status Text */}
      <div className="h-8 relative w-full overflow-hidden">
        <AnimatePresence mode="wait">
          <motion.p
            key={statusIndex}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.3 }}
            className="absolute inset-0 flex justify-center text-sm font-medium text-jade"
          >
            {result ? "Complete!" : STATUS_TEXTS[statusIndex]}
          </motion.p>
        </AnimatePresence>
      </div>

    </div>
  );
}
