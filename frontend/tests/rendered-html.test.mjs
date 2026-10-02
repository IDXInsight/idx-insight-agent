import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";

// The workspace page is prerendered by `next build`; run the build before this test.
const page = new URL("../.next/server/app/index.html", import.meta.url);

test("prerendered workspace shows no illustrative data and links no hosting template", { skip: !existsSync(page) && "run `npm run build` first" }, () => {
  const html = readFileSync(page, "utf8");
  assert.match(html, /IDX Insight/);
  assert.match(html, /Temukan konteks/);
  assert.match(html, /Watchlist kamu/);
  assert.match(html, /Researcher/);
  assert.doesNotMatch(html, /ilustra|Prototipe|sintetis/i);
  assert.doesNotMatch(html, /chatgpt|openai|codex/i);
});
