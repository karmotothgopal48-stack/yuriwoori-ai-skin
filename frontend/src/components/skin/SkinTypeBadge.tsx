const LABELS: Record<string, string> = {
  oily: "Oily skin",
  dry: "Dry skin",
  combination: "Combination skin",
  normal: "Normal skin",
};

export function SkinTypeBadge({ skinType }: { skinType: string | null }) {
  const label = skinType ? LABELS[skinType] ?? skinType : "Analyzing…";
  return (
    <div className="inline-block px-3.5 py-1.5 rounded-full bg-brand-primary/10 text-brand-primary text-xs font-semibold mb-5">
      {label}
    </div>
  );
}
