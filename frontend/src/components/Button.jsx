import { ArrowRight, Loader2 } from "lucide-react";
import { motion } from "framer-motion";

const VARIANTS = {
  primary: "bg-jade text-cream hover:bg-[#004647] hover:shadow-bloom disabled:bg-jade-line disabled:hover:shadow-none focus-visible:ring-2 focus-visible:ring-jade focus-visible:ring-offset-2 focus-visible:ring-offset-cream border border-transparent",
  secondary: "border border-jade text-jade hover:bg-mist focus-visible:ring-2 focus-visible:ring-jade focus-visible:ring-offset-2 focus-visible:ring-offset-cream",
  tertiary: "text-jade hover:text-[#004647] bg-transparent group focus-visible:ring-2 focus-visible:ring-jade focus-visible:ring-offset-2 focus-visible:ring-offset-cream rounded-sm px-2 py-1",
  ghost: "bg-mist text-jade hover:bg-aqua focus-visible:ring-2 focus-visible:ring-jade focus-visible:ring-offset-2",
};

export function Button({ 
  variant = "primary", 
  icon: Icon = variant === "primary" ? ArrowRight : null, 
  iconLeft: IconLeft, 
  full, 
  loading,
  className = "", 
  children, 
  ...rest 
}) {
  const isTertiary = variant === "tertiary";
  const baseClasses = isTertiary 
    ? "inline-flex items-center gap-1.5 text-sm font-semibold tracking-wide transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
    : "inline-flex items-center justify-center gap-2 rounded-pill min-h-[48px] px-8 py-3 text-sm font-semibold tracking-wide transition-all active:scale-[0.98] disabled:cursor-not-allowed disabled:active:scale-100";

  return (
    <button
      {...rest}
      disabled={loading || rest.disabled}
      className={`${baseClasses} ${VARIANTS[variant]} ${full && !isTertiary ? "w-full" : ""} ${className}`}
    >
      {loading ? (
        <Loader2 className="animate-spin" size={18} />
      ) : (
        <>
          {IconLeft && <IconLeft size={18} strokeWidth={1.5} />}
          {isTertiary ? (
            <span className="relative">
              {children}
              <span className="absolute -bottom-1 left-0 w-0 h-[1.5px] bg-jade transition-all duration-300 group-hover:w-full" />
            </span>
          ) : (
            children
          )}
          {Icon && !isTertiary && <Icon size={18} strokeWidth={1.5} />}
          {Icon && isTertiary && <Icon size={16} strokeWidth={1.5} className="transition-transform group-hover:translate-x-1" />}
        </>
      )}
    </button>
  );
}

export function Eyebrow({ children, className = "" }) {
  return <p className={`eyebrow ${className}`}>{children}</p>;
}
