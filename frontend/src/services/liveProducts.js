/* Current product details from the official YuriWoori store, via the backend (GET /v1/catalogue/live,
   which reads yuriwoori.com's public Shopify feed). Nothing about products is hardcoded in the frontend. */
import { api } from "./api";

/** { storeUrl, byHandle: { [handle]: liveProduct }, fetchedAt, stale } for the given Shopify product handles.
    `stale`: the store couldn't be reached just now and the backend's last copy (read at `fetchedAt`) was used. */
export async function fetchLiveProducts(handles) {
  const unique = [...new Set(handles.filter(Boolean))];
  if (!unique.length) return { storeUrl: null, byHandle: {}, fetchedAt: null, stale: false };
  const res = await api(`/catalogue/live?handles=${encodeURIComponent(unique.join(","))}`, { auth: false });
  return {
    storeUrl: res.store_url,
    byHandle: Object.fromEntries(res.products.map((p) => [p.handle, p])),
    fetchedAt: res.fetched_at ?? null,
    stale: res.stale === true,
  };
}
