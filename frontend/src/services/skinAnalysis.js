/* Service boundary to the backend. Screens only call these functions.
   Scan flow: POST /scans → POST /scans/{id}/frames → POST /scans/{id}/analyze,
   then CSV-catalogue recommendations, routine and compatibility for that scan. */
import { api, ApiError } from "./api";

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

// ---- Photo prep ---------------------------------------------------------
// The backend quality gate only accepts JPEG. Uploaded files can be PNG/WebP/HEIC-as-PNG,
// so every photo is re-encoded through a canvas (also caps size).
function toJpegDataUrl(dataUrl, maxSide = 1280) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const scale = Math.min(1, maxSide / Math.max(img.width, img.height));
      const c = document.createElement("canvas");
      c.width = Math.round(img.width * scale); c.height = Math.round(img.height * scale);
      c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
      resolve(c.toDataURL("image/jpeg", 0.92));
    };
    img.onerror = () => reject(new ApiError("That photo couldn't be read. Please retake or choose another.", 0));
    img.src = dataUrl;
  });
}

// ---- Backend metrics → screen model -------------------------------------
// Backend scores are 0–100. hydration/texture: higher = better. The rest are "amount of the trait",
// so they are flipped to a health score where higher = better. Only metrics the backend
// actually measures are shown (no face-region markers, dark circles or lines).
const METRICS = [
  { id: "hydration", label: "Hydration", key: "hydration", flip: false },
  { id: "oiliness", label: "Oil balance", key: "oiliness", flip: true },
  { id: "texture", label: "Texture", key: "texture", flip: false },
  { id: "redness", label: "Redness", key: "redness", flip: true },
  { id: "pigmentation", label: "Pigmentation", key: "pigmentation", flip: true },
  { id: "pores", label: "Pores", key: "pore_visibility", flip: true },
  { id: "acne", label: "Blemishes", key: "blemish_index", flip: true },
];

const NOTES = {
  hydration: ["Skin reads as well hydrated.", "Hydration looks moderate.", "Skin looks under-hydrated."],
  oiliness: ["Shine and oil look well balanced.", "Some shine is visible.", "Noticeable shine suggests excess oil."],
  texture: ["Texture looks smooth and even.", "Texture looks fairly even, with some roughness.", "Texture looks uneven in places."],
  redness: ["Very little visible redness.", "Mild redness is visible.", "Visible redness stands out."],
  pigmentation: ["Tone looks even.", "Some tonal variation is visible.", "Noticeable uneven tone or darker patches."],
  pores: ["Pores are barely visible.", "Pores are slightly visible.", "Pores are clearly visible."],
  acne: ["Few visible blemishes.", "A few blemish-prone spots.", "Several blemish-prone spots."],
};
// Which backend concern tags (from /catalogue/recommendations) address each result area.
// Texture has no matching product tag, so it never gets product suggestions.
const AREA_TAGS = {
  hydration: ["hydration"],
  oiliness: ["oiliness"],
  redness: ["redness"],
  pigmentation: ["brightening", "uneven-tone"],
  pores: ["pore-visibility"],
  acne: ["blemish"],
};
const areasFor = (concernTags) => Object.keys(AREA_TAGS).filter((a) => AREA_TAGS[a].some((t) => concernTags.includes(t)));

const noteFor = (id, score) => NOTES[id][score >= 75 ? 0 : score >= 55 ? 1 : 2];

function buildAnalysis(p) {
  const scored = METRICS
    .filter((m) => p[m.key] != null)
    .map((m) => {
      const score = Math.round(m.flip ? 100 - p[m.key] : p[m.key]);
      return { id: m.id, label: m.label, score: Math.max(0, Math.min(100, score)), note: noteFor(m.id, score), markers: [] };
    });
  const focus = [...scored].sort((a, b) => a.score - b.score).slice(0, 3).map((c) => c.id);
  const concerns = scored.map((c) => ({ ...c, status: c.score >= 75 ? "strength" : focus.includes(c.id) ? "focus" : "balanced" }));
  const names = focus.map((id) => concerns.find((c) => c.id === id).label.toLowerCase());
  const type = p.skin_type ? p.skin_type[0].toUpperCase() + p.skin_type.slice(1) : "Unknown";
  return {
    concerns,
    profile: {
      skinType: type,
      overall: p.overall_score != null ? Math.round(p.overall_score) : null,
      summary: names.length ? `Your main areas of focus are ${names.join(", ")}.` : "Your skin looks balanced overall.",
      focus,
    },
  };
}

const capitalize = (s) => (s ? s[0].toUpperCase() + s.slice(1) : "");

/** @param {string} imageDataUrl captured face photo (data URL) */
export async function analyzeSkin(imageDataUrl) {
  const image = await toJpegDataUrl(imageDataUrl);

  const { scan_id: scanId } = await api("/scans", { method: "POST" });
  const frame = await api(`/scans/${scanId}/frames`, { method: "POST", body: { angle: "front", image_base64: image } });
  if (!frame.passed) {
    throw new ApiError(
      `This photo didn't pass the quality check (sharpness ${Math.round(frame.blur_score)}, lighting ${Math.round(frame.lighting_score)}). ` +
      "Please retake it facing a soft, even light.", 422);
  }
  const profile = await api(`/scans/${scanId}/analyze`, { method: "POST" });

  // Extras are best-effort: a failure here should not throw away a successful analysis.
  const [recs, routine, products] = await Promise.allSettled([
    api(`/catalogue/recommendations?scan_id=${scanId}`), // products from data/products_export.csv
    api(`/scans/${scanId}/routine`),
    api("/products"),
  ]);
  const byId = Object.fromEntries((products.value ?? []).map((p) => [p.id, p]));
  const shape = (id, name, image, price) => ({ id, name, image, price, url: byId[id]?.product_url ?? null, step: capitalize(byId[id]?.routine_step) });

  let compatibility = [];
  if (routine.status === "fulfilled") {
    try { compatibility = await api(`/scans/${scanId}/compatibility`); } catch { /* optional */ }
  }

  const stepList = (list) => list.map((s) => ({
    ...shape(s.product_id, s.product_name, s.image_url, byId[s.product_id]?.price ?? null),
    order: s.step_order, reason: s.reason,
  }));

  return {
    scanId,
    ...buildAnalysis(profile),
    recommendations: recs.status === "fulfilled"
      ? recs.value.recommendations.map((r) => ({
          id: r.handle, name: r.name, image: r.image_url, price: r.price, url: r.product_url,
          step: capitalize(r.routine_step), reason: r.match_reason,
          areas: areasFor(r.matched_concerns), // result areas (hydration, pores, …) this product helps
        }))
      : null,
    routine: routine.status === "fulfilled" ? { AM: stepList(routine.value.AM), PM: stepList(routine.value.PM) } : null,
    compatibility: compatibility.map((f) => ({ a: f.product_a_name, b: f.product_b_name, type: f.relationship_type, text: f.explanation })),
  };
}

let conversationId = null;

/** Send a message to Yuri (Claude via the backend). Keeps the conversation across messages. */
export async function askYuri(question) {
  const res = await api("/coach/message", { method: "POST", body: { conversation_id: conversationId, message: question } });
  conversationId = res.conversation_id;
  return res.reply;
}

/* Face detection seam. The camera screen calls this with a video element;
   the backend has no face-detection endpoint, so this stays a simulated result. */
export async function detectFace(videoEl) {
  void videoEl;
  await wait(1800);
  return { detected: true, centered: true, simulated: true };
}
