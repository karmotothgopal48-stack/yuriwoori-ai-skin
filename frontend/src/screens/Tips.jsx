import { Sun, Glasses, ScanFace, Camera } from "lucide-react";
import { Button, Eyebrow } from "../components/Button";
import { IMAGES } from "../theme/brand";
import { motion } from "framer-motion";

const TIPS = [
  { icon: Sun, t: "Good lighting", b: "Face a window or soft, even light. Avoid harsh shadows." },
  { icon: Glasses, t: "Bare face", b: "Remove glasses and heavy makeup if possible for best results." },
  { icon: ScanFace, t: "Keep face inside frame", b: "Ensure your entire face is visible within the oval guide." },
  { icon: Camera, t: "Look directly at camera", b: "Keep your head straight and maintain a neutral expression." },
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

export default function Tips({ go }) {
  return (
    <div className="flex-1 w-full max-w-4xl mx-auto px-4 sm:px-8 py-8 sm:py-12 flex flex-col">
      <div className="flex flex-col items-center text-center mb-10">
        <Eyebrow className="mb-3">Step 2 &middot; Tips</Eyebrow>
        <h2 className="font-display text-3xl sm:text-4xl text-[#004647] mb-6">How to get the best scan</h2>
        
        <div className="relative w-32 h-32 rounded-full p-1 bg-gradient-to-tr from-jade-soft to-mist shadow-soft mb-4">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,var(--color-jade-soft)_0%,transparent_70%)] opacity-30 blur-xl" />
          <img 
            src={IMAGES.analysisFace} 
            alt="Face centered" 
            className="w-full h-full object-cover rounded-full border-[3px] border-white relative z-10"
          />
        </div>
      </div>

      <motion.div 
        variants={containerVariants}
        initial="hidden"
        animate="show"
        className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6 mb-12 flex-1"
      >
        {TIPS.map((t, i) => (
          <motion.div 
            key={i} 
            variants={itemVariants}
            className="flex items-start gap-4 bg-white rounded-card p-5 sm:p-6 shadow-soft border border-hairline"
          >
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-mist/50">
              <t.icon size={22} className="text-jade" strokeWidth={1.5} />
            </div>
            <div>
              <h3 className="font-semibold text-jade mb-1 text-[15px]">{t.t}</h3>
              <p className="text-[13px] leading-relaxed text-ink-soft">{t.b}</p>
            </div>
          </motion.div>
        ))}
      </motion.div>

      <div className="flex flex-col-reverse sm:flex-row items-center justify-center gap-4 mt-auto">
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
