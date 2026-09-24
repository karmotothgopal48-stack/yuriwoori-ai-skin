import { RotateCcw, Check, Sparkles } from "lucide-react";
import { Button, Eyebrow } from "../components/Button";
import { motion } from "framer-motion";

export default function Review({ go, photo }) {
  return (
    <div className="flex-1 w-full max-w-lg mx-auto px-4 sm:px-8 py-8 sm:py-12 flex flex-col items-center">
      
      <Eyebrow className="mb-3">Step 4 &middot; Review</Eyebrow>
      <h2 className="font-display text-3xl sm:text-4xl text-[#004647] mb-8 text-center">Review your scan</h2>
      
      {/* Polaroid style frame */}
      <motion.div 
        initial={{ opacity: 0, scale: 0.95, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        className="w-full max-w-[320px] aspect-[3/4] bg-white p-3 pb-12 rounded-[24px] shadow-float border border-hairline mb-8 relative"
      >
        <div className="w-full h-full rounded-[16px] overflow-hidden bg-mist">
          {photo ? (
            <img src={photo} alt="Captured photo" className="w-full h-full object-cover -scale-x-100" />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-ink-soft text-sm">No photo found</div>
          )}
        </div>
        
        {/* Subtle decorative tape or text on polaroid */}
        <div className="absolute bottom-4 inset-x-0 text-center text-[10px] uppercase tracking-widest text-ink-soft/50 font-semibold">
          YuriWoori Scan
        </div>
      </motion.div>

      {/* Checklist */}
      <div className="w-full max-w-[320px] bg-white/50 backdrop-blur-sm rounded-2xl p-4 shadow-sm border border-hairline mb-10">
        <p className="text-[11px] font-semibold uppercase tracking-widest text-ink-soft mb-3 text-center">Check for clarity</p>
        <ul className="flex flex-col gap-2">
          {["Face is clear and visible", "Lighting is soft and even", "No strong shadows"].map((text, i) => (
            <li key={i} className="flex items-center gap-2.5 text-xs text-ink-soft">
              <Check size={14} className="text-jade" strokeWidth={2} />
              {text}
            </li>
          ))}
        </ul>
      </div>

      <div className="flex flex-col sm:flex-row w-full max-w-[320px] gap-3 mt-auto">
        <Button variant="secondary" iconLeft={RotateCcw} icon={null} full onClick={() => go("camera")}>
          Retake
        </Button>
        <Button full icon={Sparkles} onClick={() => go("processing")} disabled={!photo}>
          Analyze My Skin
        </Button>
      </div>
      
    </div>
  );
}
