/* Pure presentation logic for the Personalized Routine (no React, so it can be unit-tested with node --test).
   Which products and steps appear always comes from the backend routine; this only merges and words them. */

// Skincare order for display; products whose step is unknown go last.
export const STEP_ORDER = ["Cleanse", "Tone", "Treat", "Moisturize", "Protect"];
// Daily routine steps (lower-case, as the recommender's routine_step); everything else is an optional extra.
export const ROUTINE_STEPS = ["cleanse", "tone", "treat", "moisturize", "protect"];

// One product = one card: the key is the backend product ID (falling back to its official URL), never the name.
export const productKey = (step) => step.id ?? step.url ?? step.handle;

/** The morning and evening routines as one ordered list of unique products, each with when to use it. */
export function mergeRoutine(routine) {
  const byKey = new Map();
  [["AM", routine?.AM ?? []], ["PM", routine?.PM ?? []]].forEach(([time, list]) => list.forEach((step, i) => {
    const key = productKey(step);
    if (key == null) return; // a step without any product identity cannot be shown or bought
    const found = byKey.get(key);
    if (found) found.times.add(time);
    else byKey.set(key, { step, times: new Set([time]), order: (time === "AM" ? 0 : 1000) + i });
  }));
  const rank = (e) => { const r = STEP_ORDER.indexOf(e.step.step); return r < 0 ? STEP_ORDER.length : r; };
  return [...byKey.values()]
    .sort((a, b) => rank(a) - rank(b) || a.order - b.order)
    .map((e) => ({ ...e, when: e.times.size === 2 ? "Morning & Evening" : e.times.has("AM") ? "Morning" : "Evening" }));
}

/** Recommended products that are not a daily step and not already in the routine, each once. */
export function optionalExtras(recommendations, entries) {
  const inRoutine = new Set(entries.map((e) => e.step.handle));
  const seen = new Set();
  return (recommendations ?? []).filter((p) => {
    if (ROUTINE_STEPS.includes(p.routineStep) || inRoutine.has(p.id) || seen.has(p.id)) return false;
    seen.add(p.id);
    return true;
  });
}

// ---- "Use consistently": how often (official) + when to review (a checkpoint, never a result promise) ----
// Frequency comes only from official YuriWoori text (the live endpoint's `usage`, quoted from the product's
// "How to use" copy or its yuriwoori.com description). When nothing is stated, the wording says so. The review
// checkpoint is the routine's general minimum of 3 weeks of consistent use, naming the measurement(s) this
// product was matched to in the scan; no product states a result timeline, so none is given.
export const FREQUENCY = { daily: "daily", morning_and_night: "morning and night", morning: "in the morning", weekly: "weekly", as_needed: "as needed" };
export const REVIEW_FOCUS = { hydration: "hydration", brightening: "skin tone", "uneven-tone": "skin tone", redness: "redness", blemish: "blemishes", "pore-visibility": "pore visibility", oiliness: "oiliness" };
export const REVIEW_WEEKS = 3;
const listOf = (items) => (items.length < 2 ? items.join("") : `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`);

export function guidance({ usage, when, tags }) {
  const f = usage?.frequency;
  const official = f && FREQUENCY[f] ? `Use ${FREQUENCY[f]}, as the official product information recommends.` : null;
  const focus = [...new Set((tags ?? []).map((t) => REVIEW_FOCUS[t]).filter(Boolean))];
  const review = `Review your ${focus.length ? `${listOf(focus)} and scan measurements` : "skin"} after at least ${REVIEW_WEEKS} weeks of consistent use.`;
  return {
    // daily routine card: official frequency (or its absence) + the routine slot
    routine: official
      ? `${official} In your routine: ${(when ?? "").toLowerCase()}.`
      : `Use ${(when ?? "").toLowerCase()} as part of your routine; the official product information doesn't state a specific frequency.`,
    // optional extra: official frequency or the safe default
    extra: official ?? "Use according to the product's recommended frequency; yuriwoori.com doesn't state how often.",
    wear: usage?.wear_time ? `Leave on for ${usage.wear_time} each time, as directed.` : null,
    review,
    source: usage?.quote ? `yuriwoori.com: “${usage.quote}”` : undefined,
  };
}

/**
 * What the routine page shows for the loaded analysis:
 *   "ready"          products to show
 *   "maintenance"    the backend's explicit "balanced" verdict, with a maintenance routine of real catalogue products
 *   "balanced"       the same verdict, when no maintenance product is available
 *   "matching-error" concerns were detected, but no matching product came back
 *   "server-error"   the server couldn't be reached or failed
 *   "data-error"     the analysis or a response is missing, incomplete or doesn't fit
 * A failure, an empty product list or missing data is never "balanced".
 */
export function routineState(analysis, entries, extras) {
  if (!analysis?.scanId) return "data-error";
  const errors = analysis.matchErrors ?? [];
  const failed = (part) => `${analysis.matchErrorKinds?.[part] ?? "data"}-error`;
  if (errors.includes("routine")) return failed("routine");
  if (!analysis.routine) return "data-error";
  if (entries.length === 0 && extras.length === 0) {
    if (errors.includes("recommendations")) return failed("recommendations");
    if (analysis.analysisStatus === "balanced") {
      if (errors.includes("maintenance")) return failed("maintenance");
      const care = analysis.maintenance;
      return care && (care.AM.length > 0 || care.PM.length > 0) ? "maintenance" : "balanced";
    }
    if (analysis.analysisStatus === "concerns") return "matching-error";
    return "data-error";
  }
  // products for a scan the backend called balanced: the two responses disagree
  if (analysis.analysisStatus === "balanced" && entries.length > 0) return "data-error";
  return "ready";
}
