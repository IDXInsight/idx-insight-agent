import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";

// Both public routes are prerendered by `next build`.
const landing = new URL("../.next/server/app/index.html", import.meta.url);
const workspace = new URL("../.next/server/app/research.html", import.meta.url);

test("landing explains the agent and banking terms", { skip: !existsSync(landing) && "run `npm run build` first" }, () => {
  const html = readFileSync(landing, "utf8");
  assert.match(html, /IDX Insight/);
  assert.match(html, /Temukan konteks/);
  assert.match(html, /Jejak riset yang jelas/);
  assert.match(html, /Telusuri buktinya/);
  assert.match(html, /Return on Equity/);
  assert.match(html, /BOPO/);
  assert.match(html, /Buka ruang riset/);
  assert.doesNotMatch(html, /24[.,]2%|Data ilustrasi|Nilai sintetis/i);
});

test("workspace keeps the research controls and shows no fabricated results", { skip: !existsSync(workspace) && "run `npm run build` first" }, () => {
  const html = readFileSync(workspace, "utf8");
  assert.match(html, /Watchlist kamu/);
  assert.match(html, /Researcher/);
  assert.doesNotMatch(html, /ilustra|Prototipe|sintetis/i);
  assert.doesNotMatch(html, /chatgpt|openai|codex/i);
});


test("flip actions render one label per control", { skip: !existsSync(landing) && "run `npm run build` first" }, () => {
  const landingHtml = readFileSync(landing, "utf8");
  const workspaceHtml = readFileSync(workspace, "utf8");
  const headerAction = landingHtml.match(/<a[^>]*class="[^"]*flip-action flip-link header-action[^"]*"[^>]*>(.*?)<\/a>/s)?.[1];
  const footerAction = landingHtml.match(/<button[^>]*class="[^"]*flip-action wave-footer-cta[^"]*"[^>]*>(.*?)<\/button>/s)?.[1];
  const researchAction = workspaceHtml.match(/<button[^>]*class="[^"]*flip-action primary-button[^"]*"[^>]*>(.*?)<\/button>/s)?.[1];
  assert.ok(headerAction);
  assert.ok(footerAction);
  assert.ok(researchAction);
  assert.equal((headerAction.match(/Buka ruang riset/g) ?? []).length, 1);
  assert.equal((footerAction.match(/Mulai riset baru/g) ?? []).length, 1);
  assert.equal((researchAction.match(/Jalankan riset/g) ?? []).length, 1);
  for (const action of [headerAction, footerAction, researchAction]) {
    assert.doesNotMatch(action, /flip-measure|flip-face--back/);
  }
});


test("workspace exposes three reorderable context widgets", { skip: !existsSync(workspace) && "run `npm run build` first" }, () => {
  const html = readFileSync(workspace, "utf8");
  assert.match(html, /widget-reorder-group/);
  assert.equal((html.match(/class="widget-drag-handle"/g) ?? []).length, 3);
  assert.match(html, /Pindahkan widget/);
  assert.match(html, /Tarik pegangan/);
});
