import assert from "node:assert/strict";
import test from "node:test";
import { BodyTooLargeError, clientIp, errorForBackend, limitedJsonBody, proxyStatus, sameOriginRequest } from "../lib/proxy.ts";

test("prefers the client IP headers Vercel sets itself", () => {
  const headers = new Headers({
    "x-forwarded-for": "198.51.100.9, 10.0.0.1",
    "x-vercel-forwarded-for": "203.0.113.7",
  });
  assert.equal(clientIp(headers), null); // A direct caller can forge these headers.
  assert.equal(clientIp(headers, true), "203.0.113.7");
  assert.equal(clientIp(new Headers({ "x-forwarded-for": "2001:db8::1, 10.0.0.1" }), true), "2001:db8::1");
  assert.equal(clientIp(new Headers()), null);
});

test("ignores values that are not IP addresses", () => {
  assert.equal(clientIp(new Headers({ "x-vercel-forwarded-for": "<script>alert(1)</script>" }), true), null);
  assert.equal(clientIp(new Headers({ "x-vercel-forwarded-for": "a:b:c" }), true), null);
  assert.equal(clientIp(new Headers({ "x-vercel-forwarded-for": "a".repeat(80) }), true), null);
});

test("blocks cross-origin browser requests to the paid agent endpoint", () => {
  const url = "https://idx-insight.example/api/agent/query";
  assert.equal(sameOriginRequest(new Request(url, { headers: { origin: "https://idx-insight.example", "sec-fetch-site": "same-origin" } })), true);
  assert.equal(sameOriginRequest(new Request(url, { headers: { origin: "https://attacker.example", "sec-fetch-site": "cross-site" } })), false);
  assert.equal(sameOriginRequest(new Request(url, { headers: { origin: "null" } })), false);
  assert.equal(sameOriginRequest(new Request(url, { headers: { "sec-fetch-site": "same-site" } })), false);
});

test("accepts the host the page was opened on when the dev server reports localhost", () => {
  const url = "http://localhost:3000/api/agent/query";
  const local = (origin, host) => new Request(url, { headers: { origin, host, "sec-fetch-site": "same-origin" } });
  assert.equal(sameOriginRequest(local("http://127.0.0.1:3000", "127.0.0.1:3000")), true);
  assert.equal(sameOriginRequest(local("http://localhost:3000", "localhost:3000")), true);
  assert.equal(sameOriginRequest(local("http://attacker.example", "127.0.0.1:3000")), false);
  assert.equal(sameOriginRequest(local("https://127.0.0.1:3000", "127.0.0.1:3000")), false);
});

test("caps JSON request bytes even without a Content-Length header", async () => {
  const url = "https://idx-insight.example/api/agent/query";
  const small = new Request(url, { method: "POST", body: JSON.stringify({ query: "Bandingkan BBCA dan BBRI" }) });
  assert.deepEqual(await limitedJsonBody(small), { query: "Bandingkan BBCA dan BBRI" });
  const huge = new Request(url, { method: "POST", body: JSON.stringify({ query: "A".repeat(9000) }) });
  await assert.rejects(limitedJsonBody(huge), BodyTooLargeError);
  const declared = new Request(url, { method: "POST", headers: { "content-length": "9000" }, body: "{}" });
  await assert.rejects(limitedJsonBody(declared), BodyTooLargeError);
});

test("maps backend replies onto user-facing error codes", () => {
  assert.equal(errorForBackend(429, { error: "daily_limit" }), "daily_limit");
  assert.equal(errorForBackend(429, { error: "rate_limited" }), "rate_limited");
  assert.equal(errorForBackend(429, { error: { code: "429", message: "rate limit" } }), "rate_limited");
  assert.equal(errorForBackend(429, null), "rate_limited");
  assert.equal(errorForBackend(422, {}), "invalid_request");
  assert.equal(errorForBackend(503, { error: "storage_unavailable" }), "backend_unavailable");
  assert.equal(errorForBackend(401, { error: "unauthorized" }), "backend_error");
  assert.equal(proxyStatus.daily_limit, 429);
});
