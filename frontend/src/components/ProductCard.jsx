import { ExternalLink } from "lucide-react";
import { SITE_URL } from "../data/catalogue";
import { ProvidedLogo } from "./Logo";

export function ProductImage({ product, className = "" }) {
  return (
    <div className={`relative flex items-center justify-center overflow-hidden bg-cream border-b border-hairline ${className} group-hover:bg-mist transition-colors duration-500`}>
      {/* Decorative backdrop glow */}
      <div className="absolute inset-0 bg-gradient-to-tr from-jade-soft/10 to-transparent opacity-50" />
      
      {product.image ? (
        <img
          src={product.image} 
          alt={product.name} 
          loading="lazy" 
          className="relative z-10 w-[80%] h-[80%] object-contain transition-transform duration-700 ease-out group-hover:scale-105"
          onError={(e) => { e.currentTarget.style.display = "none"; e.currentTarget.nextSibling.style.display = "flex"; }}
        />
      ) : null}
      
      <div style={{ display: product.image ? "none" : "flex" }} className="relative z-10 flex-col items-center justify-center text-ink-soft opacity-30">
        <ProvidedLogo height={32} />
      </div>
    </div>
  );
}

export function ProductCard({ product, reason, delay = 0 }) {
  return (
    <article 
      className="group flex flex-col h-full overflow-hidden rounded-card bg-white shadow-soft transition-all duration-500 hover:shadow-float hover:-translate-y-1 border border-hairline"
    >
      <ProductImage product={product} className="aspect-[4/5] sm:aspect-square" />
      
      <div className="flex flex-1 flex-col p-5 sm:p-6 relative">
        {product.step && (
          <span className="self-start rounded-pill bg-mist/50 backdrop-blur-sm border border-mist px-3 py-1 text-[10px] font-semibold uppercase tracking-widest text-jade mb-3">
            {product.step}
          </span>
        )}
        
        <h3 className="font-display text-xl sm:text-2xl leading-tight mb-2 group-hover:text-[#004647] transition-colors">{product.name}</h3>
        
        {product.price != null && (
          <p className="text-sm font-semibold tracking-wide text-jade/80 mb-3">
            ₹{product.price.toLocaleString("en-IN")}
          </p>
        )}
        
        {reason && (
          <p className="flex-1 text-sm leading-relaxed text-ink-soft mb-6">{reason}</p>
        )}
        
        <div className="mt-auto pt-4 border-t border-hairline">
          <a
            href={product.url || SITE_URL} target="_blank" rel="noreferrer"
            className="inline-flex items-center gap-2 text-[13px] font-semibold uppercase tracking-wider text-jade hover:text-[#004647] transition-colors"
          >
            View Product <ExternalLink size={14} strokeWidth={2} />
          </a>
        </div>
      </div>
    </article>
  );
}
