/* Static copy used by the screens. Skin results, products, routine and chat replies
   come from the backend via src/services/skinAnalysis.js. */

// Generic guidance per focus area (ids match the metrics in services/skinAnalysis.js).
export const FOCUS_GUIDANCE = {
  hydration: { title: "Boost hydration", body: "Layer lightweight moisture in both routines and keep cleansing gentle so skin isn't stripped." },
  oiliness: { title: "Balance excess oil", body: "Use a light, oil-free moisturizer and a gentle cleanser so skin isn't stripped and rebounds oilier." },
  texture: { title: "Smooth your texture", body: "Keep skin hydrated and add a gentle exfoliating or renewing step a few times a week." },
  redness: { title: "Calm redness", body: "Include a soothing step after cleansing, especially when skin feels warm or tight." },
  pigmentation: { title: "Even out skin tone", body: "Add a brightening step and use sun protection every morning to keep tone even." },
  pores: { title: "Refine the look of pores", body: "Cleanse thoroughly at night and use a toner or treatment that keeps pores clear." },
  acne: { title: "Care for blemish-prone skin", body: "Keep to a gentle routine, avoid picking, and use targeted products only on the affected areas." },
};

export const ANALYSIS_STAGES = [
  "Correcting lighting & exposure",
  "Mapping facial regions",
  "Reading texture, tone & hydration",
  "Building your skin profile",
  "Personalizing your routine",
];

export const SUGGESTED_QUESTIONS = [
  "How should I use my routine?",
  "Which product do I use first?",
  "What helps with dry skin?",
  "Can I use these products together?",
];
