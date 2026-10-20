import { test } from "node:test";
import assert from "node:assert/strict";
import { createReportPhoto, dataUrlToBlob, releaseReportPhoto, reportPhotoFor } from "../src/services/reportPhoto.js";

const JPEG = "data:image/jpeg;base64," + Buffer.from([0xff, 0xd8, 0xff, 0xe0, 1, 2, 3, 0xff, 0xd9]).toString("base64");

// Records object URLs instead of creating real ones, so each test can check what was created and revoked.
function fakeUrls() {
  const live = new Set();
  let n = 0;
  return {
    live,
    createObjectURL: (blob) => { assert.ok(blob instanceof Blob); const u = `blob:test/${++n}`; live.add(u); return u; },
    revokeObjectURL: (u) => { live.delete(u); },
  };
}

test("the capture becomes an in-memory Blob with its own bytes and type", async () => {
  const blob = dataUrlToBlob(JPEG);
  assert.equal(blob.type, "image/jpeg");
  assert.deepEqual([...new Uint8Array(await blob.arrayBuffer())], [0xff, 0xd8, 0xff, 0xe0, 1, 2, 3, 0xff, 0xd9]);
});

test("only base64 data: URLs are accepted: nothing is fetched from a URL or path", () => {
  for (const bad of [null, undefined, "", "https://example.com/selfie.jpg", "/uploads/scan/front.jpg", "blob:x/1", "data:image/jpeg,raw", "data:image/jpeg;base64,%%%"]) {
    assert.equal(dataUrlToBlob(bad), null, String(bad));
  }
});

test("a report photo is bound to its scan and shown only for that scan", () => {
  const urls = fakeUrls();
  const rp = createReportPhoto(JPEG, "scan-a", urls);
  assert.equal(rp.scanId, "scan-a");
  assert.equal(reportPhotoFor(rp, { scanId: "scan-a" }), rp.url);
  assert.equal(reportPhotoFor(rp, { scanId: "scan-b" }), null); // another scan never shows this photo
  assert.equal(reportPhotoFor(rp, null), null);
  assert.equal(reportPhotoFor(null, { scanId: "scan-a" }), null); // released: the report shows the placeholder
});

test("no photo without a scan id or a usable capture", () => {
  const urls = fakeUrls();
  assert.equal(createReportPhoto(JPEG, null, urls), null);
  assert.equal(createReportPhoto("https://example.com/a.jpg", "scan-a", urls), null);
  assert.equal(urls.live.size, 0);
});

test("releasing revokes the object URL; releasing nothing or twice is harmless", () => {
  const urls = fakeUrls();
  const rp = createReportPhoto(JPEG, "scan-a", urls);
  assert.equal(urls.live.size, 1);
  releaseReportPhoto(rp, urls);
  releaseReportPhoto(rp, urls);
  releaseReportPhoto(null, urls);
  assert.equal(urls.live.size, 0);
});
