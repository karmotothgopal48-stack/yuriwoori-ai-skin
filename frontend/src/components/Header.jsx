import { MessageCircle } from "lucide-react";
import { ProvidedLogo } from "./Logo";

/* Logo top-left per Brand Book §2.7 (digital default). */
export function Header({ onHome, onChat, step, total }) {
  return (
    <header className="sticky top-0 z-40 border-b border-mist bg-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-2.5 sm:px-10">
        <button onClick={onHome} aria-label="AI Skin Analysis home"><ProvidedLogo height={60} /></button>
        <div className="flex items-center gap-4">
          {step > 0 && <span className="hidden text-[11px] font-medium text-ink-soft sm:block">Step {step} of {total}</span>}
          <button onClick={onChat} className="inline-flex items-center gap-1.5 rounded-full bg-mist px-4 py-2 text-xs font-semibold text-jade hover:bg-aqua">
            <MessageCircle size={14} /> Ask Yuri
          </button>
        </div>
      </div>
      {step > 0 && (
        <div className="h-0.5 bg-mist"><div className="h-full bg-jade transition-all duration-500" style={{ width: `${(step / total) * 100}%` }} /></div>
      )}
    </header>
  );
}
