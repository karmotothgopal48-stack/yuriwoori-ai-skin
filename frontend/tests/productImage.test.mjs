import { test } from "node:test";
import assert from "node:assert/strict";
import { productImageSources, sizedImage } from "../src/services/productImage.js";

const CDN = "https://cdn.shopify.com/s/files/1/0842/4865/7954/files/144.webp?v=1787701080";

test("Shopify CDN images are requested at the shown width, keeping their version", () => {
  const u = new URL(sizedImage(CDN, 240));
  assert.equal(u.searchParams.get("width"), "240");
  assert.equal(u.searchParams.get("v"), "1787701080");
  assert.equal(u.pathname, "/s/files/1/0842/4865/7954/files/144.webp");
});

test("the store's own /cdn/ addresses are sized too; a width already set is replaced", () => {
  assert.equal(new URL(sizedImage("https://yuriwoori.com/cdn/shop/files/a.webp?width=1500", 300)).searchParams.get("width"), "300");
  assert.equal(new URL(sizedImage("//yuriwoori.com/cdn/shop/files/a.png", 96)).searchParams.get("width"), "96");
});

test("any other address, or no address, is left exactly as it was", () => {
  for (const url of ["https://example.com/a.jpg", "/assets/hero-portrait.webp", "https://yuriwoori.com/products/x", "data:image/png;base64,AAAA"]) {
    assert.equal(sizedImage(url, 200), url, url);
  }
  assert.equal(sizedImage(null, 200), null);
  assert.equal(sizedImage(undefined, 200), null);
  assert.equal(sizedImage(CDN, 0), CDN);
});

test("1x and 2x sources for sharp images on high-density screens", () => {
  const { src, srcSet } = productImageSources(CDN, 112);
  assert.equal(new URL(src).searchParams.get("width"), "112");
  assert.match(srcSet, /width=112 1x, .*width=224 2x$/);
  assert.deepEqual(productImageSources("https://example.com/a.jpg", 112), { src: "https://example.com/a.jpg", srcSet: undefined });
  assert.deepEqual(productImageSources(null, 112), { src: null, srcSet: undefined });
});
