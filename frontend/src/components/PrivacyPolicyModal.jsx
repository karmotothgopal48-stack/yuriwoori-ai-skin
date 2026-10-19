import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";

// What the backend does with the details of someone who continues (users, scans, scan_frames, skin_profiles,
// recommendations, contact_verifications, reports, result_deliveries, customer_sheet_sync, engagement_events).
// Keep in sync with CONSENT_VERSION in backend endpoints/users.py (currently 2026-10-19c).
const COLLECTED = [
  "Your name, WhatsApp number and email address, and when you accepted this notice",
  "The photo you take or upload — analysed on our server and then discarded straight away, including when the analysis can't be completed. It is never saved",
  "The skin measurements and results from your analysis, and the routine and products recommended to you",
  "Technical information such as IP address",
  "Products viewed or opened, for service analytics and internal reporting",
  "To verify your WhatsApp number: a one-time 6-digit code sent to it on WhatsApp. It expires after 10 minutes, and we keep only a one-way check value of it, never the code itself",
  "If you agree to receive your report: it is sent only after your WhatsApp number is verified, only to your own verified WhatsApp number and — if you also confirm it — your email address. The report is created from your saved results each time it is sent or opened, and is not stored as a file or document. Its personal link expires after 30 days and you can withdraw it at any time",
  "For each report message: the contact it was sent to and its delivery status (for example sent, delivered or failed). WhatsApp (Meta) and our email provider deliver the messages under their own terms; a copy can remain in your inbox, with those services and in our sending mailbox. A report PDF given to WhatsApp for delivery is deleted from WhatsApp's media storage once it is delivered",
  "So our team can follow up with you, after your WhatsApp number is verified: your name, email address, WhatsApp number, sign-up date, consent and verification status, and whether your analysis finished are saved in YuriWoori's private customer follow-up spreadsheet in Google Sheets (stored by Google). Only authorised YuriWoori team members can open it. Your photo, measurements and report are never added to it",
  "We keep your account details, consent and verification records, analysis results and delivery status until you ask us to delete them. To correct or delete your details, write to support@yuriwoori.com",
];

// Pending legal review (DPDP Act 2023 / GDPR): the retention statement and contact above need the business's
// confirmation, and a grievance officer may still need to be named.

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** Accessible privacy policy dialog: Esc / backdrop / Close to dismiss, focus trapped while open,
    page scroll locked, and focus handed back to whatever opened it. */
export function PrivacyPolicyModal({ open, onClose }) {
  const dialogRef = useRef(null);
  const closeRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    const opener = document.activeElement;
    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();

    const onKey = (e) => {
      if (e.key === "Escape") { e.preventDefault(); onClose(); return; }
      if (e.key !== "Tab") return;
      const items = [...(dialogRef.current?.querySelectorAll(FOCUSABLE) ?? [])];
      if (!items.length) return;
      const first = items[0], last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
      opener?.focus?.();
    };
  }, [open, onClose]);

  // Portal: the screen container is transformed during page transitions, which would break position: fixed.
  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-end sm:items-center justify-center sm:p-6"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}
        >
          <div className="absolute inset-0 bg-ink/40 backdrop-blur-sm" onClick={onClose} aria-hidden="true" />
          <motion.div
            ref={dialogRef}
            role="dialog" aria-modal="true" aria-labelledby="privacy-policy-title"
            className="relative flex w-full sm:max-w-lg max-h-[92dvh] sm:max-h-[80vh] flex-col bg-white shadow-float rounded-t-[24px] sm:rounded-card"
            initial={{ y: 24, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 24, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="flex items-center justify-between gap-4 border-b border-hairline px-6 py-4">
              <h2 id="privacy-policy-title" className="font-display text-2xl text-[#004647]">Privacy Policy</h2>
              <button type="button" onClick={onClose} aria-label="Close privacy policy"
                className="p-2 -mr-2 rounded-full text-ink-soft hover:text-ink hover:bg-mist focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-jade">
                <X size={20} strokeWidth={1.5} />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto overscroll-contain px-6 py-5 text-sm leading-relaxed text-ink-soft">
              <p className="text-ink mb-2">YuriWoori may collect and process:</p>
              <ul className="list-disc pl-5 space-y-1.5 marker:text-jade">
                {COLLECTED.map((c) => <li key={c}>{c}</li>)}
              </ul>
            </div>

            <div className="border-t border-hairline px-6 py-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
              <button ref={closeRef} type="button" onClick={onClose}
                className="w-full min-h-[48px] rounded-pill border border-jade text-jade text-sm font-semibold tracking-wide hover:bg-mist transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-jade focus-visible:ring-offset-2">
                Close
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
