"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { analyzeScan } from "@/lib/api";

function AnalyzingContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const scanId = searchParams.get("scan_id");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!scanId) return;
    analyzeScan(scanId)
      .then(() => router.replace(`/scan/result?scan_id=${scanId}`))
      .catch(() => setError("Analysis failed. Please try scanning again."));
  }, [scanId, router]);

  if (error) {
    return <main className="min-h-screen flex items-center justify-center px-8 text-center">{error}</main>;
  }

  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-8">
      <div className="w-24 h-24 rounded-full border border-border-soft relative mb-8 flex items-center justify-center">
        <div className="absolute inset-[-1.5px] rounded-full border border-transparent border-t-brand-primary border-r-brand-primary animate-spin" />
        <span className="font-display text-2xl text-brand-text">AI</span>
      </div>
      <p className="text-brand-muted text-sm">Analyzing your skin…</p>
    </main>
  );
}

export default function AnalyzingPage() {
  // useSearchParams() requires a Suspense boundary around the component that
  // calls it, or `next build` fails to prerender this route.
  return (
    <Suspense fallback={null}>
      <AnalyzingContent />
    </Suspense>
  );
}
