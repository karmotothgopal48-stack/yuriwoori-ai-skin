/* "Your report": the skin-analysis report of this scan (saved results + live YuriWoori products), its PDF, and
   its delivery to the customer's own email and WhatsApp (services/delivery.js). Each channel shows what the
   backend recorded — pending (and why), sending, sent, delivered or failed — with the one next step that
   applies: agree to sending, confirm the contact with a code, retry, or check again. Nothing is ever shown
   as sent unless the provider confirmed it. */
import { useCallback, useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, Download, Loader2, Mail, MessageCircle, RotateCcw, Send } from "lucide-react";
import { CARD, Kicker } from "./result";
import { CHANNEL_LABELS, confirmCode, createReport, downloadOwnReportPdf, reportStatus, sendCode, sendReport } from "../services/delivery";
import { deliveryView, shouldPoll } from "../services/reportView";

const ICONS = { email: Mail, whatsapp: MessageCircle };
const BTN = "inline-flex min-h-[40px] items-center justify-center gap-2 rounded-pill px-5 text-[13px] font-semibold tracking-wide transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-jade disabled:opacity-60";
const PRIMARY = `${BTN} bg-jade text-cream hover:bg-jade-deep`;
const SECONDARY = `${BTN} border border-jade-line bg-white text-jade hover:bg-mist`;
const TONE = { sent: "text-jade-deep", delivered: "text-jade-deep", failed: "text-danger-strong", unavailable: "text-ink-soft", ask: "text-ink", pending: "text-ink" };

function Channel({ info, scanId, onChange, onRecheck }) {
  const view = deliveryView(info);
  const [codeSent, setCodeSent] = useState(false);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const Icon = ICONS[info.channel];

  const run = async (action) => {
    setBusy(true); setError("");
    try { await action(); } catch (e) { setError(e.message || "Something went wrong. Please try again."); } finally { setBusy(false); }
  };
  const send = () => run(async () => { await sendReport(scanId, info.channel); await onChange(); });
  const requestCode = () => run(async () => { await sendCode(info.channel); setCodeSent(true); setCode(""); });
  const confirm = () => run(async () => { await confirmCode(info.channel, code.trim()); setCodeSent(false); await onChange(); });

  return (
    <li className="rounded-2xl border border-hairline bg-white p-4">
      <p className="flex items-center gap-2 text-[14px] font-semibold text-jade-deep">
        <Icon size={16} className="text-jade" aria-hidden="true" />{CHANNEL_LABELS[info.channel]}
        {info.destination && <span className="font-normal text-ink-soft">· {info.destination}</span>}
      </p>
      <p className={`mt-2 flex items-start gap-2 text-[13px] leading-relaxed ${TONE[view.kind] ?? "text-ink"}`} role="status">
        {(view.kind === "sent" || view.kind === "delivered") && <CheckCircle2 size={15} className="mt-0.5 shrink-0" aria-hidden="true" />}
        {view.kind === "failed" && <AlertCircle size={15} className="mt-0.5 shrink-0" aria-hidden="true" />}
        {view.kind === "pending" && <Loader2 size={15} className="mt-0.5 shrink-0 animate-spin" aria-hidden="true" />}
        <span>{view.text}</span>
      </p>

      {view.action === "consent" && (
        <button type="button" onClick={send} disabled={busy} className={`${PRIMARY} mt-3`}>
          {busy ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : <Send size={14} aria-hidden="true" />}Yes, send my report
        </button>
      )}
      {view.action === "code" && !codeSent && (
        <button type="button" onClick={requestCode} disabled={busy} className={`${SECONDARY} mt-3`}>
          {busy && <Loader2 size={14} className="animate-spin" aria-hidden="true" />}Send me a code
        </button>
      )}
      {view.action === "code" && codeSent && (
        <form className="mt-3 flex flex-wrap items-end gap-3" onSubmit={(e) => { e.preventDefault(); if (/^\d{6}$/.test(code.trim())) confirm(); }}>
          <label className="flex flex-col gap-1 text-[12px] font-semibold text-ink">
            Code sent to {info.destination}
            <input value={code} onChange={(e) => setCode(e.target.value)} inputMode="numeric" autoComplete="one-time-code" maxLength={6}
              className="h-10 w-36 rounded-xl border border-sage-light px-3 text-[15px] tracking-[0.3em] tabular-nums outline-none focus:border-jade focus:ring-4 focus:ring-jade/10" />
          </label>
          <button type="submit" disabled={busy || !/^\d{6}$/.test(code.trim())} className={PRIMARY}>
            {busy && <Loader2 size={14} className="animate-spin" aria-hidden="true" />}Confirm &amp; send
          </button>
          <button type="button" onClick={requestCode} disabled={busy} className="min-h-[40px] text-[12px] font-semibold uppercase tracking-[0.12em] text-jade">Send a new code</button>
        </form>
      )}
      {view.action === "retry" && (
        <button type="button" onClick={send} disabled={busy} className={`${SECONDARY} mt-3`}>
          {busy ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : <RotateCcw size={14} aria-hidden="true" />}Try again
        </button>
      )}
      {view.action === "check" && view.kind === "unavailable" && (
        <button type="button" onClick={() => run(onRecheck)} disabled={busy} className="mt-2 min-h-[36px] text-[12px] font-semibold uppercase tracking-[0.12em] text-jade">
          Check again
        </button>
      )}
      {error && <p className="mt-2 text-[13px] text-danger-strong" role="alert">{error}</p>}
    </li>
  );
}

export function ResultsDelivery({ scanId }) {
  const [report, setReport] = useState(null); // ReportStatusResponse
  const [state, setState] = useState("loading"); // loading | ready | error
  const [pdfBusy, setPdfBusy] = useState(false);
  const [pdfError, setPdfError] = useState("");

  // Creating is idempotent: the report is generated once from the saved analysis; this also sends it wherever ready.
  const load = useCallback(async () => {
    try { setReport(await createReport(scanId)); setState("ready"); } catch { setState("error"); }
  }, [scanId]);
  const refresh = useCallback(async () => {
    try { setReport(await reportStatus(scanId)); } catch { /* keep the last known state */ }
  }, [scanId]);

  useEffect(() => { if (scanId) load(); }, [scanId, load]);
  // while a message is on its way (sending, or accepted by WhatsApp), look again every few seconds for a minute
  useEffect(() => {
    if (!report || !shouldPoll(report.deliveries)) return;
    let n = 0;
    const id = setInterval(() => { n += 1; if (n > 12) clearInterval(id); else refresh(); }, 5000);
    return () => clearInterval(id);
  }, [report, refresh]);

  if (!scanId) return null;
  const downloadPdf = async () => {
    setPdfBusy(true); setPdfError("");
    try { await downloadOwnReportPdf(scanId); } catch (e) { setPdfError(e.message || "The PDF couldn't be downloaded. Please try again."); } finally { setPdfBusy(false); }
  };

  return (
    <section aria-labelledby="report-title" className={`${CARD} mx-auto mb-10 max-w-3xl p-6 sm:p-8`}>
      <Kicker>Keep your results</Kicker>
      <h2 id="report-title" className="mt-1 font-display text-[26px] leading-tight text-jade-deep">Your skin-analysis report</h2>
      <p className="mt-3 text-[14px] leading-relaxed text-ink-soft">
        Your measured results, what we noticed, your morning and evening routine, and your products with current prices and any store discounts — as a PDF, by email and on WhatsApp.
      </p>

      {state === "loading" && <p className="mt-4 flex items-center gap-2 text-[13px] text-ink-soft"><Loader2 size={15} className="animate-spin" aria-hidden="true" />Preparing your report…</p>}
      {state === "error" && (
        <div className="mt-4 flex flex-wrap items-center gap-3 text-[13px] text-danger-strong" role="alert">
          <AlertCircle size={15} aria-hidden="true" />Your report couldn't be prepared right now.
          <button type="button" onClick={() => { setState("loading"); load(); }} className={SECONDARY}><RotateCcw size={14} aria-hidden="true" />Try again</button>
        </div>
      )}

      {state === "ready" && report && (
        <>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button type="button" onClick={downloadPdf} disabled={pdfBusy} className={PRIMARY}>
              {pdfBusy ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : <Download size={14} aria-hidden="true" />}Download PDF
            </button>
            {report.revoked && <span className="text-[13px] text-ink-soft">The link to this report was withdrawn.</span>}
          </div>
          {pdfError && <p className="mt-2 text-[13px] text-danger-strong" role="alert">{pdfError}</p>}
          {!report.revoked && (
            <ul className="mt-4 grid gap-3">
              {report.deliveries.map((d) => <Channel key={d.channel} info={d} scanId={scanId} onChange={refresh} onRecheck={load} />)}
            </ul>
          )}
        </>
      )}
    </section>
  );
}
