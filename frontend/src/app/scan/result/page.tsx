"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { getScanProfile, SkinProfileResponse } from "@/lib/api";
import { RadialScore } from "@/components/skin/RadialScore";
import { SkinTypeBadge } from "@/components/skin/SkinTypeBadge";

export default function ResultPage() {
  const searchParams = useSearchParams();
  const scanId = searchParams.get("scan_id");
  const [profile, setProfile] = useState<SkinProfileResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!scanId) return;
    getScanProfile(scanId).then(setProfile).catch(() => setError("Could not load this scan."));
  }, [scanId]);

  if (error) return <main className="min-h-screen flex items-center justify-center px-8 text-center">{error}</main>;
  if (!profile) return <main className="min-h-screen flex items-center justify-center text-brand-muted">Loading…</main>;

  const scores = [
    { label: "Hydration", val: profile.hydration ?? 0 },
    { label: "Oiliness", val: profile.oiliness ?? 0 },
    { label: "Texture", val: profile.texture ?? 0 },
    { label: "Redness", val: profile.redness ?? 0 },
    { label: "Pigmentation", val: profile.pigmentation ?? 0 },
    { label: "Blemish", val: profile.blemish_index ?? 0 },
  ];

  return (
    <main className="min-h-screen bg-bg-cream flex flex-col">
      <div className="flex justify-between items-center px-6 pt-6">
        <span className="text-sm tracking-widest uppercase text-brand-muted">YuriWoori</span>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5">
        <div className="mb-5">
          <h1 className="font-display font-semibold text-[27px] mb-1">Your Skin Profile</h1>
          <p className="text-[12.5px] text-brand-muted">From today's scan, front + side angles combined</p>
        </div>

        <SkinTypeBadge skinType={profile.skin_type} />

        <div className="grid grid-cols-3 gap-x-2.5 gap-y-3.5 mb-5">
          {scores.map((s) => (
            <RadialScore key={s.label} label={s.label} value={s.val} />
          ))}
        </div>

        <div className="text-[11.5px] text-brand-muted bg-bg-cream-alt border border-border-soft rounded-lg px-3.5 py-3 leading-relaxed mb-6">
          This is a cosmetic skin-texture reading, not a medical or dermatological diagnosis. See a
          dermatologist for any persistent skin concern.
        </div>

        <Link
          href={`/passport?scan_id=${scanId}`}
          className="block text-center bg-brand-primary text-white px-6 py-3 rounded-full hover:bg-brand-primary-light transition"
        >
          Save to My Skin Passport
        </Link>
      </div>
    </main>
  );
}