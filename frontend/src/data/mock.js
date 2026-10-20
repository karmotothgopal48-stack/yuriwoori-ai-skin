/* Static copy used by the screens. Skin results, products, routine and chat replies
   come from the backend via src/services/skinAnalysis.js. */

// The seven values the backend's analyzer returns (backend app/services/skin_analysis.py).
// `measures` describes what the code actually computes; `tags` are the concern tags the backend
// recommender matches for this metric (app/services/recommendation.py CONCERN_RULES + hydration).
// Texture has no rule, so it is measured but never used to pick products.
export const METRIC_INFO = [
  { id: "hydration", label: "Hydration", key: "hydration", higherIsBetter: true, tags: ["hydration"],
    measures: "An estimate from how smooth the skin looks and how much shine it has — not a direct moisture reading." },
  { id: "oiliness", label: "Oiliness", key: "oiliness", higherIsBetter: false, tags: ["oiliness"],
    measures: "How much of the face shows bright, low-colour highlights (shine)." },
  { id: "texture", label: "Texture", key: "texture", higherIsBetter: true, tags: [],
    measures: "How smooth the skin area looks, from the amount of fine detail in the photo." },
  { id: "redness", label: "Redness", key: "redness", higherIsBetter: false, tags: ["redness"],
    measures: "The average red tone of the skin-coloured pixels in the measured skin area." },
  { id: "pigmentation", label: "Uneven tone", key: "pigmentation", higherIsBetter: false, tags: ["brightening", "uneven-tone"],
    measures: "How much the brightness of your skin varies across the measured skin area." },
  { id: "pores", label: "Pore visibility", key: "pore_visibility", higherIsBetter: false, tags: ["pore-visibility"],
    measures: "The amount of fine detail in the centre of the face (nose and inner cheeks)." },
  { id: "acne", label: "Blemishes", key: "blemish_index", higherIsBetter: false, tags: ["blemish"],
    measures: "How many small reddish spots appear on the skin." },
];

// Routine step order used by the backend routine builder (app/services/routine_builder.py).
export const STEP_ORDER = ["cleanse", "tone", "treat", "moisturize", "protect", "mask", "unassigned"];

export const DISCLAIMER = "This analysis is for skincare guidance and is not a medical diagnosis.";

export const SUGGESTED_QUESTIONS = [
  "How should I use my routine?",
  "Which product do I use first?",
  "What helps with dry skin?",
  "Can I use these products together?",
];
