"use client";
import { checkCompatibility, CompatibilityFlagResponse } from "@/lib/api";
import { useEffect, useState , Suspense} from "react";
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

function RoutinePage() {
  const searchParams = useSearchParams();
  const scanId = searchParams.get("scan_id");
  const [routine, setRoutine] = useState<RoutineResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!scanId) return;
    getRoutine(scanId).then(setRoutine).catch(() => setError("Could not load your routine."));
  }, [scanId]);
  const [flags, setFlags] = useState<CompatibilityFlagResponse[]>([]);

  useEffect(() => {
    if (!scanId) return;
    checkCompatibility(scanId).then(setFlags).catch(() => {});
  }, [scanId]);

  if (error) return <main className="min-h-screen flex items-center justify-center px-8 text-center">{error}</main>;
  if (!routine) return <main className="min-h-screen flex items-center justify-center text-brand-muted">Loadingâ€¦</main>;

  return (
    <main className="min-h-screen bg-bg-cream px-6 py-6">
      <h1 className="font-display font-semibold text-[27px] mb-1">Your Routine</h1>
      <p className="text-brand-muted text-sm mb-6">Built from today&apos;s profile â€” adjusts as your skin changes</p>
      {flags.length > 0 && (
        <div className="mb-6 flex flex-col gap-2">
          {flags.map((f, i) => {
            const color =
              f.relationship_type === "synergistic"
                ? "bg-brand-mint/15 text-brand-primary border-brand-mint/30"
                : f.relationship_type === "avoid_same_routine"
                ? "bg-red-50 text-red-700 border-red-200"
                : "bg-amber-50 text-amber-700 border-amber-200";

            return (
              <div
                key={i}
                className={`text-xs border rounded-lg px-3 py-2.5 ${color}`}
              >
                <span className="font-semibold">
                  {f.product_a_name} + {f.product_b_name}:
                </span>{" "}
                {f.explanation}
              </div>
            );
          })}
        </div>
      )}

      <RoutineBlock label="Morning" icon="â˜€" steps={routine.AM} />
      <RoutineBlock label="Night" icon="ðŸŒ™" steps={routine.PM} />

      {routine.AM.length === 0 && routine.PM.length === 0 && (
        <p className="text-brand-muted text-sm">
          No routine steps matched yet â€” your scan didn&apos;t trigger any of the concerns our catalogue currently targets.
        </p>
      )}
    </main>
  );
}
export default function RoutinePageWithSuspense() {
  return (
    <Suspense fallback={null}>
      <RoutinePage />
    </Suspense>
  );
}
