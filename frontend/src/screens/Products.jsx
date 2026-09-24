import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button, Eyebrow } from "../components/Button";
import { ProductCard } from "../components/ProductCard";
import { motion } from "framer-motion";

const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.1 } }
};

const itemVariants = {
  hidden: { opacity: 0, y: 15 },
  show: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 300, damping: 24 } }
};

export default function Products({ go, analysis }) {
  const items = analysis?.recommendations;

  return (
    <div className="flex-1 w-full max-w-6xl mx-auto px-4 sm:px-8 py-8 sm:py-12">
      <div className="flex flex-col items-center text-center mb-12">
        <Eyebrow className="mb-3">Step 9 &middot; Products</Eyebrow>
        <h2 className="font-display text-3xl sm:text-5xl text-[#004647] mb-4">Recommended for you</h2>
        <p className="text-sm text-ink-soft max-w-md">Curated specifically for your skin profile and focus areas.</p>
      </div>

      {!items && (
        <div className="bg-[#fcf4f3] border border-[#f0dedd] p-8 text-center rounded-card mb-12 max-w-2xl mx-auto">
          <p className="text-sm text-[#8a2e2e]">We couldn't load recommendations right now. Please try the scan again.</p>
        </div>
      )}

      {items?.length === 0 && (
        <div className="bg-mist p-8 text-center rounded-card mb-12 max-w-2xl mx-auto border border-hairline">
          <p className="text-sm text-ink-soft italic">No products were a strong match for this scan. Your skin looks well balanced.</p>
        </div>
      )}

      {items?.length > 0 && (
        <motion.div 
          variants={containerVariants}
          initial="hidden"
          animate="show"
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 sm:gap-6 lg:gap-8 mb-16"
        >
          {items.map((p) => (
            <motion.div key={p.id} variants={itemVariants}>
              <ProductCard product={p} reason={p.reason} />
            </motion.div>
          ))}
        </motion.div>
      )}

      <div className="flex flex-col-reverse sm:flex-row items-center justify-between gap-4 mt-12 pt-8 border-t border-hairline">
        <Button variant="secondary" iconLeft={ChevronLeft} icon={null} onClick={() => go("recommendations")} className="w-full sm:w-auto">
          Back
        </Button>
        <Button onClick={() => go("routine")} icon={ChevronRight} className="w-full sm:w-auto">
          Build My Routine
        </Button>
      </div>
    </div>
  );
}
