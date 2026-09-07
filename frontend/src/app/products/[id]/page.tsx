"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getProductDetail, ProductDetailResponse } from "@/lib/api";

export default function ProductDetailPage() {
  const params = useParams<{ id: string }>();
  const [product, setProduct] = useState<ProductDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showAllIngredients, setShowAllIngredients] = useState(false);

  useEffect(() => {
    getProductDetail(params.id).then(setProduct).catch(() => setError("Could not load this product."));
  }, [params.id]);

  if (error) return <main className="min-h-screen flex items-center justify-center px-8 text-center">{error}</main>;
  if (!product) return <main className="min-h-screen flex items-center justify-center text-brand-muted">Loadingâ€¦</main>;

  const visibleIngredients = showAllIngredients ? product.ingredients : product.ingredients.slice(0, 8);

  return (
    <main className="min-h-screen bg-bg-cream pb-10">
      {product.image_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={product.image_url} alt={product.name} className="w-full h-72 object-cover" />
      ) : (
        <div className="w-full h-72 bg-bg-cream-alt" />
      )}

      <div className="px-6 py-5">
        <p className="text-xs uppercase tracking-widest text-brand-muted mb-2">{product.category}</p>
        <h1 className="font-display text-2xl mb-2">{product.name}</h1>
        {product.price && <p className="text-lg font-semibold text-brand-primary mb-4">â‚¹{product.price}</p>}

        {product.chips.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-5">
            {product.chips.map((chip) => (
              <span key={chip} className="text-xs bg-white border border-border-soft rounded-full px-3 py-1.5">
                {chip}
              </span>
            ))}
          </div>
        )}

        {product.benefits.length > 0 && (
          <div className="mb-6">
            <p className="text-sm font-semibold mb-3">Key benefits</p>
            <div className="flex flex-col gap-3">
              {product.benefits.map((b, i) => (
                <div key={i} className="flex gap-3">
                  <span className="text-xl">{b.icon}</span>
                  <div>
                    <p className="text-sm font-medium">{b.title}</p>
                    <p className="text-xs text-brand-muted">{b.description}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {product.description && (
          <div className="mb-6">
            <p className="text-sm font-semibold mb-2">About this product</p>
            <p className="text-sm text-brand-muted leading-relaxed">{product.description}</p>
          </div>
        )}

        {product.ingredients.length > 0 && (
          <div className="mb-6">
            <p className="text-sm font-semibold mb-2">Full ingredient list (INCI)</p>
            <p className="text-xs text-brand-muted leading-relaxed">
              {visibleIngredients.join(", ")}
              {!showAllIngredients && product.ingredients.length > 8 && "â€¦"}
            </p>
            {product.ingredients.length > 8 && (
              <button
                onClick={() => setShowAllIngredients((v) => !v)}
                className="text-xs text-brand-primary mt-2 underline"
              >
                {showAllIngredients ? "Show less" : `Show all ${product.ingredients.length} ingredients`}
              </button>
            )}
          </div>
        )}

        {product.product_url && (
          <a href={product.product_url}
            target="_blank"
            rel="noopener noreferrer"
            className="block text-center bg-brand-primary text-white px-6 py-3 rounded-full hover:bg-brand-primary-light transition"
          >
            View on YuriWoori.com
          </a>
        )}
      </div>
    </main>
  );
}
