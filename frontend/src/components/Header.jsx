import { X } from "lucide-react";
import { OfficialLogo } from "./Logo";
import { motion } from "framer-motion";

/* Slim progress header: centred logo with "Step n of total · label" centred beneath it, actions (e.g. the cart)
   and close on the right,
   and one thin line showing completion. Equal side columns keep the centre column truly centred.
   The official website logo scales smoothly with the viewport (≈60px on phones → ≈88px on wide screens) and
   the header height follows the logo's height, so every step renders the same header at a given width. */
const LOGO_W = "clamp(60px, 50px + 2.5vw, 88px)";
export function Header({ onHome, step, total = 11, label, actions }) {
  const isFlow = step > 0 && step <= total;
  const pct = isFlow ? (step / total) * 100 : 0;

  return (
    <header className="sticky top-0 z-40 bg-white/85 backdrop-blur-md border-b border-hairline" style={{ "--logo-w": LOGO_W }}>
      {/* min-height + padding (not a fixed height), so the step line below the logo always has room and never overlaps it */}
      <div className="mx-auto grid min-h-[calc(var(--logo-w)*638/774+18px)] py-2 sm:min-h-[calc(var(--logo-w)*638/774+19px)] max-w-7xl grid-cols-[4.75rem_minmax(0,1fr)_4.75rem] items-center gap-3 px-4 sm:grid-cols-[6rem_minmax(0,1fr)_6rem] sm:px-6">
        <span aria-hidden="true" />

        <div className="flex min-w-0 flex-col items-center justify-center">
          <button onClick={onHome} aria-label="YuriWoori, exit to home" className="shrink-0 rounded-sm focus-visible:outline-2 focus-visible:outline-jade">
            {/* official yuriwoori.com logo (transparent, high resolution), scaled proportionally (never stretched) */}
            <OfficialLogo width="var(--logo-w)" />
          </button>
          {isFlow && (
            <p className="mt-1.5 max-w-full truncate text-center text-[11px] font-semibold uppercase leading-4 tracking-[0.14em] text-ink-soft">
              Step {step} of {total}
              {label && <span className="hidden sm:inline"><span aria-hidden="true" className="mx-2 text-sage-light">·</span><span className="text-jade-deep">{label}</span></span>}
            </p>
          )}
        </div>

        <div className="flex items-center justify-end gap-0.5">
          {actions}
          {isFlow && (
            <button onClick={onHome} aria-label="Exit the skin analysis"
              className="-mr-2 rounded-full p-2 text-ink-soft transition-colors hover:bg-mist hover:text-ink focus-visible:outline-2 focus-visible:outline-jade">
              <X size={20} strokeWidth={1.5} />
            </button>
          )}
        </div>
      </div>

      {isFlow && (
        <div className="absolute inset-x-0 bottom-0 h-[2px] bg-mist/70" role="progressbar" aria-valuemin={1} aria-valuemax={total} aria-valuenow={step}
          aria-valuetext={`Step ${step} of ${total}${label ? `: ${label}` : ""}`}>
          <motion.div className="h-full bg-jade" initial={false} animate={{ width: `${pct}%` }} transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }} />
        </div>
      )}
    </header>
  );
}
