import { CheckCircle2, ChevronRight, Target } from "lucide-react";
import { Button, Eyebrow } from "../components/Button";
import { ScoreRing } from "../components/ScoreRing";
import { motion } from "framer-motion";

const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.1 } }
};

const itemVariants = {
  hidden: { opacity: 0, y: 15 },
  show: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 300, damping: 24 } }
};

export default function Profile({ go, photo, analysis }) {
  const { concerns = [], profile } = analysis ?? {};
  
  if (!profile) return null;
  
  const overall = profile.overall ?? Math.round(concerns.reduce((a, c) => a + c.score, 0) / (concerns.length || 1));
  const byId = Object.fromEntries(concerns.map((c) => [c.id, c]));
  const strengths = concerns.filter((c) => c.status === "strength");
  const focusAreas = profile.focus.map(f => byId[f]).filter(Boolean);

  return (
    <div className="flex-1 w-full max-w-5xl mx-auto px-4 sm:px-8 py-8 sm:py-12">
      <Eyebrow className="mb-3 text-center sm:text-left">Step 7 &middot; Summary</Eyebrow>
      <h2 className="font-display text-3xl sm:text-4xl text-[#004647] mb-8 text-center sm:text-left">Your Skin Profile</h2>

      <motion.div 
        variants={containerVariants}
        initial="hidden"
        animate="show"
        className="grid grid-cols-1 lg:grid-cols-[1.5fr_1fr] gap-6 mb-12"
      >
        {/* Banner Card */}
        <motion.div variants={itemVariants} className="flex flex-col sm:flex-row items-center sm:items-stretch overflow-hidden rounded-[24px] bg-[#004647] text-white shadow-float relative">
          
          {/* Subtle Background Pattern */}
          <div className="absolute inset-0 opacity-10 mix-blend-overlay pointer-events-none" 
            style={{ backgroundImage: "radial-gradient(circle at 100% 100%, white 0%, transparent 60%)" }} 
          />
          
          <div className="w-full sm:w-1/3 aspect-square sm:aspect-auto relative bg-[#0a3839]">
            {photo && <img src={photo} alt="" className="absolute inset-0 w-full h-full object-cover -scale-x-100 opacity-90" />}
            <div className="absolute inset-0 bg-gradient-to-t sm:bg-gradient-to-r from-[#004647] via-transparent to-transparent opacity-80" />
          </div>
          
          <div className="flex-1 p-8 sm:p-10 flex flex-col justify-center relative z-10 text-center sm:text-left">
            <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-jade-soft/80 mb-2">Primary Skin Type</p>
            <p className="font-display text-4xl sm:text-5xl mb-4">{profile.skinType}</p>
            <p className="text-sm leading-relaxed text-white/80 max-w-md">{profile.summary}</p>
          </div>
        </motion.div>

        {/* Overall Score */}
        <motion.div variants={itemVariants} className="flex flex-row items-center justify-center gap-6 rounded-[24px] bg-white p-8 border border-hairline shadow-soft">
          <ScoreRing value={overall} size={100} stroke={6} label="Overall Score" />
          <div className="flex flex-col">
            <h3 className="font-semibold text-lg text-ink mb-1">Overall Balance</h3>
            <p className="text-xs text-ink-soft">Based on {concerns.length} metrics</p>
          </div>
        </motion.div>

        {/* Focus Areas */}
        <motion.div variants={itemVariants} className="rounded-[24px] bg-[#fcf4f3] p-8 border border-[#f0dedd]">
          <div className="flex items-center gap-2 mb-6">
            <Target size={20} className="text-[#8a2e2e]" />
            <h3 className="font-display text-2xl text-[#8a2e2e]">Focus Areas</h3>
          </div>
          <ol className="flex flex-col gap-4">
            {focusAreas.length > 0 ? focusAreas.map((f, i) => (
              <li key={f.id} className="flex items-start gap-4 bg-white/60 rounded-xl p-4">
                <span className="flex shrink-0 h-7 w-7 items-center justify-center rounded-full bg-white text-xs font-bold text-[#8a2e2e] shadow-sm">
                  {i + 1}
                </span>
                <div>
                  <p className="font-semibold text-ink text-sm mb-1">{f.label}</p>
                  <p className="text-xs text-ink-soft leading-relaxed">{f.note}</p>
                </div>
              </li>
            )) : (
              <li className="text-sm text-ink-soft italic">No major focus areas detected.</li>
            )}
          </ol>
        </motion.div>

        {/* Strengths */}
        <motion.div variants={itemVariants} className="rounded-[24px] bg-jade/5 p-8 border border-jade/10">
          <div className="flex items-center gap-2 mb-6">
            <CheckCircle2 size={20} className="text-jade" />
            <h3 className="font-display text-2xl text-[#004647]">Strengths</h3>
          </div>
          <ul className="flex flex-col gap-3">
            {strengths.length > 0 ? strengths.map((s) => (
              <li key={s.id} className="flex items-center justify-between bg-white rounded-xl p-4 shadow-sm border border-white/50">
                <span className="font-medium text-sm text-ink">{s.label}</span>
                <span className="text-xs font-bold bg-jade-soft/20 text-jade px-2.5 py-1 rounded-pill">{s.score}/100</span>
              </li>
            )) : (
              <li className="text-sm text-ink-soft italic">Your skin is balanced.</li>
            )}
          </ul>
        </motion.div>
      </motion.div>

      <div className="flex justify-center sm:justify-end">
        <Button onClick={() => go("recommendations")} className="w-full sm:w-auto" icon={ChevronRight}>
          See Recommendations
        </Button>
      </div>
    </div>
  );
}
