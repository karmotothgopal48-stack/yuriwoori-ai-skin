import { ProvidedLogo } from "./Logo";

export function ProductImage({ product, className = "", bg = "bg-cream" }) {
  return (
    <div className={`relative flex items-center justify-center overflow-hidden ${bg} ${className}`}>
      {product.image ? (
        <img
          src={product.image}
          alt={product.name}
          loading="lazy"
          className="relative z-10 w-[85%] h-[85%] object-contain transition-transform duration-700 ease-out group-hover:scale-105"
          onError={(e) => { e.currentTarget.style.display = "none"; e.currentTarget.nextSibling.style.display = "flex"; }}
        />
      ) : null}
      <div style={{ display: product.image ? "none" : "flex" }} className="relative z-10 flex-col items-center justify-center text-ink-soft opacity-30">
        <ProvidedLogo height={32} />
      </div>
    </div>
  );
}
