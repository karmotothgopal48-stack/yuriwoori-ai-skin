// ---- Opening the camera -------------------------------------------------

/** What the person is told for each way the camera can fail (see cameraErrorKind). */
export const CAMERA_MESSAGES = {
  denied: "Camera access is blocked for this site. Allow the camera in your browser's site settings (the camera icon in the address bar), then try again — or upload a photo instead.",
  notFound: "No camera was found on this device. Connect a camera and try again — or upload a photo instead.",
  inUse: "Your camera is being used by another app or browser (for example Teams, Zoom, or a tab in another browser). Close the camera there, then try again — or upload a photo instead.",
  unsupported: "This browser can't use the camera here. Open the app in a current version of Chrome, Edge, Safari or Firefox at http://localhost or over https — or upload a photo instead.",
  unknown: "The camera couldn't be started. Please try again — or upload a photo instead.",
};

/** getUserMedia failure -> "denied" | "notFound" | "inUse" | "unsupported" | "unknown" (names differ by browser). */
export function cameraErrorKind(error) {
  switch (error?.name) {
    case "NotAllowedError": case "PermissionDeniedError": case "SecurityError":
      return "denied";
    case "NotFoundError": case "DevicesNotFoundError": case "OverconstrainedError": case "ConstraintNotSatisfiedError":
      return "notFound";
    case "NotReadableError": case "TrackStartError": case "AbortError": // the device exists but couldn't be started
      return "inUse";
    case "CameraUnsupportedError":
      return "unsupported";
    default:
      return "unknown";
  }
}

export const describeCameraError = (error) => CAMERA_MESSAGES[cameraErrorKind(error)];

/** Camera stream for these video constraints. If the camera refuses the preferred size/facing (some Windows
    drivers report that as NotReadableError), it is asked once more for any picture. Throws a
    CameraUnsupportedError when the browser has no camera API here (old browser, or a page not on
    localhost/https). */
export async function openCamera(video, mediaDevices = globalThis.navigator?.mediaDevices) {
  if (typeof mediaDevices?.getUserMedia !== "function") {
    const e = new Error("navigator.mediaDevices.getUserMedia is not available in this browser context");
    e.name = "CameraUnsupportedError";
    throw e;
  }
  try {
    return await mediaDevices.getUserMedia({ video });
  } catch (e) {
    if (video !== true && ["OverconstrainedError", "ConstraintNotSatisfiedError", "NotReadableError", "AbortError"].includes(e?.name)) {
      return mediaDevices.getUserMedia({ video: true });
    }
    throw e;
  }
}

/** Turn the camera off (releases the device: on Windows only one app can use a camera at a time). */
export function stopStream(stream) {
  stream?.getTracks().forEach((t) => t.stop());
}

// ---- Photos and frames --------------------------------------------------

export function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(r.result);
    r.onerror = reject;
    r.readAsDataURL(file);
  });
}

/** Mean brightness (0–255) of the current video frame, sampled at low resolution. */
export function measureBrightness(video, canvas) {
  const w = 48, h = 48;
  canvas.width = w; canvas.height = h;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(video, 0, 0, w, h);
  const d = ctx.getImageData(0, 0, w, h).data;
  let sum = 0;
  for (let i = 0; i < d.length; i += 4) sum += 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
  return sum / (w * h);
}

/** Grab the current frame as a mirrored (selfie-style) JPEG data URL. */
export function captureFrame(video) {
  const c = document.createElement("canvas");
  c.width = video.videoWidth; c.height = video.videoHeight;
  const ctx = c.getContext("2d");
  ctx.translate(c.width, 0); ctx.scale(-1, 1);
  ctx.drawImage(video, 0, 0);
  return c.toDataURL("image/jpeg", 0.92);
}
