import { CircleCheck } from "lucide-react";

/* The balanced result (with or without a maintenance routine): shown only when the backend's analysis verdict for this scan is "balanced"
   (screens/Routine.jsx, services/routinePlan.js routineState). Failures have their own error state. */
const COPY = {
  balanced: {
    icon: CircleCheck, tone: "bg-jade/5 border-jade/15", iconTone: "text-jade",
    title: "Your skin reads as balanced",
    body: "No specific concerns were detected in this scan. Your skin profile appears balanced, so no targeted products were selected.",
    note: "This is a complete result, not an error. Readings can shift with light and angle, so you can scan again anytime.",
  },
  // balanced, with a maintenance routine shown below it
  maintenance: {
    icon: CircleCheck, tone: "bg-jade/5 border-jade/15", iconTone: "text-jade",
    title: "Your skin reads as balanced",
    body: "Your skin appears balanced, so we recommend a simple maintenance routine to help maintain your current skin condition.",
    note: "No specific concerns were detected in this scan. Readings can shift with light and angle, so you can scan again anytime.",
  },
};

export function ResultNotice({ reason, body, children }) {
  const c = COPY[reason];
  return (
    <div className={`rounded-[24px] border p-6 sm:p-8 max-w-2xl mx-auto text-center ${c.tone}`} role="status">
      <c.icon size={32} className={`mx-auto mb-3 ${c.iconTone}`} strokeWidth={1.5} />
      <h3 className="font-display text-2xl text-ink mb-2">{c.title}</h3>
      <p className="text-sm leading-relaxed text-ink-soft">{body ?? c.body}</p>
      {c.note && <p className="mt-3 text-[12px] leading-relaxed text-ink-soft/80">{c.note}</p>}
      {children && <div className="mt-6 flex flex-col sm:flex-row gap-3 justify-center">{children}</div>}
    </div>
  );
}
