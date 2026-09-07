"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { getProducts, ProductResponse } from "@/lib/api";

export default function ProductsPage() {
  const [products, setProducts] = useState<ProductResponse[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getProducts().then(setProducts).catch(() => setError("Could not load products."));
  }, []);

  if (error) return <main className="min-h-screen flex items-center justify-center">{error}</main>;

  return (
    <main className="min-h-screen bg-bg-cream px-6 py-6">
      <h1 className="font-display font-semibold text-[27px] mb-1">Explore products</h1>
      <p className="text-brand-muted text-sm mb-6">{products.length} real products, synced from YuriWoori</p>

      <div className="grid grid-cols-2 gap-4">
        {products.map((p) => (
          <Link key={p.id} href={`/products/${p.id}`} className="bg-white rounded-xl border border-border-soft overflow-hidden block">
            {p.image_url && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={p.image_url} alt={p.name} className="w-full h-32 object-cover" />
            )}
            <div className="p-3">
              <p className="text-sm font-medium leading-snug mb-1">{p.name}</p>
              <p className="text-xs text-brand-muted mb-1">{p.category}</p>
              {p.price && <p className="text-sm font-semibold text-brand-primary">â‚¹{p.price}</p>}
            </div>
          </Link>
                ))}
      </div>
    </main>
  );
}

