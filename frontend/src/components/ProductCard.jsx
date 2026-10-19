import { useState } from "react";
import { HeartMark } from "./Logo";
import { productImageSources } from "../services/productImage";

/* An official product photo (Shopify CDN via the live catalogue), requested at the width it is shown (`size`, CSS px)
   with a 2x source for sharp screens. A soft placeholder shows while it loads; if there is no image or it fails,
   the YuriWoori heart mark stands in (never another product's photo). */
export function ProductImage({ product, className = "", bg = "bg-cream", size = 160 }) {
  const { src, srcSet } = productImageSources(product.image, size);
  // load state belongs to one address: when the live catalogue swaps the image in, it starts loading afresh
  const [load, setLoad] = useState({ src: null, status: "loading" });
  const status = load.src === src ? load.status : "loading";
  const showImage = src && status !== "failed";
  return (
    <div className={`relative flex items-center justify-center overflow-hidden ${bg} ${className}`}>
      {showImage && status === "loading" && <span aria-hidden="true" className="absolute inset-0 animate-pulse bg-mist/60" />}
      {showImage ? (
        <img
          src={src}
          srcSet={srcSet}
          alt={product.name}
          width={size}
          height={size}
          loading="lazy"
          decoding="async"
          onLoad={() => setLoad({ src, status: "loaded" })}
          onError={() => setLoad({ src, status: "failed" })}
          className={`relative z-10 h-[85%] w-[85%] object-contain transition-[opacity,transform] duration-500 ease-out group-hover:scale-105 ${status === "loaded" ? "opacity-100" : "opacity-0"}`}
        />
      ) : (
        <span role="img" aria-label={product.name} className="relative z-10 flex items-center justify-center opacity-40">
          <HeartMark className="h-8" />
        </span>
      )}
    </div>
  );
}
