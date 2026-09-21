import { ExternalLink } from "lucide-react";
import { SITE_URL } from "../data/catalogue";

/* Product name, price and image come from the backend catalogue. If the image fails to load,
   a labelled placeholder is shown instead of a fake picture. */
export function ProductImage({ product, className = "" }) {
  return (
    <div className={`flex items-center justify-center overflow-hidden bg-mist ${className}`}>
      {product.image ? (
        <img
          src={product.image} alt={product.name} loading="lazy" className="h-full w-full object-cover"
          onError={(e) => { e.currentTarget.style.display = "none"; e.currentTarget.nextSibling.style.display = "block"; }}
        />
      ) : null}
      <span style={{ display: product.image ? "none" : "block" }} className="px-3 text-center text-[11px] text-ink-soft">
        Product image
      </span>
    </div>
  );
}

export function ProductCard({ product, reason }) {
  return (
    <article className="flex flex-col overflow-hidden rounded-2xl border border-mist bg-white">
      <ProductImage product={product} className="aspect-square" />
      <div className="flex flex-1 flex-col p-5">
        {product.step && (
          <span className="self-start rounded-full bg-mist px-2.5 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide text-jade">
            {product.step}
          </span>
        )}
        <h3 className="mt-3 text-lg leading-snug">{product.name}</h3>
        {product.price != null && <p className="mt-1 text-sm font-semibold text-jade">₹{product.price.toLocaleString("en-IN")}</p>}
        {reason && <p className="mt-2 flex-1 text-[13px] leading-relaxed text-ink-soft">{reason}</p>}
        <a
          href={product.url || SITE_URL} target="_blank" rel="noreferrer"
          className="mt-4 inline-flex items-center gap-1.5 text-sm font-semibold text-jade hover:underline"
        >
          View on yuriwoori.com <ExternalLink size={13} />
        </a>
      </div>
    </article>
  );
}
