/* The customer's selfie on their own skin-profile report, held in browser memory only (NO SELFIE STORAGE).
   The capture (a data: URL in React state) becomes an in-memory Blob behind an object URL, bound to the scan it
   was analysed for. Nothing here writes to localStorage, sessionStorage, IndexedDB, cookies or caches, and nothing
   is sent to the server: once released (new scan, home, sign-out) or the page is closed, the photo is gone. */

/** Blob for a base64 data: URL, or null for anything else (no network fetch, so nothing can be re-downloaded). */
export function dataUrlToBlob(dataUrl) {
  const m = typeof dataUrl === "string" ? /^data:([^;,]*)(?:;[^,]*)?;base64,(.*)$/s.exec(dataUrl) : null;
  if (!m) return null;
  try {
    const bin = atob(m[2]);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return new Blob([bytes], { type: m[1] || "image/jpeg" });
  } catch {
    return null;
  }
}

/** { scanId, url } for the report of `scanId`, or null when there is no usable photo or scan. */
export function createReportPhoto(dataUrl, scanId, urls = URL) {
  if (!scanId) return null;
  const blob = dataUrlToBlob(dataUrl);
  return blob ? { scanId, url: urls.createObjectURL(blob) } : null;
}

/** Revokes the object URL, so the browser frees the image. Safe to call with null or twice. */
export function releaseReportPhoto(reportPhoto, urls = URL) {
  if (reportPhoto?.url) urls.revokeObjectURL(reportPhoto.url);
}

/** The photo's URL only for the report of that same scan: never another scan's (or customer's) photo. */
export const reportPhotoFor = (reportPhoto, analysis) =>
  reportPhoto && analysis?.scanId && reportPhoto.scanId === analysis.scanId ? reportPhoto.url : null;
