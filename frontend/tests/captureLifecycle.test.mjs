import { test } from "node:test";
import assert from "node:assert/strict";
import { CAPTURE_SCREENS, keepsCapture } from "../src/services/captureLifecycle.js";

test("the captured photo may stay only while Review or the analysis is on screen", () => {
  assert.deepEqual([...CAPTURE_SCREENS], ["review", "processing"]);
  assert.equal(keepsCapture("review"), true);
  assert.equal(keepsCapture("processing"), true); // includes "Try again" after a failed analysis
});

test("exit, restart and completion screens release it", () => {
  // home / logo / ✕ (exit), details and camera or tips (restart / retake), results and routine (completed), chat
  for (const screen of ["start", "about", "permission", "tips", "camera", "profile", "routine", "assistant"]) {
    assert.equal(keepsCapture(screen), false, screen);
  }
});

test("unknown or missing screens release it (fail closed)", () => {
  for (const screen of [undefined, null, "", "report", "admin", "Review"]) assert.equal(keepsCapture(screen), false, String(screen));
});

test("the rule can't be changed at runtime", () => {
  assert.throws(() => { CAPTURE_SCREENS.push("start"); });
});
