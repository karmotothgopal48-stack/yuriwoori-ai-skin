import { Button, Eyebrow } from "../components/Button";
import { ProductCard } from "../components/ProductCard";

export default function Products({ go, analysis }) {
  const items = analysis?.recommendations;

  return (
    <div className="yw-enter mx-auto max-w-6xl px-5 py-12 sm:px-10">
      <Eyebrow>Recommended for you</Eyebrow>
      <h2 className="mt-3 text-3xl text-jade sm:text-4xl">Matched to your skin scan</h2>
      {!items && <p className="mt-8 text-sm text-ink-soft">We couldn't load recommendations right now. Please try the scan again.</p>}
      {items?.length === 0 && <p className="mt-8 text-sm text-ink-soft">No products were a strong match for this scan. Your skin looks well balanced.</p>}
      <div className="mt-8 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {items?.map((p) => <ProductCard key={p.id} product={p} reason={p.reason} />)}
      </div>
      <div className="mt-10 flex flex-wrap gap-3">
        <Button onClick={() => go("routine")}>Build my routine</Button>
        <Button variant="ghost" icon={null} onClick={() => go("recommendations")}>Back</Button>
      </div>
    </div>
  );
}
