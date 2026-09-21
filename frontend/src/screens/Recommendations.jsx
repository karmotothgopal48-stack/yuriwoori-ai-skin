import { Button, Eyebrow } from "../components/Button";
import { ProductCard } from "../components/ProductCard";
import { FOCUS_GUIDANCE } from "../data/mock";

const PER_AREA = 3;

export default function Recommendations({ go, analysis }) {
  const focus = analysis?.profile?.focus ?? [];
  const label = Object.fromEntries((analysis?.concerns ?? []).map((c) => [c.id, c.label]));
  const recs = analysis?.recommendations;

  // Each recommended product is shown once, under the first focus area it helps.
  const shown = new Set();
  const byArea = Object.fromEntries(focus.map((f) => [f, (recs ?? [])
    .filter((p) => p.areas.includes(f) && !shown.has(p.id))
    .slice(0, PER_AREA)
    .map((p) => { shown.add(p.id); return p; })]));

  return (
    <div className="yw-enter mx-auto max-w-6xl px-5 py-12 sm:px-10">
      <Eyebrow>Personalized recommendations</Eyebrow>
      <h2 className="mt-3 text-3xl text-jade sm:text-4xl">What your skin needs most</h2>
      {!recs && <p className="mt-4 text-sm text-ink-soft">We couldn't load product suggestions right now, but your focus areas are below.</p>}
      <div className="mt-8 space-y-6">
        {focus.map((f, i) => (
          <section key={f} className="rounded-3xl bg-cream p-6 sm:p-7">
            <div className="flex gap-5">
              <span className="font-display text-5xl leading-none text-jade-soft">{i + 1}</span>
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-jade">{label[f]}</p>
                <h3 className="mt-1 text-2xl">{FOCUS_GUIDANCE[f]?.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-ink-soft">{FOCUS_GUIDANCE[f]?.body}</p>
              </div>
            </div>
            {recs && byArea[f].length > 0 && (
              <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {byArea[f].map((p) => <ProductCard key={p.id} product={p} reason={p.reason} />)}
              </div>
            )}
            {recs && byArea[f].length === 0 && (
              <p className="mt-5 text-xs text-ink-soft">No specific products matched this area in your scan.</p>
            )}
          </section>
        ))}
      </div>
      <div className="mt-10 flex flex-wrap gap-3">
        <Button onClick={() => go("products")}>View all recommended products</Button>
        <Button variant="ghost" icon={null} onClick={() => go("profile")}>Back to profile</Button>
      </div>
    </div>
  );
}
