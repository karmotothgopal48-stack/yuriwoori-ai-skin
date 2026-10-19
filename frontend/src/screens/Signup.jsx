import { useCallback, useRef, useState } from "react";
import { AlertCircle } from "lucide-react";
import { Button, Eyebrow } from "../components/Button";
import { FullLockup } from "../components/Logo";
import { ProductImage } from "../components/ProductCard";
import { PrivacyPolicyModal } from "../components/PrivacyPolicyModal";
import { useShowcaseProducts } from "../services/showcase";
import { signUp } from "../services/skinAnalysis";
import { setUserToken } from "../services/session";
import { validateSignup as validate } from "../services/contact";
import { ConfirmContacts } from "../components/ConfirmContacts";

// Name + WhatsApp number + email + consent, asked at the start of the analysis (and again before the upload
// if the session is gone): every scan endpoint needs this session. App.jsx shows this in place of a
// NEEDS_SIGNUP screen; once setUser runs, that screen renders and continues.
// There is no password. The backend records the consent time and version (users.consented_at / consent_version).
// An email that already has an account (another device) is only opened with the 6-digit code the backend emails to
// it: the form then asks for that code and sends the same details again with it. Results are only sent to a
// contact the user confirms later.

function Field({ id, label, error, hint, ...input }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-[13px] font-semibold tracking-wide text-ink">{label}</label>
      <input
        id={id}
        aria-invalid={!!error}
        aria-describedby={[error && `${id}-error`, hint && `${id}-hint`].filter(Boolean).join(" ") || undefined}
        className={`h-12 w-full rounded-xl border bg-white px-4 text-[15px] text-ink placeholder:text-ink-soft/60 outline-none transition-[border-color,box-shadow] focus:ring-4 ${
          error ? "border-[#c98f8a] focus:border-[#b5635c] focus:ring-[#b5635c]/15" : "border-sage-light hover:border-sage focus:border-jade focus:ring-jade/10"
        }`}
        {...input}
      />
      {hint && <p id={`${id}-hint`} className="text-[12px] leading-relaxed text-ink-soft">{hint}</p>}
      {error && <p id={`${id}-error`} className="text-[13px] text-[#9a3b35]">{error}</p>}
    </div>
  );
}

export default function Signup({ setUser }) {
  const [values, setValues] = useState({ name: "", whatsapp: "", email: "" });
  const [touched, setTouched] = useState({ name: false, whatsapp: false, email: false });
  const [consent, setConsent] = useState(false);
  // separate and optional: send the report to these contacts (each is confirmed with a code before anything is sent)
  const [reportConsent, setReportConsent] = useState(false);
  const [signedUp, setSignedUp] = useState(null); // the new user while their contacts are being confirmed
  const finishSignup = useCallback(() => setUser(signedUp), [setUser, signedUp]);
  const [policyOpen, setPolicyOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [signIn, setSignIn] = useState(null); // { sentTo } while a sign-in code is awaited for an existing account
  const [code, setCode] = useState("");
  const submitting = useRef(false);
  const products = useShowcaseProducts();

  const errors = validate(values);
  const valid = !errors.name && !errors.whatsapp && !errors.email && consent && (!signIn || /^\d{6}$/.test(code.trim()));
  const closePolicy = useCallback(() => setPolicyOpen(false), []);

  const change = (key) => (e) => {
    setValues((v) => ({ ...v, [key]: e.target.value }));
    if (key === "email") { setSignIn(null); setCode(""); } // a code belongs to the email it was sent to
  };
  const blur = (key) => () => setTouched((t) => ({ ...t, [key]: true }));

  const submit = async (e) => {
    e.preventDefault();
    setTouched({ name: true, whatsapp: true, email: true });
    if (!valid || submitting.current) return; // one request at a time, even on a double click
    submitting.current = true;
    setBusy(true); setError("");
    try {
      const res = await signUp(values.name.trim(), values.whatsapp.trim(), values.email.trim(), true, reportConsent, signIn ? code.trim() : undefined);
      if (res.code_required) { // this email already has an account: ask for the code that was emailed to it
        setSignIn({ sentTo: res.sent_to }); setCode("");
        submitting.current = false; setBusy(false);
        return;
      }
      const { token, user } = res;
      setUserToken(token);
      // Verify the mobile number next (ConfirmContacts moves on by itself when WhatsApp isn't set up or it is
      // already verified): every report waits for it, so the report can go out automatically after the analysis.
      setSignedUp(user);
    } catch (err) {
      // For diagnosis: HTTP status and the server's reason only, never the name, email or session token.
      // (A 503 here usually means the backend can't reach PostgreSQL; the backend log names the cause.)
      console.warn(`Signup failed: HTTP ${err.status ?? "?"} (${err.reason ?? "unknown"}): ${err.message}`);
      // A server error gets a plain message; connection, 404 and validation errors keep their own explanation.
      setError(err.reason === "server" ? "We couldn't save your analysis right now. Please try again." : err.message || "Something went wrong. Please try again.");
      submitting.current = false;
      setBusy(false);
    }
  };

  const openPolicy = (e) => {
    e.preventDefault();
    e.stopPropagation(); // the link sits inside the consent label: never toggle the checkbox
    setPolicyOpen(true);
  };

  return (
    <div className="relative flex-1 w-full flex flex-col items-center px-4 sm:px-6 pt-1 pb-10 sm:pt-2">
      {/* One soft jade glow behind the logo: brand atmosphere, never competes with the form */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-y-0 left-1/2 w-screen -translate-x-1/2 overflow-hidden">
        <div className="absolute left-1/2 -top-40 h-[28rem] w-[46rem] -translate-x-1/2 rounded-full bg-mist blur-3xl opacity-90" />
      </div>

      <header className="relative flex flex-col items-center text-center w-full max-w-3xl">
        {/* Official transparent lockup (the client-supplied file has a white box, for white surfaces only).
            The negative margin offsets the file's transparent bottom padding (~17%). */}
        <FullLockup className="h-[64px] sm:h-[88px] -mb-2.5 sm:-mb-3" />
        <Eyebrow className="mt-2 mb-1.5 text-jade">Before we begin</Eyebrow>
        <h1 className="font-display text-[25px] sm:text-[32px] leading-[1.15] text-[#004647]">Your Skin Analysis</h1>
        <p className="mt-2 text-sm sm:text-[15px] leading-relaxed text-ink-soft max-w-3xl text-balance sm:text-wrap">
          Enter your details so we can save your skin analysis, your results and your personalised product recommendations.
        </p>
      </header>

      {signedUp ? <ConfirmContacts onDone={finishSignup} /> : (
      <form
        onSubmit={submit}
        noValidate
        aria-label="Your details"
        className="relative mt-4 w-full max-w-[560px] rounded-card bg-white border border-hairline shadow-float px-5 py-6 sm:px-9 sm:py-6"
      >
        <div className="flex flex-col gap-3">
          <Field id="entry-name" label="Name" type="text" placeholder="Enter your name" autoComplete="name" required maxLength={100}
            value={values.name} onChange={change("name")} onBlur={blur("name")} error={touched.name ? errors.name : ""} />
          <Field id="entry-whatsapp" label="WhatsApp Number" type="tel" inputMode="tel" placeholder="e.g. 98765 43210" autoComplete="tel" required maxLength={25}
            hint="Next, we'll send a 6-digit code to this number on WhatsApp to verify it. Your results are only ever sent after it's verified."
            value={values.whatsapp} onChange={change("whatsapp")} onBlur={blur("whatsapp")} error={touched.whatsapp ? errors.whatsapp : ""} />
          <Field id="entry-email" label="Email Address" type="email" placeholder="Enter your email" autoComplete="email" required maxLength={254}
            hint="Why we ask: to send you your skin-analysis results and personalised recommendations. Nothing is sent to it before your WhatsApp number is verified."
            value={values.email} onChange={change("email")} onBlur={blur("email")} error={touched.email ? errors.email : ""} />

          <label htmlFor="entry-consent" className="mt-0.5 flex items-start gap-3 cursor-pointer rounded-xl bg-cream/70 border border-hairline px-3.5 py-3">
            <input
              id="entry-consent" type="checkbox" required checked={consent} onChange={(e) => setConsent(e.target.checked)}
              aria-describedby={touched.name && touched.whatsapp && touched.email && !consent ? "entry-consent-error" : undefined}
              className="mt-0.5 h-5 w-5 shrink-0 cursor-pointer accent-[#005C5D] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-jade"
            />
            <span className="text-[13px] leading-relaxed text-ink">
              I agree to the{" "}
              <a href="#privacy-policy" onClick={openPolicy}
                className="font-semibold text-jade underline decoration-jade/40 underline-offset-2 hover:decoration-jade focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-jade rounded-sm">
                Privacy Policy
              </a>{" "}
              and consent to YuriWoori processing my name, WhatsApp number, email and the photo I take or upload (analysed, then discarded) for skin analysis, personalised recommendations and sending me my results after I verify my WhatsApp number, and — once it is verified — to my name, email and WhatsApp number being saved in YuriWoori's private Google Sheet so authorised team members can follow up with me.
            </span>
          </label>

          <label htmlFor="entry-report-consent" className="flex items-start gap-3 cursor-pointer rounded-xl bg-cream/70 border border-hairline px-3.5 py-3">
            <input id="entry-report-consent" type="checkbox" checked={reportConsent} onChange={(e) => setReportConsent(e.target.checked)}
              className="mt-0.5 h-5 w-5 shrink-0 cursor-pointer accent-[#005C5D] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-jade" />
            <span className="text-[13px] leading-relaxed text-ink">
              Send my skin-analysis report (with my results and personalised recommendations) to my email and WhatsApp number. <span className="text-ink-soft">Optional — you can also choose this after your analysis.</span>
            </span>
          </label>

          {signIn && (
            <div className="rounded-xl border border-jade-line bg-mist/60 px-3.5 py-3">
              <Field id="entry-code" label="Sign-in code" type="text" inputMode="numeric" autoComplete="one-time-code" placeholder="6-digit code" maxLength={6}
                hint={`This email already has a YuriWoori account. We've emailed a 6-digit code to ${signIn.sentTo ?? "it"} — enter it to continue. It expires in 10 minutes.`}
                value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} />
              <button type="button" onClick={() => { setSignIn(null); setCode(""); setError(""); }} disabled={busy}
                className="mt-2 min-h-[36px] text-[12px] font-semibold uppercase tracking-[0.12em] text-jade">
                Send a new code
              </button>
            </div>
          )}

          {touched.name && touched.whatsapp && touched.email && !consent && (
            <p id="entry-consent-error" className="-mt-1 text-[13px] text-[#9a3b35]">Please accept the Privacy Policy to continue.</p>
          )}

          {error && (
            <p className="flex items-start gap-2 rounded-xl bg-[#fcf4f3] border border-[#f0dedd] p-3 text-sm text-[#8a2e2e]" role="alert">
              <AlertCircle size={16} className="shrink-0 mt-0.5" /> {error}
            </p>
          )}

          <Button type="submit" full loading={busy} disabled={!valid} icon={null} aria-busy={busy} className="mt-1 text-[15px]">
            {signIn ? "Continue →" : "Analyse My Skin →"}
          </Button>
        </div>
      </form>
      )}

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

      <PrivacyPolicyModal open={policyOpen} onClose={closePolicy} />
    </div>
  );
}
