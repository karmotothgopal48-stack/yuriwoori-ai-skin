import { X } from "lucide-react";
import { ProvidedLogo } from "./Logo";
import { motion } from "framer-motion";

export function Header({ onHome, step, total = 11 }) {
  // We only show progress if step > 0
  const isFlow = step > 0 && step <= total;
  
  return (
    <header className="sticky top-0 z-40 bg-white/80 backdrop-blur-md border-b border-hairline">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6">
        <button onClick={onHome} aria-label="Exit to home" className="flex items-center shrink-0">
          <ProvidedLogo height={40} />
        </button>
        
        {isFlow && (
          <div className="flex flex-1 items-center justify-end sm:justify-center px-4">
            <span className="text-[11px] uppercase tracking-wider font-semibold text-ink-soft">
              Step {step} of {total}
            </span>
          </div>
        )}

        <div className="flex shrink-0 justify-end w-10 sm:w-24">
          {isFlow && (
            <button 
              onClick={onHome} 
              aria-label="Exit" 
              className="p-2 -mr-2 text-ink-soft hover:text-ink transition-colors rounded-full hover:bg-mist"
            >
              <X size={20} strokeWidth={1.5} />
            </button>
          )}
        </div>
      </div>
      
      {/* 11-segment progress bar */}
      {isFlow && (
        <div className="h-[2px] w-full bg-cream flex gap-[1px]">
          {Array.from({ length: total }).map((_, i) => {
            const isCompleted = i < step;
            const isCurrent = i === step - 1;
            return (
              <div key={i} className="flex-1 bg-mist/50 h-full relative overflow-hidden">
                <motion.div
                  className="absolute inset-0 bg-jade"
                  initial={{ x: "-100%" }}
                  animate={{ x: isCompleted || isCurrent ? "0%" : "-100%" }}
                  transition={{ duration: 0.5, ease: "easeOut" }}
                />
              </div>
            );
          })}
        </div>
      )}
    </header>
  );
}
