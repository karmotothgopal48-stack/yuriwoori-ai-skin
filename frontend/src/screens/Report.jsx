/* The customer's skin-analysis report, opened from the secure link sent by email / WhatsApp
   (https://<app>/report#t=<token>). The token stays in the URL fragment and is sent to the API in a header.
   It shows the report as it was made (saved results, routine, products and Shopify's prices on that date);
   "Continue to checkout" asks Shopify for a fresh cart, so the checkout always has current prices and discounts. */
import { useEffect, useState } from "react";
import { FINAL_PRICE_UNAVAILABLE, SHIPPING_TAXES_NOTE, discountLabel } from "../services/pricing";
import { AlertCircle, Download, ExternalLink, Loader2, Moon, ShoppingBag, Sun } from "lucide-react";
import { FullLockup } from "../components/Logo";
import { ProductImage } from "../components/ProductCard";
import { CARD, Kicker } from "../components/result";
import { downloadSharedReportPdf, sharedReport, shopifyCart } from "../services/delivery";
import { money, parseReportToken } from "../services/reportView";

const STEP = { cleanse: "Cleanse", tone: "Tone", treat: "Treat", moisturize: "Moisturize", protect: "Protect", mask: "Mask" };
const date = (iso) => (iso ? new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "long", year: "numeric", hour: "numeric", minute: "2-digit" }) : "");

function Product({ p, heading, notes }) {
  return (
    <li className="flex gap-4 border-b border-hairline py-4 last:border-b-0">
      <ProductImage product={{ name: p.name, image: p.image_url }} bg="bg-white" size={80} className="h-20 w-20 shrink-0 rounded-2xl border border-hairline" />
      <div className="min-w-0 flex-1 text-[13px] leading-relaxed">
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-sage">{heading}</p>
        <a href={p.url} target="_blank" rel="noreferrer" className="font-display text-[17px] leading-snug text-jade-deep hover:underline">{p.name.replace(/^Yuri Woori /, "")}</a>
        <p className="mt-0.5">
          <span className="font-semibold text-jade-deep">{money(p.price)}</span>
          {p.compare_at_price != null && <span className="ml-2 text-ink-soft/70 line-through">{money(p.compare_at_price)}</span>}
          {p.discount_percent != null && <span className="ml-2 rounded-full bg-mist px-2 py-0.5 text-[10px] font-semibold text-jade-deep">{p.discount_percent}% off</span>}
          {!p.available && <span className="ml-2 text-danger-strong">Unavailable</span>}
        </p>
        {notes.filter(Boolean).map((n, i) => <p key={i} className="mt-1 text-ink-soft">{n}</p>)}
      </div>
    </li>
  );
}

export default function Report() {
  const token = parseReportToken(window.location.hash);
  const [state, setState] = useState(token ? "loading" : "invalid"); // loading | ready | invalid | error
  const [report, setReport] = useState(null);
  const [checkout, setCheckout] = useState({ busy: false, error: "" });
  const [pdf, setPdf] = useState({ busy: false, error: "" });

  useEffect(() => {
    if (!token) return;
    sharedReport(token)
      .then((r) => { setReport(r); setState("ready"); })
      .catch((e) => setState(e.status === 404 ? "invalid" : "error"));
  }, [token]);

  const c = report?.content;
  const routineVariants = c ? [...new Set(["AM", "PM"].flatMap((p) => c.routine[p] ?? []).map((s) => c.products[s.handle])
    .filter((p) => p.available && p.variant_id).map((p) => p.variant_id))] : [];

  const goToCheckout = async () => {
    setCheckout({ busy: true, error: "" });
    try {
      const cart = await shopifyCart(routineVariants);
      window.location.assign(cart.checkout_url);
    } catch (e) {
      setCheckout({ busy: false, error: e.message || "The checkout couldn't be opened. Please try again." });
    }
  };
  const downloadPdf = async () => {
    setPdf({ busy: true, error: "" });
    try { await downloadSharedReportPdf(token); setPdf({ busy: false, error: "" }); } catch (e) { setPdf({ busy: false, error: e.message || "The PDF couldn't be downloaded." }); }
  };

  return (
    <div className="min-h-dvh bg-cream px-4 pb-16 pt-6 sm:px-6">
      <div className="mx-auto max-w-2xl">
        <header className="flex flex-col items-center text-center">
          <FullLockup className="h-[56px]" />
          <Kicker className="mt-3">Skin-analysis report</Kicker>
        </header>

        {state === "loading" && <p className="mt-10 flex items-center justify-center gap-2 text-sm text-ink-soft"><Loader2 size={16} className="animate-spin" aria-hidden="true" />Opening your report…</p>}
        {(state === "invalid" || state === "error") && (
          <div className="mt-8 rounded-[24px] border border-danger-line bg-danger-soft p-6 text-center" role="alert">
            <AlertCircle size={28} className="mx-auto mb-2 text-danger" aria-hidden="true" />
            <p className="font-display text-xl text-ink">{state === "invalid" ? "This report link isn't valid or has expired." : "Your report couldn't be opened right now."}</p>
            <p className="mt-2 text-sm text-ink-soft">{state === "invalid" ? "Report links are personal and expire after a while. You can run a new skin analysis at any time." : "Please try again in a moment."}</p>
          </div>
        )}

        {state === "ready" && c && (
          <>
            <section className={`${CARD} mt-6 p-6`}>
              <h1 className="font-display text-[28px] leading-tight text-jade-deep">{c.customer_name ? `${c.customer_name}'s skin report` : "Your skin report"}</h1>
              <p className="mt-1 text-[13px] text-ink-soft">Analysis of {date(c.analysis_date)}{c.body_part === "hand" ? " · hand scan" : ""}</p>
              <div className="mt-4 flex flex-wrap gap-3 text-[14px]">
                {c.skin_type && <span className="rounded-full bg-mist px-3 py-1">Skin type: <b>{c.skin_type}</b></span>}
                {c.overall_score != null && <span className="rounded-full bg-mist px-3 py-1">Overall score: <b>{c.overall_score}/100</b></span>}
              </div>
              <div className="mt-5 flex flex-wrap gap-3">
                <button type="button" onClick={downloadPdf} disabled={pdf.busy} className="inline-flex min-h-[44px] items-center gap-2 rounded-pill border border-jade-line bg-white px-5 text-[13px] font-semibold text-jade hover:bg-mist">
                  {pdf.busy ? <Loader2 size={15} className="animate-spin" aria-hidden="true" /> : <Download size={15} aria-hidden="true" />}Download PDF
                </button>
              </div>
              {pdf.error && <p className="mt-2 text-[13px] text-danger-strong" role="alert">{pdf.error}</p>}
            </section>

            <section className={`${CARD} mt-5 p-6`} aria-labelledby="m-title">
              <h2 id="m-title" className="font-display text-[22px] text-jade-deep">Your measurements</h2>
              <ul className="mt-3 divide-y divide-hairline">
                {c.metrics.map((m) => (
                  <li key={m.key} className="py-3">
                    <div className="flex items-baseline justify-between gap-3">
                      <span className="font-semibold text-ink">{m.label}</span>
                      <span className="tabular-nums text-jade-deep"><b>{m.value}</b>/100{m.benchmark != null && <span className="ml-2 text-[12px] text-ink-soft">typical {m.benchmark}</span>}</span>
                    </div>
                    <p className="mt-1 text-[12px] leading-relaxed text-ink-soft">{m.measures}</p>
                    {m.concern && <p className="mt-1 text-[12px] font-semibold text-danger-strong">Flagged: {m.concern}</p>}
                  </li>
                ))}
              </ul>
              {c.benchmark_note && <p className="mt-2 text-[11px] leading-relaxed text-ink-soft">{c.benchmark_note}</p>}
            </section>

            <section className={`${CARD} mt-5 p-6`} aria-labelledby="n-title">
              <h2 id="n-title" className="font-display text-[22px] text-jade-deep">What we noticed</h2>
              <p className="mt-2 text-[14px] leading-relaxed text-ink-soft">
                {c.concerns.length
                  ? `Your scan crossed our levels for: ${c.concerns.map((x) => x.phrase).join(", ")}. Your routine uses YuriWoori products whose own product information addresses these.`
                  : "None of your measurements crossed our levels for a concern, so this is a simple care routine with YuriWoori products made for general care."}
              </p>
            </section>

            {[["AM", "Morning routine", Sun], ["PM", "Evening routine", Moon]].map(([period, title, Icon]) => (c.routine[period]?.length ? (
              <section key={period} className={`${CARD} mt-5 p-6`}>
                <h2 className="flex items-center gap-2 font-display text-[22px] text-jade-deep"><Icon size={18} className="text-jade" aria-hidden="true" />{title}</h2>
                <ol className="mt-2">
                  {c.routine[period].map((s) => (
                    <Product key={s.handle} p={c.products[s.handle]} heading={`Step ${s.step_order} · ${STEP[s.step] ?? s.step}`}
                      notes={[s.reason, c.products[s.handle].how_to_use && `How to use: ${c.products[s.handle].how_to_use}`]} />
                  ))}
                </ol>
              </section>
            ) : null))}

            {c.extras?.length > 0 && (
              <section className={`${CARD} mt-5 p-6`}>
                <h2 className="font-display text-[22px] text-jade-deep">Optional extras</h2>
                <ul className="mt-2">
                  {c.extras.map((x) => {
                    const p = c.products[x.handle];
                    return <Product key={x.handle} p={p} heading="Extra" notes={[x.reason, p.usage_quote ? `How often: ${p.usage_quote}` : p.how_to_use && `How to use: ${p.how_to_use}`]} />;
                  })}
                </ul>
              </section>
            )}

            <section className={`${CARD} mt-5 p-6`} aria-labelledby="p-title">
              <h2 id="p-title" className="font-display text-[22px] text-jade-deep">Your routine on yuriwoori.com</h2>
              {c.pricing ? (
                <>
                  <dl className="mt-3 grid gap-1.5 text-[14px]">
                    <div className="flex justify-between text-ink-soft"><dt>Subtotal</dt><dd className="tabular-nums">{money(c.pricing.subtotal)}</dd></div>
                    {c.pricing.discounts.map((d) => (
                      <div key={`${d.kind}-${d.title}`} className="flex justify-between text-jade-deep"><dt>{discountLabel(d)}</dt><dd className="tabular-nums">−{money(d.amount)}</dd></div>
                    ))}
                    <div className="flex justify-between text-ink-soft"><dt>Shipping &amp; taxes</dt><dd className="text-[12px]">{SHIPPING_TAXES_NOTE}</dd></div>
                    <div className="flex justify-between border-t border-sage-light pt-2 font-semibold text-jade-deep"><dt>Total payable (before shipping)</dt><dd className="tabular-nums">{money(c.pricing.total)}</dd></div>
                  </dl>
                  <p className="mt-2 text-[11px] leading-relaxed text-ink-soft">All routine products, one of each, as priced by Shopify on {date(c.pricing.quoted_at)} with the discounts it applied automatically. The checkout prices your cart again now and shows the final amount, including shipping.</p>
                </>
              ) : (
                <p className="mt-2 text-[13px] text-ink-soft"><span className="font-semibold text-ink">{FINAL_PRICE_UNAVAILABLE}</span> Shopify couldn't price the routine just now; the checkout shows the current prices, discounts and total.</p>
              )}
              {routineVariants.length > 0 && (
                <button type="button" onClick={goToCheckout} disabled={checkout.busy}
                  className="mt-4 inline-flex min-h-[50px] w-full items-center justify-center gap-2 rounded-pill bg-jade text-[15px] font-semibold tracking-wide text-cream hover:bg-jade-deep">
                  {checkout.busy ? <Loader2 size={16} className="animate-spin" aria-hidden="true" /> : <ShoppingBag size={16} aria-hidden="true" />}Continue to checkout <ExternalLink size={14} aria-hidden="true" />
                </button>
              )}
              {checkout.error && <p className="mt-2 text-[13px] text-danger-strong" role="alert">{checkout.error}</p>}
            </section>

            <p className="mt-6 text-center text-[11px] leading-relaxed text-ink-soft">
              {c.disclaimer} Report made {date(c.generated_at)}. This link is personal to you and expires on {date(report.expires_at)}.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
