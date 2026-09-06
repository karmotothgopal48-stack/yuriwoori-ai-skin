export function RadialScore({ label, value }: { label: string; value: number }) {
  const r = 27;
  const c = 2 * Math.PI * r;
  const offset = c - (value / 100) * c;

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative w-16 h-16 flex items-center justify-center">
        <svg width="64" height="64" viewBox="0 0 64 64" className="absolute inset-0 -rotate-90">
          <circle cx="32" cy="32" r={r} stroke="#DDD6C8" strokeWidth="4" fill="none" />
          <circle
            cx="32"
            cy="32"
            r={r}
            stroke="#4F6B57"
            strokeWidth="4"
            fill="none"
            strokeDasharray={c}
            strokeDashoffset={offset}
            strokeLinecap="round"
          />
        </svg>
        <span className="text-[15px] font-semibold text-brand-text">{Math.round(value)}</span>
      </div>
      <span className="text-[11px] text-brand-muted text-center">{label}</span>
    </div>
  );
}export function RadialScore({ label, value }: { label: string; value: number }) {
  const r = 27;
  const c = 2 * Math.PI * r;
  const offset = c - (value / 100) * c;

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative w-16 h-16 flex items-center justify-center">
        <svg width="64" height="64" viewBox="0 0 64 64" className="absolute inset-0 -rotate-90">
          <circle cx="32" cy="32" r={r} stroke="#DDD6C8" strokeWidth="4" fill="none" />
          <circle
            cx="32"
            cy="32"
            r={r}
            stroke="#4F6B57"
            strokeWidth="4"
            fill="none"
            strokeDasharray={c}
            strokeDashoffset={offset}
            strokeLinecap="round"
          />
        </svg>
        <span className="text-[15px] font-semibold text-brand-text">{Math.round(value)}</span>
      </div>
      <span className="text-[11px] text-brand-muted text-center">{label}</span>
    </div>
  );
}