import { test } from "node:test";
import assert from "node:assert/strict";
import { CAMERA_MESSAGES, cameraErrorKind, describeCameraError, openCamera, stopStream } from "../src/services/camera.js";

const domError = (name) => Object.assign(new Error(name), { name });

test("each getUserMedia failure gets its own message", () => {
  const cases = {
    NotAllowedError: "denied", PermissionDeniedError: "denied", SecurityError: "denied",
    NotFoundError: "notFound", DevicesNotFoundError: "notFound", OverconstrainedError: "notFound",
    NotReadableError: "inUse", TrackStartError: "inUse", AbortError: "inUse",
    CameraUnsupportedError: "unsupported", TypeError: "unknown",
  };
  for (const [name, kind] of Object.entries(cases)) {
    assert.equal(cameraErrorKind(domError(name)), kind, name);
    assert.equal(describeCameraError(domError(name)), CAMERA_MESSAGES[kind]);
  }
  assert.equal(cameraErrorKind(undefined), "unknown");
  assert.match(CAMERA_MESSAGES.inUse, /another app or browser/);
  assert.notEqual(CAMERA_MESSAGES.inUse, CAMERA_MESSAGES.notFound); // "in use" is no longer reported as "no camera"
});

test("a browser without the camera API is reported as unsupported", async () => {
  await assert.rejects(openCamera(true, undefined), (e) => cameraErrorKind(e) === "unsupported");
  await assert.rejects(openCamera(true, {}), (e) => cameraErrorKind(e) === "unsupported");
});

test("preferred settings the camera can't start are retried once as any camera", async () => {
  const asked = [];
  const devices = { getUserMedia: async (c) => { asked.push(c); if (asked.length === 1) throw domError("NotReadableError"); return "stream"; } };
  assert.equal(await openCamera({ facingMode: "user" }, devices), "stream");
  assert.deepEqual(asked, [{ video: { facingMode: "user" } }, { video: true }]);
});

test("a camera in use by another app still fails clearly after the retry", async () => {
  const devices = { getUserMedia: async () => { throw domError("NotReadableError"); } };
  await assert.rejects(openCamera({ facingMode: "user" }, devices), (e) => describeCameraError(e) === CAMERA_MESSAGES.inUse);
});

test("permission denied is not retried", async () => {
  let calls = 0;
  const devices = { getUserMedia: async () => { calls += 1; throw domError("NotAllowedError"); } };
  await assert.rejects(openCamera({ facingMode: "user" }, devices), (e) => cameraErrorKind(e) === "denied");
  assert.equal(calls, 1);
});

test("stopping a stream stops every track", () => {
  const stopped = [];
  stopStream({ getTracks: () => [{ stop: () => stopped.push("video") }, { stop: () => stopped.push("audio") }] });
  assert.deepEqual(stopped, ["video", "audio"]);
  stopStream(null); // nothing open: no error
});
