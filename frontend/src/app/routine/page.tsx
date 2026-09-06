"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { getRoutine, RoutineResponse, RoutineStepResponse } from "@/lib/api";

function RoutineBlock({ label, icon, steps }: { label: string; icon: string; steps: RoutineStepResponse[] }) {
  if (steps.length === 0) return null;
  return (
    <div className="mb-6">
      <p className="text-sm font-semibold text-brand-text mb-3">
        {icon} {label}
      </p>
      <div className="flex flex-col gap-3">
        {steps.map((s) => (
          <div key={s.product_id} className="flex gap-3 items-start">
            <span className="w-6 h-6 rounded-full bg-brand-primary text-white text-xs flex items-center justify-center flex-shrink-0 mt-0.5">
              {s.step_order}
            </span>
            <div>
              <p className="text-sm font-medium">{s.product_name}</p>
              <p className="text-xs text-brand-muted">{s.reason}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function RoutinePage() {
  const searchParams = useSearchParams();
  const scanId = searchParams.get("scan_id");
  const [routine, setRoutine] = useState<RoutineResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!scanId) return;
    getRoutine(scanId).then(setRoutine).catch(() => setError("Could not load your routine."));
  }, [scanId]);

  if (error) return <main className="min-h-screen flex items-center justify-center px-8 text-center">{error}</main>;
  if (!routine) return <main className="min-h-screen flex items-center justify-center text-brand-muted">Loading…</main>;

  return (
    <main className="min-h-screen bg-bg-cream px-6 py-6">
      <h1 className="font-display font-semibold text-[27px] mb-1">Your Routine</h1>
      <p className="text-brand-muted text-sm mb-6">Built from today&apos;s profile — adjusts as your skin changes</p>

      <RoutineBlock label="Morning" icon="☀" steps={routine.AM} />
      <RoutineBlock label="Night" icon="🌙" steps={routine.PM} />

      {routine.AM.length === 0 && routine.PM.length === 0 && (
        <p className="text-brand-muted text-sm">
          No routine steps matched yet — your scan didn&apos;t trigger any of the concerns our catalogue currently targets.
        </p>
      )}
    </main>
  );
}