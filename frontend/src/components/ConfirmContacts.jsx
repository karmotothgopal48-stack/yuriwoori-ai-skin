/* Right after signup: verify the customer's mobile (WhatsApp) number with a one-time code. Every report waits
   for this — by WhatsApp and by email alike — so it can be sent automatically as soon as the analysis is done.
   The email address needs no code. When WhatsApp isn't set up on the server (or the number is already verified)
   this step moves on by itself. There is no silent skip: the customer can continue only by choosing, in plain
   words, not to receive their report now (the analysis itself still works, and the results page offers the
   same verification later). */
import { useEffect, useState } from "react";
import { CheckCircle2, Loader2, MessageCircle } from "lucide-react";
import { Button, Eyebrow } from "./Button";
import { confirmCode, deliveryStatus, sendCode } from "../services/delivery";
import { contactsToConfirm } from "../services/reportView";

export function ConfirmContacts({ onDone }) {
  const [status, setStatus] = useState(null);
  const [sent, setSent] = useState(false);
  const [code, setCode] = useState("");
  const [verified, setVerified] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    deliveryStatus()
      .then((s) => { if (contactsToConfirm(s).length === 0) onDone(); else setStatus(s); })
      .catch(() => onDone()); // can't check: carry on; the results page offers verification too
  }, [onDone]);

  if (!status) {
    return <p className="mt-10 flex items-center justify-center gap-2 text-sm text-ink-soft" role="status"><Loader2 size={16} className="animate-spin" aria-hidden="true" />One moment…</p>;
  }
  const number = status.whatsapp.destination;
  const run = async (action) => {
    setBusy(true); setError("");
    try { await action(); } catch (e) { setError(e.message || "Something went wrong. Please try again."); } finally { setBusy(false); }
  };
  const request = () => run(async () => { await sendCode("whatsapp"); setSent(true); setCode(""); });
  const confirm = () => run(async () => { await confirmCode("whatsapp", code.trim()); setVerified(true); });
  const codeOk = /^\d{6}$/.test(code.trim());

  return (
    <section aria-labelledby="confirm-title" className="relative mt-4 w-full max-w-[560px] rounded-card bg-white border border-hairline shadow-float px-5 py-6 sm:px-9">
      <Eyebrow className="text-jade">Your report</Eyebrow>
      <h2 id="confirm-title" className="mt-1 font-display text-[24px] leading-tight text-jade-deep">Verify your mobile number</h2>
      <p className="mt-2 text-[14px] leading-relaxed text-ink-soft">
        We'll send a 6-digit code by WhatsApp to confirm this number is yours. {status.report_consent
          ? "Once it's verified, your skin-analysis report is sent automatically when your analysis is done."
          : "Once it's verified, you can have your skin-analysis report sent to you from your results page."}
      </p>

      <div className="mt-4 rounded-2xl border border-hairline bg-white p-4">
        <p className="flex items-center gap-2 text-[14px] font-semibold text-jade-deep">
          <MessageCircle size={16} className="text-jade" aria-hidden="true" />WhatsApp
          <span className="font-normal text-ink-soft">· {number}</span>
        </p>
        {verified ? (
          <p className="mt-2 flex items-center gap-2 text-[13px] text-jade-deep" role="status"><CheckCircle2 size={15} aria-hidden="true" />Mobile number verified</p>
        ) : !sent ? (
          <button type="button" onClick={request} disabled={busy}
            className="mt-3 inline-flex min-h-[40px] items-center gap-2 rounded-pill border border-jade-line bg-white px-5 text-[13px] font-semibold text-jade hover:bg-mist disabled:opacity-60">
            {busy && <Loader2 size={14} className="animate-spin" aria-hidden="true" />}{busy ? "Sending…" : "Send me a code"}
          </button>
        ) : (
          <form className="mt-3 flex flex-wrap items-end gap-3" onSubmit={(e) => { e.preventDefault(); if (codeOk && !busy) confirm(); }}>
            <label className="flex flex-col gap-1 text-[12px] font-semibold text-ink">
              Code sent to {number}
              <input value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} inputMode="numeric" autoComplete="one-time-code" maxLength={6}
                className="h-10 w-36 rounded-xl border border-sage-light px-3 text-[15px] tracking-[0.3em] tabular-nums outline-none focus:border-jade focus:ring-4 focus:ring-jade/10" />
            </label>
            <button type="submit" disabled={busy || !codeOk}
              className="inline-flex min-h-[40px] items-center gap-2 rounded-pill bg-jade px-5 text-[13px] font-semibold text-cream hover:bg-jade-deep disabled:opacity-60">
              {busy && <Loader2 size={14} className="animate-spin" aria-hidden="true" />}Verify
            </button>
            <button type="button" onClick={request} disabled={busy} className="min-h-[40px] text-[12px] font-semibold uppercase tracking-[0.12em] text-jade">Send a new code</button>
          </form>
        )}
        {error && <p className="mt-2 text-[13px] text-danger-strong" role="alert">{error}</p>}
      </div>

      {verified ? (
        <Button full onClick={onDone} icon={null} className="mt-5 text-[15px]">Continue →</Button>
      ) : (
        <div className="mt-5 text-center">
          <button type="button" onClick={onDone} disabled={busy}
            className="min-h-[40px] text-[13px] font-semibold text-ink-soft underline decoration-ink-soft/40 underline-offset-2 hover:text-ink disabled:opacity-60">
            Continue without receiving my report
          </button>
          <p className="mt-1 text-[12px] text-ink-soft">Your analysis still works. Nothing is sent until your mobile number is verified — you can verify it later on your results page.</p>
        </div>
      )}
    </section>
  );
}
