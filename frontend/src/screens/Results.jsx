import { Info, Droplets, Target, Wind, Activity, Maximize, AlertCircle } from "lucide-react";
import { Button, Eyebrow } from "../components/Button";
import { ScoreRing } from "../components/ScoreRing";
import { motion } from "framer-motion";

const METRIC_ICONS = {
  hydration: Droplets,
  oiliness: Target,
  texture: Wind,
  redness: Activity,
  pigmentation: Target,
  pores: Maximize,
  acne: AlertCircle,
};

const STATUS_STYLE = {
  strength: "bg-jade/10 text-[#004647] border border-jade/20",
  balanced: "bg-mist text-ink-soft border border-mist",
  focus: "bg-[#fcf4f3] text-[#8a2e2e] border border-[#f0dedd]",
};

const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.1 } }
};

const itemVariants = {
  hidden: { opacity: 0, y: 15 },
  show: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 300, damping: 24 } }
};

export default function Results({ go, photo, analysis }) {
  const concerns = analysis?.concerns ?? [];
  
  if (!analysis) return null;

  return (
    <div className="flex-1 w-full max-w-5xl mx-auto px-4 sm:px-8 py-8 sm:py-12">
      <Eyebrow className="mb-3 text-center sm:text-left">Step 6 &middot; Analysis</Eyebrow>
      <h2 className="font-display text-3xl sm:text-4xl text-[#004647] mb-8 text-center sm:text-left">Your Skin Insights</h2>

      {/* Top Overview Card */}
      <motion.div 
        initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }}
        className="flex flex-col sm:flex-row items-center sm:items-start gap-6 bg-white p-6 sm:p-8 rounded-card shadow-soft border border-hairline mb-10"
      >
        <div className="w-24 h-24 sm:w-32 sm:h-32 shrink-0 rounded-[1.5rem] overflow-hidden bg-mist">
          {photo && <img src={photo} alt="Your scan" className="w-full h-full object-cover -scale-x-100" />}
        </div>
        <div className="flex-1 text-center sm:text-left flex flex-col justify-center">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-jade mb-2">Overall Profile</p>
          <h3 className="font-display text-2xl mb-3 text-ink">{analysis.profile.skinType} Skin</h3>
          <p className="text-sm leading-relaxed text-ink-soft">{analysis.profile.summary}</p>
        </div>
      </motion.div>

      {/* Metrics Grid */}
      {concerns.length > 0 ? (
        <motion.div 
          variants={containerVariants}
          initial="hidden"
          animate="show"
          className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-6 mb-12"
        >
          {concerns.map((c) => {
            const Icon = METRIC_ICONS[c.id] || Target;
            return (
              <motion.div key={c.id} variants={itemVariants} className="flex gap-4 sm:gap-5 bg-white p-5 rounded-[20px] shadow-sm border border-hairline">
                <div className="shrink-0 flex items-center justify-center">
                  <ScoreRing value={c.score} size={64} stroke={4} label={c.label} />
                </div>
                <div className="flex flex-col justify-center flex-1">
                  <div className="flex items-center justify-between mb-1.5">
                    <h4 className="font-semibold text-[15px] flex items-center gap-2">
                      <Icon size={14} className="text-jade opacity-60" /> {c.label}
                    </h4>
                    <span className={`text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded-pill ${STATUS_STYLE[c.status]}`}>
                      {c.status}
                    </span>
                  </div>
                  <p className="text-[13px] leading-relaxed text-ink-soft">{c.note}</p>
                </div>
              </motion.div>
            );
          })}
        </motion.div>
      ) : (
        <div className="bg-mist/50 p-8 rounded-card text-center text-ink-soft mb-12">
          Detailed metrics are currently unavailable.
        </div>
      )}

      {/* Mandatory Disclaimer */}
      <div className="flex items-start sm:items-center justify-center gap-3 bg-cream px-5 py-4 rounded-xl border border-hairline/50 mb-10">
        <Info size={16} className="text-jade shrink-0 mt-0.5 sm:mt-0" />
        <p className="text-xs font-medium text-ink-soft/80">
          No medical diagnosis. This analysis is for skincare guidance only.
        </p>
      </div>

      <div className="flex justify-center sm:justify-end">
        <Button onClick={() => go("profile")} className="w-full sm:w-auto">
          Continue to Profile
        </Button>
      </div>
    </div>
  );
}
