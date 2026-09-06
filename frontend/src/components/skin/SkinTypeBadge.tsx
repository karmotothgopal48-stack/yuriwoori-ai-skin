export function SkinTypeBadge({ skinType }: { skinType: string | null }) {
  if (!skinType) return null;

  return (
    <div className="inline-flex items-center gap-2 bg-bg-cream-alt border border-border-soft text-brand-text text-[12.5px] px-3.5 py-1.5 rounded-full mb-4">
      <span className="w-1.5 h-1.5 rounded-full bg-brand-primary" />
      Skin type: <span className="font-medium capitalize">{skinType}</span>
    </div>
  );
}
