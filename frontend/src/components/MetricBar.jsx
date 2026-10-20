import { motion } from "framer-motion";

/* One measured value from the backend (0–100), shown as-is — never re-scaled or inverted.
   `flagged` comes from the backend's active_concerns (true / false / null = unknown). */
export function MetricBar({ label, value, higherIsBetter, flagged, compact = false }) {
  const tone = flagged ? "bg-[#b5655d]" : "bg-jade";
  return (
    <div className={compact ? "" : "py-1"}>
      <div className="flex items-baseline justify-between gap-3 mb-1.5">
        <span className="text-sm font-medium text-ink">{label}</span>
        <span className="text-sm font-semibold text-ink tabular-nums">
          {value}<span className="text-ink-soft/60 font-normal">/100</span>
        </span>
      </div>
      <div className="h-2 w-full rounded-pill bg-mist overflow-hidden" role="img" aria-label={`${label} ${value} out of 100`}>
        <motion.div
          className={`h-full rounded-pill ${tone}`}
          initial={{ width: 0 }}
          animate={{ width: `${Math.max(2, Math.min(100, value))}%` }}
          transition={{ duration: 0.9, ease: "easeOut" }}
        />
      </div>
      {!compact && (
        <p className="mt-1 text-[11px] text-ink-soft/80">
          {higherIsBetter ? "Higher is better" : "Higher means more of this trait"}
          {flagged === true && " · Stood out in your scan"}
        </p>
      )}
    </div>
  );
}
