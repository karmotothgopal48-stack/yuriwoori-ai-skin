import { useState } from "react";
import { Camera, Sparkles, Sun } from "lucide-react";
import { Button, Eyebrow } from "../components/Button";
import { FullLockup } from "../components/Logo";
import { ProductImage } from "../components/ProductCard";
import { useShowcaseProducts } from "../services/showcase";

// Step 1: gender + age to personalise the analysis. Name, WhatsApp, email and consent are asked just before
// this step (screens/Signup.jsx, see NEEDS_SIGNUP in App.jsx).
// Kept in app state only (never sent to the backend or browser storage).
export const GENDERS = [
  { value: "female", label: "Female" },
  { value: "male", label: "Male" },
  { value: "prefer_not_to_say", label: "Prefer not to say" },
];
export const MIN_AGE = 13;
export const MAX_AGE = 100;

const NEXT_STEPS = [
  { icon: Camera, label: "Selfie" },
  { icon: Sparkles, label: "Skin profile" },
  { icon: Sun, label: "AM/PM routine" },
];

const parseAge = (text) => (/^\d{1,3}$/.test(text) ? Number(text) : NaN);
const validAge = (n) => Number.isInteger(n) && n >= MIN_AGE && n <= MAX_AGE;

export default function AboutYou({ go, about, setAbout }) {
  const [gender, setGender] = useState(about?.gender ?? "");
  const [ageText, setAgeText] = useState(about?.age ? String(about.age) : "");
  const [ageTouched, setAgeTouched] = useState(false);
  const products = useShowcaseProducts();

  const age = parseAge(ageText);
  const ageError = ageText && !validAge(age) ? `Please enter an age between ${MIN_AGE} and ${MAX_AGE}` : "";
  const valid = !!gender && validAge(age);

  const submit = (e) => {
    e.preventDefault();
    setAgeTouched(true);
    if (!valid) return;
    setAbout({ gender, age });
    go("permission");
  };

  return (
    <div className="relative flex-1 w-full flex flex-col items-center px-4 sm:px-6 pt-1 pb-10 sm:pt-2">
      {/* One soft jade glow behind the logo: brand atmosphere, never competes with the form */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-y-0 left-1/2 w-screen -translate-x-1/2 overflow-hidden">
        <div className="absolute left-1/2 -top-40 h-[28rem] w-[46rem] -translate-x-1/2 rounded-full bg-mist blur-3xl opacity-90" />
      </div>

      <header className="relative flex flex-col items-center text-center w-full max-w-3xl">
        {/* Official transparent lockup; the negative margin offsets the file's transparent bottom padding (~17%). */}
        <FullLockup className="h-[64px] sm:h-[88px] -mb-2.5 sm:-mb-3" />
        <Eyebrow className="mt-2 mb-1.5 text-jade">Welcome to YuriWoori</Eyebrow>
        <h1 className="font-display text-[25px] sm:text-[32px] leading-[1.15] text-[#004647]">Start Your Personalised Skin Analysis</h1>
        <p className="mt-2 text-sm sm:text-[15px] leading-relaxed text-ink-soft max-w-3xl text-balance sm:text-wrap">
          Tell us a little about yourself to personalise your skin analysis and recommendations.
        </p>
      </header>

      <form
        onSubmit={submit}
        noValidate
        aria-label="Your details"
        className="relative mt-4 w-full max-w-[560px] rounded-card bg-white border border-hairline shadow-float px-5 py-6 sm:px-9 sm:py-6"
      >
        <div className="flex flex-col gap-4">
          <fieldset className="flex flex-col gap-1.5">
            <legend className="mb-1.5 text-[13px] font-semibold tracking-wide text-ink">Gender</legend>
            {/* Native radios (visually hidden) keep arrow-key navigation and screen-reader semantics */}
            <div className="grid grid-cols-3 gap-2 sm:gap-3">
              {GENDERS.map((g) => (
                <label key={g.value} className="cursor-pointer">
                  <input type="radio" name="gender" value={g.value} checked={gender === g.value} required
                    onChange={() => setGender(g.value)} className="peer sr-only" />
                  <span className="flex h-full min-h-12 items-center justify-center rounded-xl border border-sage-light bg-white px-2 py-2.5 text-center text-[14px] leading-tight text-ink transition-[border-color,background-color,box-shadow] hover:border-sage peer-checked:border-jade peer-checked:bg-mist peer-checked:font-semibold peer-checked:text-[#004647] peer-checked:ring-1 peer-checked:ring-jade peer-focus-visible:ring-4 peer-focus-visible:ring-jade/15">
                    {g.label}
                  </span>
                </label>
              ))}
            </div>
          </fieldset>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="entry-age" className="text-[13px] font-semibold tracking-wide text-ink">Age</label>
            <div className="relative w-full sm:w-44">
              <input
                id="entry-age" type="text" inputMode="numeric" pattern="[0-9]*" autoComplete="off" maxLength={3} required
                placeholder="e.g. 28" value={ageText}
                onChange={(e) => setAgeText(e.target.value.replace(/\D/g, ""))}
                onBlur={() => setAgeTouched(true)}
                aria-invalid={ageTouched && !!ageError}
                aria-describedby={ageTouched && ageError ? "entry-age-error" : undefined}
                className={`h-12 w-full rounded-xl border bg-white pl-4 pr-16 text-[15px] text-ink placeholder:text-ink-soft/60 outline-none transition-[border-color,box-shadow] focus:ring-4 ${
                  ageTouched && ageError ? "border-[#c98f8a] focus:border-[#b5635c] focus:ring-[#b5635c]/15" : "border-sage-light hover:border-sage focus:border-jade focus:ring-jade/10"
                }`}
              />
              <span aria-hidden="true" className="pointer-events-none absolute inset-y-0 right-4 flex items-center text-[13px] text-ink-soft">years</span>
            </div>
            {ageTouched && ageError && <p id="entry-age-error" className="text-[13px] text-[#9a3b35]">{ageError}</p>}
          </div>

          <Button type="submit" full disabled={!valid} icon={null} className="mt-1 text-[15px]">
            Continue →
          </Button>

          <ol className="flex flex-wrap items-center justify-center gap-x-2 gap-y-1 text-[12px] text-ink-soft" aria-label="What happens next: selfie, skin profile, AM/PM routine">
            {NEXT_STEPS.map(({ icon: Icon, label }, i) => (
              <li key={label} className="flex items-center gap-1.5">
                {i > 0 && <span aria-hidden="true" className="text-sage-light">—</span>}
                <Icon size={13} strokeWidth={1.75} className="text-sage" aria-hidden="true" /> {label}
              </li>
            ))}
          </ol>
        </div>
      </form>

      {products.length > 0 && (
        <section aria-label="YuriWoori products" className="relative mt-7 w-full max-w-[560px] flex flex-col items-center">
          <p className="text-center text-[10px] sm:text-[11px] font-semibold uppercase tracking-[0.1em] sm:tracking-[0.14em] text-sage mb-3">Personalised skincare, powered by YuriWoori</p>
          <ul className="grid w-full grid-cols-3 gap-3 sm:gap-4">
            {products.map((p) => (
              <li key={p.id} className="flex flex-col items-center gap-2">
                <ProductImage product={p} bg="bg-white" className="aspect-square w-full max-w-[140px] rounded-2xl border border-hairline" />
                <span className="text-[11px] leading-snug text-center text-ink-soft line-clamp-3 max-w-[150px]">{p.name.replace(/^Yuri Woori /, "")}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
