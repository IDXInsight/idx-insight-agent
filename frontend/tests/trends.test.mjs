import assert from "node:assert/strict";
import test from "node:test";
import { buildTrends } from "../lib/trends.ts";

const evidence = (period, value, id) => ({
  evidence_id: id, call_id: "call-1", symbol: "BBCA", period,
  field: "profitability.roe", value, unit: "ratio", source_ref: `report:${period}`,
});
const response = items => ({
  peer_comparison: { roe: { metric: "roe", period: "2025", values: { BBCA: 0.235 }, median: 0.22 } },
  evidence: items,
  tool_calls: [{ call_id: "call-1", status: "ok" }],
});

test("builds an ordered line only from two sourced, successful evidence periods", () => {
  const trends = buildTrends(response([evidence("2025", 0.235, "ev-2"), evidence("2024", 0.244, "ev-1")]), ["BBCA"]);
  assert.equal(trends.length, 1);
  assert.deepEqual(trends[0].points.map(point => point.period), ["2024", "2025"]);
  assert.equal(trends[0].points[0].change, null);
  assert.ok(Math.abs(trends[0].points[1].change + 0.009) < 1e-10);
  assert.equal(trends[0].points[0].evidence.evidence_id, "ev-1");
  assert.equal(trends[0].median, 0.22);
});

test("does not invent a trend from one period or an unsuccessful source call", () => {
  assert.deepEqual(buildTrends(response([evidence("2025", 0.235, "ev-2")]), ["BBCA"]), []);
  const failed = response([evidence("2024", 0.244, "ev-1"), evidence("2025", 0.235, "ev-2")]);
  failed.tool_calls[0].status = "error";
  assert.deepEqual(buildTrends(failed, ["BBCA"]), []);
});

test("rejects conflicting observations for the same reporting period", () => {
  const conflicting = response([
    evidence("2024", 0.244, "ev-1"), evidence("2024", 0.2, "ev-conflict"), evidence("2025", 0.235, "ev-2"),
  ]);
  assert.deepEqual(buildTrends(conflicting, ["BBCA"]), []);
});
