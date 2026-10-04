import assert from "node:assert/strict";
import test from "node:test";
import { indexedDB } from "fake-indexeddb";

globalThis.indexedDB = indexedDB;
const { clearHistory, listHistory, saveHistory } = await import("../lib/history.ts");

test("keeps complete responses for repeated questions across history reloads", async () => {
  const first = { id: "run-1", query: "Kinerja BBCA", askedAt: "2026-10-01T00:00:00Z", response: { briefing: { summary: "Pertama" }, evidence: [{ evidence_id: "e1" }] } };
  const second = { id: "run-2", query: "Kinerja BBCA", askedAt: "2026-10-02T00:00:00Z", response: { briefing: { summary: "Kedua" }, evidence: [{ evidence_id: "e2" }] } };
  await clearHistory();
  try {
    await saveHistory(first);
    await saveHistory(second);
    const restored = await listHistory();
    assert.deepEqual(restored.map(e => e.id), [second.id, first.id]);
    assert.deepEqual(restored[0].response, second.response);
    assert.deepEqual(restored[1].response, first.response);
  } finally {
    await clearHistory();
  }
  assert.deepEqual(await listHistory(), []);
});
