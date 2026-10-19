/* Sized official product images. Product photos come from the store's Shopify CDN (via the backend's live catalogue)
   at full resolution; the CDN serves any width on request with `width=`, so a thumbnail never downloads the original.
   Other addresses are left exactly as they are. */

const SHOPIFY_HOSTS = ["cdn.shopify.com", "yuriwoori.com", "www.yuriwoori.com"];

const isShopifyCdn = (u) => SHOPIFY_HOSTS.includes(u.hostname) && (u.hostname === "cdn.shopify.com" || u.pathname.startsWith("/cdn/"));

/** The image at `width` CSS pixels wide (Shopify CDN only; anything else is returned unchanged). */
export function sizedImage(url, width) {
  if (!url || !width) return url ?? null;
  let u;
  // absolute or protocol-relative ("//host/...") addresses only: a relative path is one of this app's own files
  try { u = new URL(url.startsWith("//") ? `https:${url}` : url); } catch { return url; }
  if (!isShopifyCdn(u)) return url;
  u.searchParams.set("width", String(Math.round(width)));
  return u.toString();
}

/** { src, srcSet } for an image shown `displayWidth` CSS pixels wide: 1x and 2x (sharp on high-density screens). */
export function productImageSources(url, displayWidth) {
  const src = sizedImage(url, displayWidth);
  if (!src || src === url) return { src: url ?? null, srcSet: undefined };
  return { src, srcSet: `${src} 1x, ${sizedImage(url, displayWidth * 2)} 2x` };
}
