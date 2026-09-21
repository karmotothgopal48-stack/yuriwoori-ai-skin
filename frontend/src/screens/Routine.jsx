import { Sun, Moon, AlertTriangle } from "lucide-react";
import { Button, Eyebrow } from "../components/Button";
import { ProductImage } from "../components/ProductCard";

function Block({ title, icon: Icon, steps }) {
  return (
    <div className="min-w-0 rounded-3xl bg-cream p-6 sm:p-7">
      <div className="flex items-center gap-2.5"><Icon size={18} className="text-jade" /><h3 className="text-2xl">{title}</h3></div>
      {steps.length === 0 && <p className="mt-5 text-sm text-ink-soft">No steps for this routine.</p>}
      <ol className="mt-5 divide-y divide-jade-line/60">
        {steps.map((s, i) => (
          <li key={`${s.id}-${i}`} className="flex items-center gap-4 py-4">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-jade text-xs font-semibold text-white">{i + 1}</span>
            <ProductImage product={s} className="h-14 w-14 shrink-0 rounded-xl" />
            <div className="min-w-0">
              {s.step && <p className="text-sm font-semibold">{s.step}</p>}
              <p className="truncate text-xs text-jade">{s.name}</p>
              <p className="text-xs text-ink-soft">{s.reason}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

export default function Routine({ go, analysis }) {
  const routine = analysis?.routine;
  const flags = analysis?.compatibility ?? [];
  return (
    <div className="yw-enter mx-auto max-w-5xl px-5 py-12 sm:px-10">
      <Eyebrow>Personalized routine</Eyebrow>
      <h2 className="mt-3 text-3xl text-jade sm:text-4xl">Your morning and evening ritual</h2>
      {!routine && <p className="mt-8 text-sm text-ink-soft">We couldn't build a routine right now. Please try the scan again.</p>}
      {routine && (
        <div className="mt-8 grid grid-cols-1 gap-5 md:grid-cols-2">
          <Block title="Morning" icon={Sun} steps={routine.AM} />
          <Block title="Evening" icon={Moon} steps={routine.PM} />
        </div>
      )}
      {flags.length > 0 && (
        <div className="mt-5 rounded-3xl border border-mist p-6 sm:p-7">
          <div className="flex items-center gap-2.5"><AlertTriangle size={18} className="text-jade" /><h3 className="text-xl">Using these together</h3></div>
          <ul className="mt-4 space-y-3 text-sm">
            {flags.map((f, i) => (
              <li key={i}><span className="font-semibold">{f.a} + {f.b}</span><span className="block text-ink-soft">{f.text}</span></li>
            ))}
          </ul>
        </div>
      )}
      <div className="mt-10 flex flex-wrap gap-3">
        <Button onClick={() => go("assistant")}>Ask Yuri about my routine</Button>
        <Button variant="ghost" icon={null} onClick={() => go("products")}>Back to products</Button>
      </div>
    </div>
  );
}
