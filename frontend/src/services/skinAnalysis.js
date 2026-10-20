/* Service boundary to the backend. Screens only call these functions.
   Scan flow: POST /scans → POST /scans/{id}/frames → POST /scans/{id}/analyze,
   then (in parallel) recommendations and the routine, both chosen from the live yuriwoori.com catalogue. */
import { api, ApiError } from "./api";
import { METRIC_INFO } from "../data/mock";

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
    img.onerror = () => reject(scanError("photo", "That photo couldn't be read. Please retake it or choose another one."));
    img.src = dataUrl;
  });
}

// Errors carry a `kind` so the Processing screen can give the right advice:
// photo (unreadable file), quality (backend quality gate), face (no centred face), hand (no hand), network, server.
function scanError(kind, message, status = 0) {
  const e = new ApiError(message, status);
  e.kind = kind;
  return e;
}

// ---- Backend metrics → screen model -------------------------------------
// Metric definitions (label, backend field, direction, and the concern tags the backend
// recommender uses for it) live in data/mock.js as METRIC_INFO, next to their explanations.
// A metric is "flagged" only when the backend reports one of its tags in `active_concerns`
// (i.e. the value crossed the backend's own threshold) — the frontend never re-derives thresholds.
// Each metric is shown as { metric, typicalBenchmark, yourResult }: yourResult is the analysed score;
// typicalBenchmark is the fixed internal YuriWoori benchmark the backend sends with every analysis
// (`profile.benchmark`, backend app/services/benchmark.py) — the same for every scan, and separate from
// the product thresholds behind `flagged`. null when no benchmark is configured (hand scans).
function compareWithBenchmark(result, benchmark) {
  if (benchmark == null) return null;
  return result > benchmark ? "higher" : result < benchmark ? "lower" : "same";
}

function buildConcerns(profile, activeConcerns) {
  return METRIC_INFO.filter((m) => profile[m.key] != null).map((m) => {
    const tags = m.tags.filter((t) => activeConcerns && t in activeConcerns);
    const typicalBenchmark = profile.benchmark?.[m.key] ?? null;
    const yourResult = Math.round(profile[m.key]);
    return {
      metric: m.key,
      id: m.id,
      label: m.label,
      value: Math.round(profile[m.key]),
      higherIsBetter: m.higherIsBetter,
      measures: m.measures,
      tags: m.tags,
      matchable: m.tags.length > 0,
      // null = unknown (recommendations call failed), true/false = backend verdict
      flagged: activeConcerns ? tags.length > 0 : null,
      phrase: tags.length ? activeConcerns[tags[0]] : null,
      yourResult,
      typicalBenchmark: typicalBenchmark != null ? Math.round(typicalBenchmark) : null,
      comparison: compareWithBenchmark(yourResult, typicalBenchmark != null ? Math.round(typicalBenchmark) : null),
    };
  });
}

const capitalize = (s) => (s ? s[0].toUpperCase() + s.slice(1) : "");

/**
 * Runs the full scan and returns everything the result screens need.
 * @param {string} imageDataUrl captured or uploaded face photo (data URL)
 * @param {(stage: "upload"|"quality"|"analyze"|"match"|"done") => void} [onStage] real progress callback
 * @param {"face"|"hand"} [bodyPart] what the camera step detected; sent as the frame angle so the
 *   server runs (and first verifies) the matching analysis
 */
export async function analyzeSkin(imageDataUrl, onStage = () => {}, bodyPart = "face") {
  onStage("upload");
  const image = await toJpegDataUrl(imageDataUrl);

  let scanId;
  try {
    ({ scan_id: scanId } = await api("/scans", { method: "POST" }));  // needs the signup session
  } catch (e) {
    if (e.status === 401) throw scanError("auth", e.message, 401);
    throw e;
  }
  let frame;
  try {
    frame = await api(`/scans/${scanId}/frames`, { method: "POST", body: { angle: bodyPart === "hand" ? "hand" : "front", image_base64: image } });
  } catch (e) {
    // the server refused the photo itself (unreadable, too large or malformed): a photo problem, not a server outage
    if ([400, 413, 422].includes(e.status)) throw scanError("photo", e.message, e.status);
    throw e;
  }

  onStage("quality");
  const quality = {
    sharpness: frame.blur_score, lighting: frame.lighting_score, overall: frame.quality_score, passed: frame.passed,
  };
  if (!frame.passed) {
    throw scanError("quality",
      `The photo didn't pass the server's quality check (sharpness ${Math.round(frame.blur_score)}, ` +
      `lighting ${Math.round(frame.lighting_score)}). Retake it facing soft, even light and hold the camera steady.`, 422);
  }

  onStage("analyze");
  let profile;
  try {
    // the photo is sent again: the server never stores it, it analyses it in memory and discards it
    profile = await api(`/scans/${scanId}/analyze`, { method: "POST", body: { angle: bodyPart === "hand" ? "hand" : "front", image_base64: image } });
  } catch (e) {
    if (e.status === 422) throw scanError(bodyPart === "hand" ? "hand" : "face", e.message, 422);
    throw e;
  }

  // The analysis is saved: its report can be made now (once, from the saved results) and sent wherever the
  // customer has agreed and confirmed a contact. Best-effort here; the routine page shows and retries it.
  api("/reports", { method: "POST", body: { scan_id: scanId } }).catch(() => {});

  // Product matching never throws away a successful analysis: its failures are reported as errors on
  // the result (shown with a Retry on the routine page), never as a "balanced" result.
  onStage("match");
  const matched = await loadRecommendations(scanId);

  onStage("done");
  return applyRecommendations({
    scanId,
    bodyPart,
    quality,
    rawProfile: profile,
    modelVersion: profile.model_version,
    benchmarkVersion: profile.benchmark_version ?? null,
    profile: {
      skinType: capitalize(profile.skin_type) || "Unknown",
      overall: profile.overall_score != null ? Math.round(profile.overall_score) : null,
    },
  }, matched);
}

// ---- Recommendations + routine (re-loadable for Retry) --------------------
// A recommendations response must describe THIS scan and state its verdict explicitly; "balanced" is only
// trusted when the backend says so and lists no concern (an empty or partial response is never "balanced").
const isRecsResponse = (r, scanId) => r && r.scan_id === scanId && (r.analysis_status === "balanced" || r.analysis_status === "concerns")
  && typeof r.active_concerns === "object" && r.active_concerns !== null && Array.isArray(r.recommendations)
  && (r.analysis_status === "balanced") === (Object.keys(r.active_concerns).length === 0);
// Why a request failed: "server" (unreachable or a server error) or "data" (refused or a response we can't use).
const failureKind = (settled) =>
  settled.status === "rejected" && (settled.reason?.status === 0 || settled.reason?.status >= 500) ? "server" : "data";
// Every step is a live store product: it must carry its identity and official page (backend RoutineStepResponse).
const isRoutineResponse = (r) => r && Array.isArray(r.AM) && Array.isArray(r.PM)
  && [...r.AM, ...r.PM].every((step) => step && step.product_id && step.product_name && step.handle && step.product_url);

/**
 * Concerns, recommendations, routine and ingredient notes for an analysed scan. Each part is validated:
 * a failed or malformed response becomes `null` plus an entry in `errors` — never an empty "balanced" result.
 * Products, steps, prices and usage copy all come from the live yuriwoori.com catalogue via the backend.
 * @returns {{ analysisStatus: "balanced"|"concerns"|null, activeConcerns: object|null, recommendations: array|null, routine: {AM, PM}|null,
 *   maintenance: {AM, PM}|null (balanced verdict only),
 *   compatibility: array, errors: string[], errorKinds: {[part: string]: "server"|"data"|"matching"} }}
 */
export async function loadRecommendations(scanId) {
  if (!scanId) throw new ApiError("This analysis has no scan ID, so its routine can't be loaded.", 0);
  const [recs, routine] = await Promise.allSettled([
    api(`/catalogue/recommendations?scan_id=${scanId}`), // concerns + products from the live store catalogue
    api(`/scans/${scanId}/routine`),                        // routine rebuilt from the live store catalogue
  ]);
  const errors = [];
  const errorKinds = {};
  const recsOk = recs.status === "fulfilled" && isRecsResponse(recs.value, scanId);
  if (!recsOk) { errors.push("recommendations"); errorKinds.recommendations = failureKind(recs); }

  const routineOk = routine.status === "fulfilled" && isRoutineResponse(routine.value);
  if (!routineOk) { errors.push("routine"); errorKinds.routine = failureKind(routine); }

  let compatibility = [];
  if (routineOk) {
    try { compatibility = await api(`/scans/${scanId}/compatibility`); } catch { /* optional: ingredient notes only */ }
  }

  // A "balanced" verdict, and only that, gets a maintenance routine from the same catalogue
  // (backend /scans/{id}/maintenance-routine). It is validated like the routine; a failure is an error.
  let maintenance = null;
  if (recsOk && recs.value.analysis_status === "balanced") {
    const [care] = await Promise.allSettled([api(`/scans/${scanId}/maintenance-routine`)]);
    if (care.status === "fulfilled" && isRoutineResponse(care.value)) {
      maintenance = care.value;
    } else {
      errors.push("maintenance");
      errorKinds.maintenance = failureKind(care);
    }
  }

  const activeConcerns = recsOk ? recs.value.active_concerns : null;
  const stepList = (list) => list.map((step) => ({
    id: step.product_id, handle: step.handle, order: step.step_order, name: step.product_name, image: step.image_url ?? null,
    step: capitalize(step.routine_step), price: step.price ?? null, url: step.product_url,
    howToUse: step.how_to_use ?? null, reason: step.reason ?? "",
    keyBenefit: step.key_benefit ?? null, benefits: step.benefits ?? [], ingredients: step.ingredients ?? [],
  }));

  return {
    analysisStatus: recsOk ? recs.value.analysis_status : null,
    activeConcerns,
    recommendations: recsOk
      ? recs.value.recommendations.map((r) => ({
          id: r.handle, rank: r.rank, score: r.score, name: r.name, image: r.image_url, price: r.price,
          url: r.product_url, step: capitalize(r.routine_step), routineStep: r.routine_step,
          keyBenefit: r.key_benefit, howToUse: r.how_to_use, chips: r.chips,
          benefits: r.benefits ?? [], ingredients: r.ingredients ?? [],
          category: r.category, description: r.description,
          matched: (r.matched_concerns ?? []).map((t) => ({ tag: t, phrase: activeConcerns?.[t] ?? null })),
          reason: r.match_reason,
        }))
      : null,
    routine: routineOk ? { AM: stepList(routine.value.AM), PM: stepList(routine.value.PM) } : null,
    maintenance: maintenance ? { AM: stepList(maintenance.AM), PM: stepList(maintenance.PM) } : null,
    compatibility: (Array.isArray(compatibility) ? compatibility : []).map((f) => ({ a: f.product_a_name, b: f.product_b_name, type: f.relationship_type, text: f.explanation })),
    errors,
    errorKinds,
  };
}

/** The analysis with (re)loaded recommendations; measurement statuses follow the backend's concerns. */
export function applyRecommendations(analysis, matched) {
  return {
    ...analysis,
    concerns: buildConcerns(analysis.rawProfile, matched.activeConcerns),
    activeConcerns: matched.activeConcerns,
    recommendations: matched.recommendations,
    routine: matched.routine,
    maintenance: matched.maintenance,
    compatibility: matched.compatibility,
    analysisStatus: matched.analysisStatus,
    matchErrors: matched.errors,
    matchErrorKinds: matched.errorKinds,
  };
}

// ---- Signup + engagement tracking ---------------------------------------

/** Name + WhatsApp number + email + accepted privacy notice (+ optional consent to have the report sent) -> { token, user }.
 *  An email that already has an account answers { code_required: true, sent_to } (a sign-in code was emailed there)
 *  unless this browser is already signed in to it; send the same details again with that code. The stored session
 *  is sent along (an expired one is ignored by the server). */
export const signUp = (name, whatsapp, email, consent, reportConsent = false, code = undefined) =>
  api("/users/signup", { method: "POST", body: { name, whatsapp, email, consent, report_consent: reportConsent, ...(code ? { code } : {}) } });

/** The signed-up user for the stored session, or throws (401 when missing/expired). */
export const fetchMe = () => api("/users/me");

// Tracking is best-effort: it must never block the user or break the product link.
/** The user reached their routine for this scan (the backend records what was offered, once). */
const shownSent = new Set(); // one request per scan per page load (React dev StrictMode runs effects twice)
export function trackRecommendationsShown(scanId) {
  if (!scanId || shownSent.has(scanId)) return;
  shownSent.add(scanId);
  api("/events", { method: "POST", body: { event_type: "recommendations_shown", scan_id: scanId } }).catch(() => shownSent.delete(scanId));
}

/** The user opened an official product page. keepalive lets the request finish while the new tab opens. */
export function trackProductClick(scanId, productHandle) {
  if (!scanId || !productHandle) return;
  api("/events", { method: "POST", keepalive: true, body: { event_type: "product_clicked", scan_id: scanId, product_handle: productHandle } }).catch(() => {});
}

let conversationId = null;

/** Send a message to Yuri (Claude via the backend). Keeps the conversation across messages. */
export async function askYuri(question) {
  const send = () => api("/coach/message", { method: "POST", body: { conversation_id: conversationId, message: question } });
  let res;
  try {
    res = await send();
  } catch (e) {
    // The conversation belongs to a previous session (e.g. after signing out): start a new one.
    if (e.status !== 404 || !conversationId) throw e;
    conversationId = null;
    res = await send();
  }
  conversationId = res.conversation_id;
  return res.reply;
}
