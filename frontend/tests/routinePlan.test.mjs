// Run with: npm test  (node --test, no extra dependencies)
import { test } from "node:test";
import assert from "node:assert/strict";
import { guidance, mergeRoutine, optionalExtras, routineState } from "../src/services/routinePlan.js";

const step = (id, stepName, extra = {}) => ({ id, handle: id, step: stepName, name: id, url: `https://yuriwoori.com/products/${id}`, ...extra });

test("same product morning and evening is shown once as Morning & Evening", () => {
  const routine = {
    AM: [step("cleanser", "Cleanse"), step("toner", "Tone"), step("spf", "Protect")],
    PM: [step("cleanser", "Cleanse"), step("toner", "Tone"), step("night-cream", "Moisturize")],
  };
  const entries = mergeRoutine(routine);
  assert.deepEqual(entries.map((e) => [e.step.id, e.when]), [
    ["cleanser", "Morning & Evening"], ["toner", "Morning & Evening"], ["night-cream", "Evening"], ["spf", "Morning"],
  ]);
});

test("dedupe uses product id/url, not the product name", () => {
  const entries = mergeRoutine({
    AM: [step("a", "Treat", { name: "Same Name" })],
    PM: [step("b", "Treat", { name: "Same Name" }), { step: "Treat", name: "no identity" }],
  });
  assert.equal(entries.length, 2);
  const byUrl = mergeRoutine({ AM: [{ url: "u1", step: "Tone" }], PM: [{ url: "u1", step: "Tone" }] });
  assert.equal(byUrl.length, 1);
  assert.equal(byUrl[0].when, "Morning & Evening");
});

test("optional extras never repeat a routine product or each other", () => {
  const entries = mergeRoutine({ AM: [step("toner", "Tone")], PM: [] });
  const extras = optionalExtras([
    { id: "toner", routineStep: "mask" }, { id: "mask", routineStep: "mask" }, { id: "mask", routineStep: "mask" },
    { id: "serum", routineStep: "treat" },
  ], entries);
  assert.deepEqual(extras.map((p) => p.id), ["mask"]);
});

const base = { scanId: "scan-1", routine: { AM: [], PM: [] }, matchErrors: [], matchErrorKinds: {} };

test("balanced only on the backend's explicit verdict for this scan", () => {
  assert.equal(routineState({ ...base, analysisStatus: "balanced", activeConcerns: {} }, [], []), "balanced");
});

test("an empty routine without an explicit verdict is a data error, never balanced", () => {
  assert.equal(routineState({ ...base, analysisStatus: null, activeConcerns: {} }, [], []), "data-error");
  assert.equal(routineState({ ...base, analysisStatus: undefined }, [], []), "data-error");
});

test("missing analysis or scan ID is a data error", () => {
  assert.equal(routineState(undefined, [], []), "data-error");
  assert.equal(routineState({ ...base, scanId: null, analysisStatus: "balanced" }, [], []), "data-error");
  assert.equal(routineState({ ...base, routine: null, analysisStatus: "balanced" }, [], []), "data-error");
});

test("server failures are server errors, never balanced", () => {
  assert.equal(routineState({ ...base, routine: null, matchErrors: ["routine"], matchErrorKinds: { routine: "server" } }, [], []), "server-error");
  assert.equal(routineState({ ...base, matchErrors: ["recommendations"], matchErrorKinds: { recommendations: "server" } }, [], []), "server-error");
});

test("an unusable recommendations response is a data error", () => {
  assert.equal(routineState({ ...base, matchErrors: ["recommendations"], matchErrorKinds: { recommendations: "data" } }, [], []), "data-error");
});

test("concerns detected but no product came back is a matching error, not balanced", () => {
  assert.equal(routineState({ ...base, analysisStatus: "concerns", activeConcerns: { redness: "calm visible redness" } }, [], []), "matching-error");
  assert.equal(routineState({ ...base, routine: null, matchErrors: ["routine"], matchErrorKinds: { routine: "matching" } }, [], []), "matching-error");
});

test("a routine with products for a scan with concerns is ready", () => {
  const entries = mergeRoutine({ AM: [step("toner", "Tone")], PM: [] });
  assert.equal(routineState({ ...base, routine: { AM: [entries[0].step], PM: [] }, analysisStatus: "concerns" }, entries, []), "ready");
});

test("products for a scan the backend called balanced is inconsistent data", () => {
  const entries = mergeRoutine({ AM: [step("toner", "Tone")], PM: [] });
  assert.equal(routineState({ ...base, routine: { AM: [entries[0].step], PM: [] }, analysisStatus: "balanced" }, entries, []), "data-error");
});

test("guidance quotes official frequency, otherwise says none is stated; review is a checkpoint, not a promise", () => {
  const official = guidance({ usage: { frequency: "morning_and_night", quote: "Use morning and night." }, when: "Morning & Evening", tags: ["hydration"] });
  assert.match(official.routine, /^Use morning and night, as the official product information recommends\. In your routine: morning & evening\.$/);
  assert.equal(official.review, "Review your hydration and scan measurements after at least 3 weeks of consistent use.");
  assert.match(official.source, /Use morning and night\./);
  const none = guidance({ usage: null, when: "Evening", tags: [] });
  assert.match(none.routine, /doesn't state a specific frequency/);
  assert.match(none.extra, /doesn't state how often/);
  for (const text of [official.routine, official.review, none.routine, none.review]) {
    assert.doesNotMatch(text, /will (see|get|have|improve)|guarantee|results in/i);
  }
});

test("balanced verdict with a maintenance routine shows it; without one, the balanced card", () => {
  const care = { AM: [step("aloe-foam", "Cleanse")], PM: [step("aloe-foam", "Cleanse")] };
  assert.equal(routineState({ ...base, analysisStatus: "balanced", maintenance: care }, [], []), "maintenance");
  assert.equal(routineState({ ...base, analysisStatus: "balanced", maintenance: { AM: [], PM: [] } }, [], []), "balanced");
});

test("a maintenance routine is never shown without the balanced verdict, nor when its request failed", () => {
  const care = { AM: [step("aloe-foam", "Cleanse")], PM: [] };
  assert.equal(routineState({ ...base, analysisStatus: "concerns", maintenance: care }, [], []), "matching-error");
  assert.equal(routineState({ ...base, analysisStatus: null, maintenance: care }, [], []), "data-error");
  assert.equal(routineState({ ...base, analysisStatus: "balanced", matchErrors: ["maintenance"], matchErrorKinds: { maintenance: "server" } }, [], []), "server-error");
  assert.equal(routineState({ ...base, analysisStatus: "balanced", matchErrors: ["maintenance"], matchErrorKinds: { maintenance: "data" } }, [], []), "data-error");
  assert.equal(routineState({ ...base, matchErrors: ["routine"], matchErrorKinds: { routine: "server" }, analysisStatus: "balanced", maintenance: care }, [], []), "server-error");
});
