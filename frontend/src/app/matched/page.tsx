"use client";

import { useEffect, useState , Suspense} from "react";
import { useSearchParams } from "next/navigation";
import { getRecommendations, RecommendationResponse } from "@/lib/api";

function MatchedPage() {
  const searchParams = useSearchParams();
  const scanId = searchParams.get("scan_id");
  const [recs, setRecs] = useState<RecommendationResponse[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!scanId) return;
    getRecommendations(scanId).then(setRecs).catch(() => setError("Could not load recommendations."));
  }, [scanId]);

  if (error) return <main className="min-h-screen flex items-center justify-center px-8 text-center">{error}</main>;

  return (
    <main className="min-h-screen bg-bg-cream px-6 py-6">
      <h1 className="font-display font-semibold text-[27px] mb-1">Matched for you</h1>
      <p className="text-brand-muted text-sm mb-6">Ranked against your current concerns</p>

      {recs.length === 0 && (
        <p className="text-brand-muted text-sm">
          No strong matches yet â€” your scan didn&apos;t show concerns our current catalogue targets directly.
        </p>
      )}

      <div className="flex flex-col gap-3">
        {recs.map((r) => (
          <div key={r.product_id} className="bg-white rounded-xl border border-border-soft p-3 flex gap-3">
            {r.image_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={r.image_url} alt={r.name} className="w-16 h-16 rounded-lg object-cover flex-shrink-0" />
            ) : (
              <div className="w-16 h-16 rounded-lg bg-bg-cream-alt flex-shrink-0" />
            )}
            <div className="flex-1">
              <p className="text-sm font-medium leading-snug mb-0.5">{r.name}</p>
              {r.price && <p className="text-sm font-semibold text-brand-primary mb-1">â‚¹{r.price}</p>}
              <p className="text-xs text-brand-muted">{r.match_reason}</p>
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}
export default function MatchedPageWithSuspense() {
  return (
    <Suspense fallback={null}>
      <MatchedPage />
    </Suspense>
  );
}
