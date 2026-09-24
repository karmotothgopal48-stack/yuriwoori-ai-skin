import { BRAND } from "../theme/brand";
import { motion, useInView } from "framer-motion";
import { useRef } from "react";

export function ScoreRing({ value, size = 88, stroke = 7, label }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-10px" });
  
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const offset = c - ((value || 0) / 100) * c;

  return (
    <div ref={ref} className="relative inline-flex items-center justify-center shrink-0">
      <svg width={size} height={size} role="img" aria-label={`${label || "Score"} ${value}`}>
        <circle cx={size / 2} cy={size / 2} r={r} stroke={BRAND.mist} strokeWidth={stroke} fill="none" />
        <motion.circle
          cx={size / 2} cy={size / 2} r={r} fill="none" stroke={BRAND.deepJade} strokeWidth={stroke}
          strokeLinecap="round" strokeDasharray={c}
          initial={{ strokeDashoffset: c }}
          animate={{ strokeDashoffset: isInView ? offset : c }}
          transition={{ duration: 1.2, ease: "easeOut", delay: 0.1 }}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
        <text x="50%" y="52%" textAnchor="middle" dominantBaseline="middle" fill={BRAND.deepJade}
          style={{ fontFamily: "var(--font-display)", fontSize: size * 0.32 }}>
          {value || 0}
        </text>
      </svg>
    </div>
  );
}
