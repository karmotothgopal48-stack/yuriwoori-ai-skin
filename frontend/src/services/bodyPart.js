/* On-device body-part detection and full-face validation for the camera step, with MediaPipe Tasks
   (Apache-2.0, trained models): Face Landmarker (478 landmarks + head pose) and Hand Landmarker.
   It decides which supported body part is in view, and for a face whether the whole face is usable,
   so capture is only enabled for a photo the analysis can use. The server runs the same checks again
   before measuring (backend app/services/skin_analysis.py), so a bad photo is still rejected there.
   Models are served from /public/models and the Wasm runtime is bundled: nothing loads from a CDN. */
import { FaceLandmarker, HandLandmarker } from "@mediapipe/tasks-vision";
import wasmLoaderPath from "@mediapipe/tasks-vision/vision_wasm_internal.js?url";
import wasmBinaryPath from "@mediapipe/tasks-vision/vision_wasm_internal.wasm?url";

const FACE_MODEL = "/models/face_landmarker.task";
const HAND_MODEL = "/models/hand_landmarker.task";
const MIN_HAND_SCORE = 0.6;
const MIN_HAND_AREA = 0.04; // smallest share of the frame a hand must cover to be measurable

// Full-face rules. LIVE (camera) is stricter than PHOTO (uploads), which matches the server
// (skin_analysis.py), so a live capture that passes here always passes there too.
const RULES = {
  LIVE: { margin: 0.03, minHeight: 0.36, maxHeight: 0.75, centreX: [0.35, 0.65], centreY: [0.3, 0.7], yaw: 20, pitch: 20, roll: 12, minPixels: 224 },
  PHOTO: { margin: 0.01, minHeight: 0.15, maxHeight: 0.9, centreX: [0.25, 0.75], centreY: [0.15, 0.85], yaw: 25, pitch: 25, roll: 15, minPixels: 224 },
};
const SECOND_FACE_SHARE = 0.25; // another face at least this big (relative to the main one) = multiple faces
// Photos are sent with their longest side capped at 1280 px (services/skinAnalysis.js toJpegDataUrl), and the
// server needs the face at least minPixels tall in that photo, so pixel sizes are judged at upload size.
const UPLOAD_MAX_SIDE = 1280;
const uploadScale = (width, height) => Math.min(1, UPLOAD_MAX_SIDE / Math.max(width, height));

// Face-mesh landmark indices (same as the server)
const FOREHEAD = 10, CHIN = 152, LEFT_CHEEK = 234, RIGHT_CHEEK = 454, LEFT_EYE = 33, RIGHT_EYE = 263, NOSE = 1;
const KEY = [FOREHEAD, CHIN, LEFT_CHEEK, RIGHT_CHEEK, LEFT_EYE, RIGHT_EYE, NOSE];

export const FACE_MESSAGES = {
  multiple: "Only one face should be visible",
  centre: "Centre your full face in the frame",
  farther: "Move slightly farther away",
  closer: "Move slightly closer",
  visible: "Make sure your full face is visible",
  straight: "Keep your head straight and look at the camera",
};

let loading = null;
let switchingMode = false; // IMAGE/VIDEO mode switch in progress: skip live frames meanwhile

/** Loads both detectors once (later calls share the same promise; a failed load can be retried). */
export function loadDetectors() {
  if (!loading) {
    const fileset = { wasmLoaderPath, wasmBinaryPath };
    const base = (path) => ({ modelAssetPath: path, delegate: "CPU" });
    loading = Promise.all([
      FaceLandmarker.createFromOptions(fileset, {
        baseOptions: base(FACE_MODEL), runningMode: "VIDEO", numFaces: 3,
        minFaceDetectionConfidence: 0.5, minFacePresenceConfidence: 0.5, outputFacialTransformationMatrixes: true,
      }),
      HandLandmarker.createFromOptions(fileset, {
        baseOptions: base(HAND_MODEL), runningMode: "VIDEO", numHands: 2,
        minHandDetectionConfidence: 0.5, minHandPresenceConfidence: 0.5,
      }),
    ]).then(([face, hand]) => ({ face, hand }));
    loading.catch(() => { loading = null; });
  }
  return loading;
}

const box = (points) => {
  const xs = points.map((p) => p.x), ys = points.map((p) => p.y);
  return { x0: Math.min(...xs), y0: Math.min(...ys), x1: Math.max(...xs), y1: Math.max(...ys) };
};
const area = (b) => Math.max(0, b.x1 - b.x0) * Math.max(0, b.y1 - b.y0);
const overlapShare = (a, b) => // share of box a covered by box b
  (Math.max(0, Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0)) * Math.max(0, Math.min(a.y1, b.y1) - Math.max(a.y0, b.y0))) / Math.max(area(a), 1e-6);

/** Yaw, pitch, roll (degrees) from the 4x4 facial transformation matrix (column-major data). */
function headPose(matrix) {
  const r = (row, col) => matrix.data[col * 4 + row];
  const deg = (rad) => (rad * 180) / Math.PI;
  return {
    yaw: deg(Math.asin(-Math.max(-1, Math.min(1, r(2, 0))))),
    pitch: deg(Math.atan2(r(2, 1), r(2, 2))),
    roll: deg(Math.atan2(r(1, 0), r(0, 0))),
  };
}

/** Maps landmarks into the visible frame: the camera preview crops the video to fill a 3:4 box. */
function toView(points, width, height, viewAspect) {
  if (!viewAspect) return points;
  const videoAspect = width / height;
  if (videoAspect > viewAspect) { // wider than the view: sides are cropped
    const visible = viewAspect / videoAspect, x0 = (1 - visible) / 2;
    return points.map((p) => ({ x: (p.x - x0) / visible, y: p.y }));
  }
  const visible = videoAspect / viewAspect, y0 = (1 - visible) / 2; // taller: top/bottom are cropped
  return points.map((p) => ({ x: p.x, y: (p.y - y0) / visible }));
}

/** Whether the main face is a complete, usable face under the given rules; message says what to fix.
    `aspect` is the frame's width / height (points are 0-1 in each direction). */
function checkFace(faces, mainIndex, faceResult, handBoxes, rules, pixelHeight, aspect) {
  // Forehead-to-chin length (straight line, so a slight tilt doesn't shrink it) as a share of the frame height
  const heights = faces.map((f) => Math.hypot((f[CHIN].x - f[FOREHEAD].x) * aspect, f[CHIN].y - f[FOREHEAD].y));
  if (heights.some((h, i) => i !== mainIndex && h >= SECOND_FACE_SHARE * heights[mainIndex])) return { ok: false, message: FACE_MESSAGES.multiple };
  const face = faces[mainIndex], height = heights[mainIndex];
  const outside = KEY.some((i) => face[i].x < rules.margin || face[i].x > 1 - rules.margin || face[i].y < rules.margin || face[i].y > 1 - rules.margin);
  if (height > rules.maxHeight) return { ok: false, message: FACE_MESSAGES.farther };
  if (outside) return { ok: false, message: height > rules.maxHeight * 0.9 ? FACE_MESSAGES.farther : FACE_MESSAGES.centre };
  const matrix = faceResult.facialTransformationMatrixes?.[mainIndex];
  if (matrix) {
    const { yaw, pitch, roll } = headPose(matrix);
    if (Math.abs(yaw) > rules.yaw || Math.abs(pitch) > rules.pitch || Math.abs(roll) > rules.roll) return { ok: false, message: FACE_MESSAGES.straight };
  }
  if (height < rules.minHeight || height * pixelHeight < rules.minPixels) return { ok: false, message: FACE_MESSAGES.closer };
  const cx = (face[LEFT_CHEEK].x + face[RIGHT_CHEEK].x) / 2, cy = (face[FOREHEAD].y + face[CHIN].y) / 2;
  if (cx < rules.centreX[0] || cx > rules.centreX[1] || cy < rules.centreY[0] || cy > rules.centreY[1]) return { ok: false, message: FACE_MESSAGES.centre };
  // The landmarker estimates hidden parts of a face, so a hand over it is checked separately.
  if (handBoxes.some((b) => overlapShare(box(face), b) > 0.1)) return { ok: false, message: FACE_MESSAGES.visible };
  return { ok: true, message: null };
}

/** Which body part is the subject, and for a face whether it passes the full-face checks. */
function classify(faceResult, handResult, width, height, rules, viewAspect) {
  const faces = faceResult.faceLandmarks.map((pts) => toView(pts, width, height, viewAspect));
  const hands = handResult.landmarks
    .filter((_, i) => (handResult.handedness[i]?.[0]?.score ?? 0) >= MIN_HAND_SCORE)
    .map((pts) => box(toView(pts, width, height, viewAspect)));

  const faceAreas = faces.map((f) => area(box(f)));
  const mainIndex = faceAreas.length ? faceAreas.indexOf(Math.max(...faceAreas)) : -1;
  const faceArea = mainIndex >= 0 ? faceAreas[mainIndex] : 0;
  const handArea = Math.max(0, ...hands.map(area).filter((a) => a >= MIN_HAND_AREA));

  // Both in view (a hand near the face, or a face behind a raised hand): the one filling more of the frame is the subject.
  if (faceArea === 0 && handArea === 0) return { part: null, face: null };
  if (handArea > faceArea) return { part: "hand", face: null };
  // Height of the visible frame in uploaded-photo pixels (face heights are shares of the visible frame).
  const visibleHeight = (viewAspect && width / height < viewAspect ? width / viewAspect : height) * uploadScale(width, height);
  const aspect = viewAspect ?? width / height;
  return { part: "face", face: checkFace(faces, mainIndex, faceResult, hands, rules, visibleHeight, aspect) };
}

/** Live detection on the current video frame (LIVE rules), or null while a mode switch is in progress.
    `viewAspect` is the preview box's width/height, so "in frame" means visible to the user. */
export function detectInVideo(detectors, video, timestamp, viewAspect) {
  if (switchingMode || !video.videoWidth) return null;
  return classify(
    detectors.face.detectForVideo(video, timestamp),
    detectors.hand.detectForVideo(video, timestamp),
    video.videoWidth, video.videoHeight, RULES.LIVE, viewAspect,
  );
}

const loadImage = (src) => new Promise((resolve, reject) => {
  const img = new Image();
  img.onload = () => resolve(img);
  img.onerror = reject;
  img.src = src;
});

/** Detection on a still photo (an uploaded file), with the same rules as the server (PHOTO). */
export async function detectInImage(dataUrl) {
  const detectors = await loadDetectors();
  const img = await loadImage(dataUrl);
  const setMode = (runningMode) => Promise.all([detectors.face.setOptions({ runningMode }), detectors.hand.setOptions({ runningMode })]);
  switchingMode = true;
  try {
    await setMode("IMAGE");
    return classify(detectors.face.detect(img), detectors.hand.detect(img), img.naturalWidth, img.naturalHeight, RULES.PHOTO, null);
  } finally {
    await setMode("VIDEO");
    switchingMode = false;
  }
}
