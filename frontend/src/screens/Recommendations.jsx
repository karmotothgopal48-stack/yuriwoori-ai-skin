import { ChevronLeft, ChevronRight, Sparkles } from "lucide-react";
import { Button, Eyebrow } from "../components/Button";
import { ProductCard } from "../components/ProductCard";
import { FOCUS_GUIDANCE } from "../data/mock";
import { motion } from "framer-motion";

const PER_AREA = 3;

const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.15 } }
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 300, damping: 25 } }
};

export default function Recommendations({ go, analysis }) {
  const focus = analysis?.profile?.focus ?? [];
  const label = Object.fromEntries((analysis?.concerns ?? []).map((c) => [c.id, c.label]));
  const recs = analysis?.recommendations;

  // Each recommended product is shown once, under the first focus area it helps.
  const shown = new Set();
  const byArea = Object.fromEntries(focus.map((f) => [f, (recs ?? [])
    .filter((p) => p.areas.includes(f) && !shown.has(p.id))
    .slice(0, PER_AREA)
    .map((p) => { shown.add(p.id); return p; })]));

  return (
    <div className="flex-1 w-full max-w-6xl mx-auto px-4 sm:px-8 py-8 sm:py-12">
      <div className="flex flex-col items-center text-center mb-12">
        <Eyebrow className="mb-3">Step 8 &middot; Recommendations</Eyebrow>
        <h2 className="font-display text-3xl sm:text-5xl text-[#004647] mb-4">What your skin needs most</h2>
        {!recs && <p className="text-sm text-ink-soft max-w-md">We couldn't load product suggestions right now, but your focus areas are below.</p>}
      </div>

      <motion.div 
        variants={containerVariants}
        initial="hidden"
        animate="show"
        className="space-y-12 sm:space-y-16 mb-16"
      >
        {focus.map((f, i) => (
          <motion.section key={f} variants={itemVariants} className="relative">
            
            {/* Elegant Header for Area */}
            <div className="flex flex-col sm:flex-row gap-5 sm:gap-8 items-start mb-8 pb-6 border-b border-hairline relative">
              {/* Decorative Number */}
              <div className="hidden sm:flex absolute -left-16 top-0 w-12 h-12 items-center justify-center rounded-full bg-jade/5 text-jade-soft font-display text-3xl border border-jade/10">
                {i + 1}
              </div>
              
              <div className="flex sm:hidden h-10 w-10 shrink-0 items-center justify-center rounded-full bg-jade/10 text-jade font-display text-xl">
                {i + 1}
              </div>

              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <Sparkles size={14} className="text-jade" />
                  <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-jade">{label[f]}</p>
                </div>
                <h3 className="font-display text-2xl sm:text-3xl text-ink mb-3">{FOCUS_GUIDANCE[f]?.title}</h3>
                <p className="text-sm sm:text-base leading-relaxed text-ink-soft max-w-3xl">{FOCUS_GUIDANCE[f]?.body}</p>
              </div>
            </div>

            {/* Product Grid */}
            {recs && byArea[f].length > 0 && (
              <div className="grid grid-cols-1 gap-4 sm:gap-6 sm:grid-cols-2 lg:grid-cols-3">
                {byArea[f].map((p, idx) => (
                  <motion.div 
                    key={p.id}
                    initial={{ opacity: 0, y: 15 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 * idx, duration: 0.5 }}
                  >
                    <ProductCard product={p} reason={p.reason} />
                  </motion.div>
                ))}
              </div>
            )}
            
            {recs && byArea[f].length === 0 && (
              <div className="flex items-center justify-center p-8 rounded-card bg-cream border border-mist text-ink-soft text-sm italic">
                No specific products matched this area in your scan.
              </div>
            )}
          </motion.section>
        ))}
      </motion.div>

      <div className="flex flex-col-reverse sm:flex-row items-center justify-between gap-4 mt-12 pt-8 border-t border-hairline">
        <Button variant="secondary" iconLeft={ChevronLeft} icon={null} onClick={() => go("profile")} className="w-full sm:w-auto">
          Back to Profile
        </Button>
        <Button onClick={() => go("products")} icon={ChevronRight} className="w-full sm:w-auto">
          View All Products
        </Button>
      </div>
    </div>
  );
}
