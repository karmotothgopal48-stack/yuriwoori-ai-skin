"use client";
import { checkout } from "@/lib/api";
import { useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { buildAgentRoutine, ShoppingAgentResponse } from "@/lib/api";

function AgentPageContent() {
  const searchParams = useSearchParams();
  const scanId = searchParams.get("scan_id") ?? undefined;

  const [input, setInput] = useState("I have a ₹2,000 budget. Build my routine.");
  const [result, setResult] = useState<ShoppingAgentResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleBuild = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await buildAgentRoutine(input, scanId);
      setResult(res);
    } catch {
      setError("Couldn't find a budget in that message — try including a number like ₹2000.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-bg-cream px-6 py-6">
      <span className="text-sm tracking-widest uppercase text-brand-muted">Yuri AI</span>
      <h1 className="font-display font-semibold text-[27px] mt-1 mb-1">Shopping Agent</h1>
      <p className="text-brand-muted text-sm mb-5">Tell me your budget, I'll build a real routine within it.</p>

      <div className="flex gap-2 mb-6">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          className="flex-1 border border-border-soft rounded-full px-4 py-2.5 text-sm bg-white outline-none"
        />
        <button
          onClick={handleBuild}
          disabled={loading}
          className="bg-brand-primary text-white px-5 py-2.5 rounded-full text-sm hover:bg-brand-primary-light transition disabled:opacity-50"
        >
          {loading ? "Building…" : "Build"}
        </button>
      </div>

      {error && <p className="text-sm text-red-600 mb-4">{error}</p>}

      {result && (
        <div className="bg-white rounded-xl border border-border-soft p-4">
          {result.items.map((item, i) => (
            <div key={i} className="flex justify-between text-sm py-2 border-b border-border-soft last:border-0">
              <span>{item.name}</span>
              <span className="text-brand-muted">₹{item.price}</span>
            </div>
          ))}
          <div className="flex justify-between text-sm font-semibold py-3">
            <span>Total</span>
            <span>₹{result.total}</span>
          </div>
          <div className="flex flex-wrap gap-2 mb-4">
            {result.tags.map((tag) => (
              <span key={tag} className="text-xs bg-brand-mint/15 text-brand-primary rounded-full px-3 py-1">
                {tag}
              </span>
            ))}
          </div>
          <button
            onClick={async () => {
              try {
                const res = await checkout(result.cart_id);
                window.location.href = res.checkout_url;
              } catch {
                alert("Couldn't start checkout ? some products may not be linked to Shopify yet.");
              }
            }}
            className="w-full bg-brand-primary text-white px-6 py-3 rounded-full hover:bg-brand-primary-light transition"
          >
            Add Complete Routine to Cart
          </button>
        </div>
      )}
    </main>
  );
}

export default function AgentPage() {
  return (
    <Suspense fallback={null}>
      <AgentPageContent />
    </Suspense>
  );
}
