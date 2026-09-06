"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { analyzeScan, SkinProfileResponse } from "@/lib/api";

export default function AnalyzingPage() {
  const searchParams = useSearchParams();
  const scanId = searchParams.get("scan_id");
  const [profile, setProfile] = useState<SkinProfileResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!scanId) return;
    analyzeScan(scanId).then(setProfile).catch(() => setError("Analysis failed."));
  }, [scanId]);

  if (error) return <main className="min-h-screen flex items-center justify-center">{error}</main>;
  if (!profile) return <main className="min-h-screen flex items-center justify-center text-brand-muted">Analyzing…</main>;

  return (
    <main className="min-h-screen p-8">
      <h1 className="font-display text-3xl mb-4">Skin Profile (raw — polished in Step 10)</h1>
      <pre className="bg-bg-cream-alt p-4 rounded-lg text-sm overflow-auto">
        {JSON.stringify(profile, null, 2)}
      </pre>
    </main>
  );
}