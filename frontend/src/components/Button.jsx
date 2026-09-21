import { ArrowRight } from "lucide-react";

const VARIANTS = {
  primary: "bg-jade text-white hover:bg-[#004647] disabled:bg-jade-line",
  ghost: "border border-jade text-jade hover:bg-mist",
  soft: "bg-mist text-jade hover:bg-aqua",
  light: "bg-white text-jade hover:bg-cream",
};

export function Button({ variant = "primary", icon: Icon = variant === "primary" ? ArrowRight : null, iconLeft: IconLeft, full, className = "", children, ...rest }) {
  return (
    <button
      {...rest}
      className={`inline-flex items-center justify-center gap-2 rounded-full px-7 py-3.5 text-sm font-semibold tracking-wide transition active:scale-[0.98] disabled:cursor-not-allowed ${VARIANTS[variant]} ${full ? "w-full" : ""} ${className}`}
    >
      {IconLeft && <IconLeft size={16} />}
      {children}
      {Icon && <Icon size={16} />}
    </button>
  );
}

export function Eyebrow({ children }) {
  return <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-jade">{children}</p>;
}

export function DemoNote({ children = "Demo data — not generated from your photo." }) {
  return (
    <p className="inline-flex items-center gap-2 rounded-full bg-mist px-3 py-1 text-[11px] font-medium text-ink-soft">
      <span className="h-1.5 w-1.5 rounded-full bg-jade-soft" /> {children}
    </p>
  );
}
