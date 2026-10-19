import { test } from "node:test";
import assert from "node:assert/strict";
import { describeFailure, detailText, NETWORK_MESSAGE } from "../src/services/apiErrors.js";

test("no response at all is a connection problem", () => {
  assert.deepEqual(describeFailure(0), { kind: "network", message: NETWORK_MESSAGE });
});

test("error statuses are never reported as 'server not running'", () => {
  for (const status of [400, 401, 404, 409, 422, 500, 503]) {
    const f = describeFailure(status, status === 404 ? "Not Found" : null);
    assert.notEqual(f.kind, "network", String(status));
    assert.notEqual(f.message, NETWORK_MESSAGE, String(status));
  }
  assert.equal(describeFailure(404, "Not Found").kind, "not-found");
  assert.match(describeFailure(404, "Not Found").message, /\(404\)/);
  assert.equal(describeFailure(500).kind, "server");
  assert.equal(describeFailure(503, "Database is unavailable.").message, "Database is unavailable.");
});

test("validation keeps the backend's own explanation", () => {
  const detail = detailText([{ msg: "String should match pattern" }, { msg: "Field required" }]);
  assert.deepEqual(describeFailure(422, detail), { kind: "validation", message: "String should match pattern; Field required" });
  assert.equal(describeFailure(400, "Please accept the privacy notice to continue.").message, "Please accept the privacy notice to continue.");
});

test("rate limiting is its own case, not an outage or a generic failure", () => {
  const f = describeFailure(429, "Too Many Requests");
  assert.equal(f.kind, "rate-limit");
  assert.notEqual(f.message, NETWORK_MESSAGE);
});

test("a saved session is dropped only when the server rejects it, never because the server is unreachable", async () => {
  const { sessionRejected } = await import("../src/services/apiErrors.js");
  assert.equal(sessionRejected(401), true);
  assert.equal(sessionRejected(403), true);
  for (const status of [0, 500, 502, 503, 504, 404, 429]) assert.equal(sessionRejected(status), false, String(status));
});
