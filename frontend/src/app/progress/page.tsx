"use client";

import { useEffect, useState } from "react";
import { getProgress, ProgressResponse } from "@/lib/api";

const METRIC_LABELS: Record<string, string> = {
  hydration: "Hydration",
  oiliness: "Oiliness",
  texture: "Texture",
  redness: "Redness",
  pigmentation: "Pigmentation",
  blemish_index: "Blemish",
};

export default function ProgressPage() {
  // Placeholder user_id until Step 20 wires real auth — a scan taken while
  // signed in will populate this once accounts exist.
  const DEV_USER_ID = "00000000-0000-0000-0000-000000000000";
  const [data, setData] = useState<ProgressResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getProgress(DEV_USER_ID)
      .then(setData)
      .catch(() => setError("No progress history yet — scan more than once, signed in, to build a trend."));
  }, []);

  if (error) return <main className="min-h-screen flex items-center justify-center px-8 text-center text-brand-muted text-sm">{error}</main>;
  if (!data) return <main className="min-h-screen flex items-center justify-center text-brand-muted">Loading…</main>;

  const latest = data.snapshots[data.snapshots.length - 1];

  return (
    <main className="min-h-screen bg-bg-cream px-6 py-6">
      <h1 className="font-display font-semibold text-[27px] mb-1">Your Skin Journey</h1>
      <p className="text-brand-muted text-sm mb-6">
        {data.snapshots.length} scan{data.snapshots.length !== 1 ? "s" : ""} tracked
      </p>

      <div className="flex flex-col gap-4 mb-6">
        {Object.entries(METRIC_LABELS).map(([key, label]) => {
          const value = latest?.[key as keyof typeof latest] as number | null;
          if (value === null || value === undefined) return null;
          return (
            <div key={key}>
              <div className="flex justify-between text-xs mb-1">
                <span className="font-medium text-brand-text">{label}</span>
                <span className="text-brand-muted">{Math.round(value)}</span>
              </div>
              <div className="h-2 bg-bg-cream-alt rounded-full overflow-hidden">
                <div className="h-full bg-brand-primary rounded-full" style={{ width: `${value}%` }} />
              </div>
            </div>
          );
        })}
      </div>

      {data.meaningful_changes.length > 0 ? (
        <div className="flex flex-col gap-2">
          {data.meaningful_changes.map((c) => (
            <div
              key={c.metric}
              className={`text-xs rounded-lg px-3 py-2.5 border ${
                c.direction === "improved"
                  ? "bg-brand-mint/15 text-brand-primary border-brand-mint/30"
                  : "bg-amber-50 text-amber-700 border-amber-200"
              }`}
            >
              {METRIC_LABELS[c.metric]}: {Math.round(c.start)} → {Math.round(c.latest)} ({c.direction})
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-brand-muted">
          No changes yet beyond normal scan-to-scan variance — check back after a few more scans.
        </p>
      )}
    </main>
  );
}