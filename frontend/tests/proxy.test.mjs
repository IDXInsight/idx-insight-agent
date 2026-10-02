import assert from "node:assert/strict";
import test from "node:test";
import { clientIp, errorForBackend, proxyStatus } from "../lib/proxy.ts";

test("prefers the client IP headers Vercel sets itself", () => {
  const headers = new Headers({
    "x-forwarded-for": "198.51.100.9, 10.0.0.1",
    "x-vercel-forwarded-for": "203.0.113.7",
  });
  assert.equal(clientIp(headers), "203.0.113.7");
  assert.equal(clientIp(new Headers({ "x-forwarded-for": "2001:db8::1, 10.0.0.1" })), "2001:db8::1");
  assert.equal(clientIp(new Headers()), null);
});

test("ignores values that are not IP addresses", () => {
  assert.equal(clientIp(new Headers({ "x-real-ip": "<script>alert(1)</script>" })), null);
  assert.equal(clientIp(new Headers({ "x-real-ip": "a".repeat(80) })), null);
});

test("maps backend replies onto user-facing error codes", () => {
  assert.equal(errorForBackend(429, { error: "daily_limit" }), "daily_limit");
  assert.equal(errorForBackend(429, { error: "rate_limited" }), "rate_limited");
  assert.equal(errorForBackend(429, null), "rate_limited");
  assert.equal(errorForBackend(422, {}), "invalid_request");
  assert.equal(errorForBackend(503, { error: "storage_unavailable" }), "backend_unavailable");
  assert.equal(errorForBackend(401, { error: "unauthorized" }), "backend_error");
  assert.equal(proxyStatus.daily_limit, 429);
});
