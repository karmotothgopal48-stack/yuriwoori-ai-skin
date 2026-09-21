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
