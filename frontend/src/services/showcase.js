import { useEffect, useState } from "react";
import { api } from "./api";

// Official catalogue products used as a quiet brand visual (a cleanse → tone → moisturise trio).
// Names and images come from the catalogue API (data/products_export.csv), never from this file.
const SHOWCASE_HANDLES = ["rice-facial-deep-cleansing-foam", "bubble-soothing-toner", "cloud-cream-korean-aqua-hyaluronic-moisture-cream"];

/** Real catalogue products for decorative strips; [] until loaded or if the catalogue can't be reached. */
export function useShowcaseProducts() {
  const [products, setProducts] = useState([]);
  useEffect(() => {
    let alive = true;
    api("/catalogue/products", { auth: false })
      .then((all) => {
        const byHandle = Object.fromEntries(all.map((p) => [p.handle, p]));
        const picked = SHOWCASE_HANDLES.map((h) => byHandle[h]).filter((p) => p?.image_url);
        if (alive) setProducts(picked.map((p) => ({ id: p.handle, name: p.name, image: p.image_url })));
      })
      .catch(() => {}); // decorative only: callers simply render nothing
    return () => { alive = false; };
  }, []);
  return products;
}
