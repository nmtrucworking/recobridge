import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request("http://localhost/", { headers: { accept: "text/html" } }),
    { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } },
    { waitUntil() {}, passThroughOnException() {} },
  );
}

test("server-renders the RecoBridge storefront", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<title>RecoBridge/);
  assert.match(html, /Gu của bạn/);
  assert.match(html, /RecoEngine/);
  assert.match(html, /Dành riêng cho/);
  assert.doesNotMatch(html, /codex-preview|Your site is taking shape|react-loading-skeleton/i);
});

test("ships product metadata and removes starter preview code", async () => {
  const [page, layout, packageJson] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
    readFile(new URL("../package.json", import.meta.url), "utf8"),
  ]);

  assert.match(page, /strategy_used|strategy/);
  assert.match(page, /add_to_cart/);
  assert.match(page, /\/api\/recommendations/);
  assert.match(page, /\/api\/events\/exposure/);
  assert.match(page, /\/api\/events\/feedback/);
  assert.match(page, /baseline_session_adaptive|session_feedback/);
  assert.match(page, /Đang xếp hạng lại từ tín hiệu mới/);
  assert.match(page, /Candidate · chưa promote/);
  assert.match(page, /Metadata release đã ẩn danh/);
  assert.match(layout, /og\.png/);
  assert.match(layout, /locale: "vi_VN"/);
  assert.doesNotMatch(packageJson, /react-loading-skeleton/);
  await access(new URL("../public/og.png", import.meta.url));
  await assert.rejects(access(new URL("../app/_sites-preview", import.meta.url)));
});

test("keeps the backend token behind same-origin BFF routes", async () => {
  const proxy = await readFile(new URL("../app/api/_proxy.ts", import.meta.url), "utf8");
  const page = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");

  assert.match(proxy, /RECOMMENDATION_API_TOKEN/);
  assert.match(proxy, /Authorization/);
  assert.doesNotMatch(page, /RECOMMENDATION_API_TOKEN|Authorization:\s*`Bearer/);
});

test("keeps storefront content configurable and interactive state device-local", async () => {
  const [page, catalogModule, storefrontConfig] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../lib/catalog.ts", import.meta.url), "utf8"),
    readFile(new URL("../lib/storefront.json", import.meta.url), "utf8"),
  ]);
  const storefront = JSON.parse(storefrontConfig);

  assert.ok(storefront.profiles.length >= 3);
  assert.ok(storefront.products.length >= storefront.experience.recommendationLimit);
  assert.ok(storefront.profiles.every((profile) => Array.isArray(profile.preferredCategories)));
  assert.match(catalogModule, /fallbackProducts|preferredCategories/);
  assert.match(catalogModule, /SESSION_CATEGORY_AFFINITY|anonymized-dataset/);
  assert.ok(storefront.profiles.slice(0, 2).every((profile) => profile.description.includes("#")));
  assert.doesNotMatch(page, /fallbackIds|useState\(2\)|device_type:\s*"desktop"/);
  assert.match(page, /localStorage|role="dialog"|mobile-navigation|Tìm sản phẩm/);
});
