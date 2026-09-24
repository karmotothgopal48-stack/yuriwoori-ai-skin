import { Sun, Moon, AlertTriangle, ChevronLeft, MessageCircle } from "lucide-react";
import { Button, Eyebrow } from "../components/Button";
import { ProductImage } from "../components/ProductCard";
import { motion } from "framer-motion";

const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.1 } }
};

const itemVariants = {
  hidden: { opacity: 0, y: 15 },
  show: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 300, damping: 24 } }
};

function RoutineBlock({ title, icon: Icon, steps, isMorning }) {
  return (
    <motion.div variants={itemVariants} className="flex flex-col rounded-[24px] bg-white border border-hairline shadow-soft overflow-hidden">
      {/* Header */}
      <div className={`px-6 sm:px-8 py-5 border-b border-hairline flex items-center gap-3 ${isMorning ? "bg-mist/30" : "bg-[#0a3839]/5"}`}>
        <div className={`w-10 h-10 rounded-full flex items-center justify-center shadow-sm ${isMorning ? "bg-white text-jade" : "bg-[#0a3839] text-[#9DD4CA]"}`}>
          <Icon size={20} strokeWidth={1.5} />
        </div>
        <h3 className="font-display text-2xl text-ink">{title}</h3>
      </div>
      
      {/* Steps */}
      <div className="p-6 sm:p-8 flex-1">
        {steps.length === 0 ? (
          <p className="text-sm text-ink-soft italic">No steps for this routine.</p>
        ) : (
          <ol className="flex flex-col gap-6 relative">
            {/* Connecting line */}
            <div className="absolute left-4 top-4 bottom-4 w-px bg-jade-line/50 -z-10" />
            
            {steps.map((s, i) => (
              <li key={`${s.id}-${i}`} className="flex items-start gap-5">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-jade text-xs font-bold text-white shadow-sm ring-4 ring-white">
                  {i + 1}
                </span>
                
                <div className="flex items-start gap-4 flex-1 p-4 rounded-xl bg-mist/30 border border-mist hover:bg-white hover:shadow-soft transition-all group">
                  <div className="h-16 w-16 shrink-0 rounded-[14px] overflow-hidden bg-white p-1 border border-hairline">
                    <ProductImage product={s} className="h-full w-full object-cover rounded-[10px] group-hover:scale-105 transition-transform duration-500" />
                  </div>
                  <div className="min-w-0 flex-1">
                    {s.step && <p className="text-[11px] font-bold uppercase tracking-widest text-jade mb-1">{s.step}</p>}
                    <p className="text-sm font-semibold text-ink truncate mb-1">{s.name}</p>
                    <p className="text-xs text-ink-soft leading-relaxed line-clamp-2">{s.reason}</p>
                  </div>
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>
    </motion.div>
  );
}

export default function Routine({ go, analysis }) {
  const routine = analysis?.routine;
  const flags = analysis?.compatibility ?? [];
  
  return (
    <div className="flex-1 w-full max-w-6xl mx-auto px-4 sm:px-8 py-8 sm:py-12">
      <div className="flex flex-col items-center text-center mb-12">
        <Eyebrow className="mb-3">Step 10 &middot; Routine</Eyebrow>
        <h2 className="font-display text-3xl sm:text-5xl text-[#004647] mb-4">Your morning and evening ritual</h2>
        {!routine && <p className="text-sm text-ink-soft max-w-md">We couldn't build a routine right now. Please try the scan again.</p>}
      </div>

      {routine && (
        <motion.div 
          variants={containerVariants}
          initial="hidden"
          animate="show"
          className="grid grid-cols-1 lg:grid-cols-2 gap-6 sm:gap-8 mb-12"
        >
          <RoutineBlock title="Morning" icon={Sun} steps={routine.AM} isMorning={true} />
          <RoutineBlock title="Evening" icon={Moon} steps={routine.PM} isMorning={false} />
        </motion.div>
      )}

      {flags.length > 0 && (
        <motion.div 
          initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }}
          className="rounded-[24px] bg-[#fcf4f3] p-6 sm:p-8 border border-[#f0dedd] mb-12"
        >
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-full bg-white flex items-center justify-center text-[#8a2e2e] shadow-sm">
              <AlertTriangle size={20} />
            </div>
            <h3 className="font-display text-2xl text-[#8a2e2e]">Using these together</h3>
          </div>
          <ul className="flex flex-col gap-4">
            {flags.map((f, i) => (
              <li key={i} className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 bg-white/60 p-4 rounded-xl">
                <span className="font-bold text-sm text-[#8a2e2e] shrink-0">{f.a} <span className="text-ink-soft/50 font-normal mx-1">+</span> {f.b}</span>
                <span className="hidden sm:block text-mist w-px h-4" />
                <span className="text-sm text-ink-soft leading-relaxed">{f.text}</span>
              </li>
            ))}
          </ul>
        </motion.div>
      )}

      <div className="flex flex-col-reverse sm:flex-row items-center justify-between gap-4 mt-12 pt-8 border-t border-hairline">
        <Button variant="secondary" iconLeft={ChevronLeft} icon={null} onClick={() => go("products")} className="w-full sm:w-auto">
          Back to Products
        </Button>
        <Button onClick={() => go("assistant")} icon={MessageCircle} className="w-full sm:w-auto">
          Ask Yuri About My Routine
        </Button>
      </div>
    </div>
  );
}
