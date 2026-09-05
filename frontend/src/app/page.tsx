export default function Home() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-6 text-center">
      <span className="text-sm tracking-widest uppercase text-brand-muted mb-4">
        YuriWoori
      </span>
      <h1 className="font-display text-5xl md:text-6xl text-brand-text mb-6">
        Understand your skin.
      </h1>
      <p className="text-brand-muted max-w-md mb-10">
        A camera that becomes a mirror — AI skin analysis, personalized routines,
        and real Korean skincare, matched to you.
      </p>
      <div className="flex gap-4">
        <button className="bg-brand-primary text-white px-6 py-3 rounded-full hover:bg-brand-primary-light transition">
          Start Skin Scan
        </button>
        <button className="border border-border-soft text-brand-text px-6 py-3 rounded-full hover:bg-bg-cream-alt transition">
          Explore Products
        </button>
      </div>
    </main>
  );
}