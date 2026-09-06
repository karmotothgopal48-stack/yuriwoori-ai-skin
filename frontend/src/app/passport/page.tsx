"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { saveToPassport, getPassport, PassportResponse } from "@/lib/api";

function PassportContent() {
  const searchParams = useSearchParams();
  const scanId = searchParams.get("scan_id");
  const [passport, setPassport] = useState<PassportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (scanId) {
      saveToPassport(scanId).then(setPassport).catch(() => setError("Could not save to passport."));
    } else {
      getPassport().then(setPassport).catch(() => setError("No passport yet — scan first."));
    }
  }, [scanId]);

  if (error) return <main className="min-h-screen flex items-center justify-center px-8 text-center">{error}</main>;
  if (!passport) return <main className="min-h-screen flex items-center justify-center text-brand-muted">Loading…</main>;

  return (
    <main className="min-h-screen bg-bg-cream px-6 py-6">
      <h1 className="font-display font-semibold text-[27px] mb-5">My Skin Passport</h1>

      <div className="bg-[#15140F] text-[#F7F4EE] rounded-2xl px-6 py-6 relative overflow-hidden mb-5">
        <div className="absolute -top-10 -right-10 w-40 h-40 rounded-full border border-white/15" />
        <p className="text-[11px] tracking-wide text-[#B8C4BB] mb-1.5 relative">SKIN PASSPORT</p>
        <p className="font-display text-[26px] mb-4 relative capitalize">{passport.skin_type ?? "—"}</p>

        <div className="flex items-end gap-2 mb-4 relative">
          <span className="font-display text-4xl">{Math.round(passport.overall_score ?? 0)}</span>
          <span className="text-xs text-[#B8C4BB] mb-1">overall score</span>
        </div>

        <div className="flex flex-wrap gap-2 relative">
          {passport.top_concerns.map((c) => (
            <span key={c} className="text-xs bg-white/10 border border-white/15 rounded-full px-3 py-1 capitalize">
              {c}
            </span>
          ))}
        </div>
      </div>

      <p className="text-brand-muted text-xs">
        {passport.last_scanned_at
          ? `Last scanned ${new Date(passport.last_scanned_at).toLocaleDateString()}`
          : ""}
      </p>
    </main>
  );
}

export default function PassportPage() {
  // useSearchParams() requires a Suspense boundary around the component that
  // calls it, or `next build` fails to prerender this route.
  return (
    <Suspense fallback={null}>
      <PassportContent />
    </Suspense>
  );
}
