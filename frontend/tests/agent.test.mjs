import assert from "node:assert/strict";
import test from "node:test";
import { dayMonth, formatEvidenceValue, isUrl, periodLabel, viewForIntent } from "../lib/agent.ts";

test("maps agent intents to result views", () => {
  assert.equal(viewForIntent("discovery", "peers"), "discovery");
  assert.equal(viewForIntent("peer_comparison", "discovery"), "peers");
  assert.equal(viewForIntent("company_context", "discovery"), "company");
  assert.equal(viewForIntent(null, "peers"), "peers");
});

test("labels quarter-end periods and keeps other periods as given", () => {
  assert.equal(periodLabel("2026-06-30"), "Q2 2026");
  assert.equal(periodLabel("2025"), "2025");
  assert.equal(periodLabel("2026-09-25"), "2026-09-25");
  assert.equal(periodLabel(null), "—");
});

test("formats evidence values by unit", () => {
  const base = { evidence_id: "ev-1", call_id: "c", tool: "t", symbol: "BBCA", period: "2025", field: "f", source_ref: "s", note: null };
  assert.equal(formatEvidenceValue({ ...base, value: 0.235, unit: "ratio" }), "23,5%");
  assert.equal(formatEvidenceValue({ ...base, value: -0.108, unit: "pct_change" }), "-10,8%");
  assert.equal(formatEvidenceValue({ ...base, value: 1500, unit: "IDR" }), "Rp1.500");
  assert.equal(formatEvidenceValue({ ...base, value: null, unit: "ratio" }), "—");
});

test("splits event dates into day and month", () => {
  assert.deepEqual(dayMonth("2026-10-02"), { day: "02", month: "OKT" });
});

test("does not turn script or data source references into links", () => {
  assert.equal(isUrl("https://example.com/filing"), true);
  assert.equal(isUrl("javascript:alert(1)"), false);
  assert.equal(isUrl("data:text/html,<script>alert(1)</script>"), false);
});
