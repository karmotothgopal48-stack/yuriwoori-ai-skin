import { useEffect, useState } from "react";
import { AlertCircle, ExternalLink, Info, Loader2, MessageCircle, Moon, RotateCcw, ShoppingBag, Sparkles, Sun, TriangleAlert } from "lucide-react";
import { motion } from "framer-motion";
import { ProductImage } from "../components/ProductCard";
import { AddToCart, Price } from "../components/Cart";
import { ResultNotice } from "../components/ResultNotice";
import { ResultsDelivery } from "../components/ResultsDelivery";
import { BTN_PRIMARY, BTN_SECONDARY, CARD, Kicker, ResultHero, SOFT, SectionHeading, fadeUp, stagger } from "../components/result";
import { applyRecommendations, loadRecommendations, trackProductClick, trackRecommendationsShown } from "../services/skinAnalysis";
import { guidance, mergeRoutine, optionalExtras, productKey, routineState } from "../services/routinePlan";
import { fetchLiveProducts } from "../services/liveProducts";
import { formatPrice, useCart } from "../services/cart";
import { shopifyCart } from "../services/delivery";
import { FINAL_PRICE_UNAVAILABLE, SHIPPING_TAXES_NOTE, currentQuote, discountLabel, discountNote, estimateBeforeDiscounts, priceState, routineLines, slabHint } from "../services/pricing";
import { whatsappProductLink } from "../services/whatsapp";

// The last step: the routine IS the product recommendation — the only place products are shown.
// WHICH products: the backend routine (GET /v1/scans/{id}/routine, best match per step) plus "optional
// extras" (the scan's other recommended products that are not a routine step, e.g. masks and eye patches,
// from GET /v1/catalogue/recommendations). Their CURRENT details — title, image, price, original price,
// discount, availability, variant — come live from the official YuriWoori store (GET /v1/catalogue/live).
// Morning and evening are merged so every product appears once ("Morning & Evening" / "Morning" / "Evening"),
// in skincare order; each card adds straight to the shared cart. The data has no frequency or duration fields,
// so none are invented: extras say "Use according to the product's recommended frequency".

// relationship_type values from the backend (IngredientInteractionType)
const INTERACTION = {
  synergistic: { title: "Work well together", cls: "bg-mist/60 border-jade-line/60", tone: "text-[#004647]" },
  caution: { title: "Use with care together", cls: "bg-[#faf3f0] border-[#ecd9d2]", tone: "text-[#7d4f45]" },
  avoid_same_routine: { title: "Avoid in the same routine", cls: "bg-[#faf3f0] border-[#ecd9d2]", tone: "text-[#7d4f45]" },
};

// The backend reason is "<why this step> Matches your scan: <concern>." When every step shares the same
// "Matches your scan" part, it is stated once above the routine instead of on every step.
const MATCH_RE = /\s*(Matches your scan:[^]*)$/;
const splitReason = (r) => { const m = (r ?? "").match(MATCH_RE); return m ? [r.slice(0, m.index).trim(), m[1].trim()] : [r ?? "", null]; };

const ROW = "grid gap-0.5 sm:grid-cols-[7.25rem_1fr] sm:gap-2";

/** Benefits and the full ingredient list (INCI), from the brand's product copy on yuriwoori.com; rows are
    left out when the store has none for the product. */
function ProductCopy({ benefits, keyBenefit, ingredients }) {
  const titles = (benefits ?? []).map((b) => b.title).filter(Boolean);
  return (
    <>
      {(titles.length > 0 || keyBenefit) && (
        <div className={ROW}><dt className="font-semibold text-ink">Benefits</dt><dd className="text-ink-soft">{titles.length ? titles.join(" · ") : keyBenefit}</dd></div>
      )}
      {ingredients?.length > 0 && (
        <div className={ROW}><dt className="font-semibold text-ink">Ingredients</dt>
          <dd className="text-ink-soft">
            <details>
              <summary className="cursor-pointer text-jade hover:text-[#004647]">Full ingredient list ({ingredients.length})</summary>
              <p className="mt-1.5 text-[12px] leading-relaxed">{ingredients.join(", ")}</p>
            </details>
          </dd>
        </div>
      )}
    </>
  );
}

/** "4:05 pm" for the backend's ISO timestamp of the live store data. */
const asOf = (iso) => {
  const d = iso ? new Date(iso) : null;
  return d && !Number.isNaN(d.getTime()) ? d.toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" }) : "an earlier check";
};

/** One product: live image, name and price (original price and discount when the store has them), how and
    why, Add to cart / quantity, a link to the official product page, and a WhatsApp enquiry about it. */
function ProductCard({ item, live, liveStatus, storeUrl, eyebrow, details, onOpen }) {
  const name = (live?.title ?? item.name).replace(/^Yuri Woori /, "");
  const productUrl = live?.url ?? item.url;
  // the enquiry names the product by its full official title and links its official page
  const whatsapp = whatsappProductLink({ name: live?.title ?? item.name, url: productUrl });
  return (
    <article className={`${CARD} mb-5 p-4 sm:p-5`}>
      <div className="flex items-start gap-4">
        <ProductImage product={{ name, image: live?.image_url ?? item.image }} bg="bg-white"
          className="h-24 w-24 shrink-0 rounded-2xl border border-hairline sm:h-28 sm:w-28 [&_img]:mix-blend-multiply" />
        <div className="min-w-0 flex-1">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-sage">{eyebrow}</p>
          <h3 className="mt-1 font-display text-[19px] leading-snug text-[#004647]">{name}</h3>
          <div className="mt-1.5">
            {live
              ? <Price price={live.price} compareAt={live.compare_at_price} discount={live.discount_percent} />
              : liveStatus === "loading"
                ? <p className="flex items-center gap-1.5 text-[12px] text-ink-soft" aria-live="polite"><Loader2 size={13} className="animate-spin" aria-hidden="true" />Loading current price…</p>
                : <p className="text-[12px] text-ink-soft">Live price unavailable — see the product page.</p>}
          </div>
        </div>
      </div>
      {details}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <AddToCart product={live} storeUrl={storeUrl} />
        <div className="flex flex-wrap items-center gap-x-5 gap-y-1">
          {whatsapp && (
            <a href={whatsapp} target="_blank" rel="noreferrer" aria-label={`Ask on WhatsApp about ${name}`}
              className="inline-flex min-h-[40px] items-center gap-1.5 rounded-sm text-[12px] font-semibold uppercase tracking-[0.12em] text-jade hover:text-[#004647] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-jade">
              <span aria-hidden="true">💬</span> Ask on WhatsApp
            </a>
          )}
          {productUrl && (
            <a href={productUrl} target="_blank" rel="noreferrer" onClick={() => onOpen?.(item)}
              className="inline-flex min-h-[40px] items-center gap-1.5 rounded-sm text-[12px] font-semibold uppercase tracking-[0.12em] text-jade hover:text-[#004647] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-jade">
              Product details <ExternalLink size={13} aria-hidden="true" />
            </a>
          )}
        </div>
      </div>
    </article>
  );
}

function RitualStep({ entry, n, last, hideMatch, liveData, onOpen, tags }) {
  const s = entry.step;
  const [why, match] = splitReason(s.reason);
  const live = liveData.byHandle[s.handle];
  const g = guidance({ usage: live?.usage, when: entry.when, tags });
  return (
    <motion.li variants={fadeUp} className="relative grid grid-cols-[auto_1fr] gap-4 sm:gap-5">
      {/* number + connector */}
      <div className="flex flex-col items-center">
        <span className="flex h-11 w-11 items-center justify-center rounded-full border border-jade-line bg-white font-display text-lg text-[#004647]">{String(n).padStart(2, "0")}</span>
        {!last && <span aria-hidden="true" className="mt-2 w-px flex-1 bg-sage-light" />}
      </div>
      <ProductCard item={s} live={live} liveStatus={liveData.status} storeUrl={liveData.storeUrl} onOpen={onOpen}
        eyebrow={`Step ${String(n).padStart(2, "0")}${s.step ? ` · ${s.step}` : ""} · ${entry.when}`}
        details={(
          <dl className="mt-4 grid gap-2.5 text-[13px] leading-relaxed">
            <div className={ROW}><dt className="font-semibold text-ink">When</dt><dd className="font-medium text-[#004647]">{entry.when}</dd></div>
            <div className={ROW}><dt className="font-semibold text-ink">How</dt><dd className="text-ink-soft">{s.howToUse ?? "The catalogue has no usage instructions for this product."}</dd></div>
            <ProductCopy benefits={s.benefits} keyBenefit={s.keyBenefit} ingredients={s.ingredients} />
            <div className={ROW}><dt className="font-semibold text-ink">Why</dt><dd className="text-ink-soft">{hideMatch ? why : [why, match].filter(Boolean).join(" ")}</dd></div>
            {live && <div className={ROW}><dt className="font-semibold text-ink">Use consistently</dt><dd className="text-ink-soft" title={g.source}>{[g.routine, g.wear, g.review].filter(Boolean).join(" ")}</dd></div>}
          </dl>
        )} />
    </motion.li>
  );
}

/** The daily routine: every unique product once, in skincare order, each marked Morning / Evening / both. */
function DailyRoutine({ entries, hideMatch, liveData, onOpen, tagsFor }) {
  const allBoth = entries.every((e) => e.times.size === 2);
  return (
    <section aria-labelledby="daily-title" className="mx-auto mb-10 max-w-3xl">
      <div className="mb-5 flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-full border border-jade-line bg-white">
          {allBoth ? <Sun size={18} className="text-jade" strokeWidth={1.6} aria-hidden="true" /> : <Moon size={18} className="text-jade" strokeWidth={1.6} aria-hidden="true" />}
        </span>
        <div>
          <p id="daily-title" className="font-display text-2xl leading-none text-[#004647]">{allBoth ? "Morning & evening" : "Your daily steps"}</p>
          <p className="mt-1 text-[12px] text-ink-soft">
            {entries.length} product{entries.length === 1 ? "" : "s"}{allBoth ? ", each used morning and evening" : " · each step shows when to use it"}
          </p>
        </div>
      </div>
      <motion.ol initial="hidden" whileInView="show" viewport={{ once: true, margin: "-40px" }} variants={stagger}>
        {entries.map((e, i) => <RitualStep key={productKey(e.step)} entry={e} n={i + 1} last={i === entries.length - 1} hideMatch={hideMatch} liveData={liveData} onOpen={onOpen} tags={tagsFor(e.step.handle)} />)}
      </motion.ol>
    </section>
  );
}

/** Recommended products that are not a daily routine step (e.g. masks, eye patches), shown once. */
/* The price of the whole daily routine (one of each product), as Shopify calculates it for that cart right now:
   subtotal, each discount it applies (automatic slab discounts need no code), total; plus the store's discount slab
   when Shopify's result confirms it. Without Shopify's pricing, only a labelled estimate before discounts is shown. */
function RoutinePrice({ entries, liveData }) {
  const lines = liveData.status === "ready" ? routineLines(entries.map((e) => e.step.handle), liveData.byHandle) : [];
  const key = lines.map((l) => l.variant_id).join(",");
  const [quote, setQuote] = useState({ key: "", status: "idle", data: null });
  const [attempt, setAttempt] = useState(0);  // "Check again" asks Shopify once more
  useEffect(() => {
    if (!key) return;
    let alive = true;
    setQuote({ key, status: "loading", data: null });
    shopifyCart(key.split(",").map(Number))
      .then((data) => { if (alive) setQuote({ key, status: "ready", data }); })
      .catch(() => { if (alive) setQuote({ key, status: "error", data: null }); });
    return () => { alive = false; };
  }, [key, attempt]);
  if (!key) return null;
  const q = currentQuote(quote, key);
  const hint = q && slabHint(q.slabs, formatPrice);
  // an estimate only from prices confirmed live just now; the store's last (stale) copy is never totalled
  const state = priceState({ shopify: q, quoteStatus: quote.key === key ? quote.status : "loading", pricesConfirmed: !liveData.stale });
  return (
    <section aria-labelledby="routine-price-title" className={`${CARD} mx-auto mb-10 max-w-3xl p-6`}>
      <h2 id="routine-price-title" className="font-display text-2xl text-[#004647]">Your routine price</h2>
      <p className="mt-1 text-[12px] text-ink-soft">All {lines.length} routine products, one of each, priced by yuriwoori.com (Shopify) for this cart.</p>
      {state === "shopify" ? (
        <>
          <dl className="mt-4 grid gap-1.5 text-[14px]" aria-live="polite">
            <div className="flex justify-between text-ink-soft"><dt>Products subtotal</dt><dd className="tabular-nums">{formatPrice(q.subtotal)}</dd></div>
            {q.discounts.map((d) => (
              <div key={`${d.kind}-${d.title}`} className="flex justify-between text-[#004647]"><dt>{discountLabel(d)}</dt><dd className="tabular-nums">−{formatPrice(d.amount)}</dd></div>
            ))}
            <div className="flex justify-between text-ink-soft"><dt>Shipping &amp; taxes</dt><dd className="text-[12px]">{SHIPPING_TAXES_NOTE}</dd></div>
            <div className="mt-1 flex items-baseline justify-between border-t border-sage-light pt-2">
              <dt className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink-soft">Total payable (before shipping)</dt>
              <dd className="font-display text-[24px] text-[#004647] tabular-nums">{formatPrice(q.total)}</dd>
            </div>
          </dl>
          <p className="mt-2 text-[12px] leading-relaxed text-ink-soft">{discountNote(q.discounts)} Shipping is added at checkout.</p>
          {hint && <p className="mt-2 rounded-xl bg-mist/60 px-3 py-2 text-[12px] leading-relaxed text-[#004647]">{hint}</p>}
        </>
      ) : state === "unavailable" ? (
        <p className="mt-4 text-[14px] leading-relaxed text-ink" role="status"><span className="font-semibold">{FINAL_PRICE_UNAVAILABLE}</span>{" "}
          yuriwoori.com couldn't confirm current prices and discounts, so no total is shown.{" "}
          <button type="button" onClick={() => setAttempt((n) => n + 1)} className="font-semibold text-jade underline-offset-4 hover:underline">Check again</button></p>
      ) : state === "estimate" ? (
        <div className="mt-4 text-[14px]" role="status">
          <p className="mb-2 font-semibold text-ink">{FINAL_PRICE_UNAVAILABLE}</p>
          <div className="flex items-baseline justify-between"><span className="text-ink-soft">Subtotal (estimate, before discounts)</span>
            <span className="tabular-nums font-semibold">{formatPrice(estimateBeforeDiscounts(lines, liveData.byHandle))}</span></div>
          <p className="mt-2 text-[12px] leading-relaxed text-ink-soft">yuriwoori.com couldn't calculate discounts just now, so this is an estimate, not the amount you pay. Any store discount and the final total are shown at checkout.{" "}
            <button type="button" onClick={() => setAttempt((n) => n + 1)} className="font-semibold text-jade underline-offset-4 hover:underline">Check again</button></p>
        </div>
      ) : (
        <p className="mt-4 flex items-center gap-2 text-[13px] text-ink-soft" role="status"><Loader2 size={14} className="animate-spin" aria-hidden="true" />{FINAL_PRICE_UNAVAILABLE} (calculating on yuriwoori.com…)</p>
      )}
    </section>
  );
}

function OptionalExtras({ extras, liveData, onOpen, tagsFor }) {
  if (!extras.length) return null;
  return (
    <section aria-labelledby="extras-title" className="mx-auto mb-10 max-w-3xl">
      <div className="mb-5 flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-full border border-jade-line bg-white"><Sparkles size={18} className="text-jade" strokeWidth={1.6} aria-hidden="true" /></span>
        <div>
          <p id="extras-title" className="font-display text-2xl leading-none text-[#004647]">Optional extras</p>
          <p className="mt-1 text-[12px] text-ink-soft">Matched to your scan, outside the daily steps</p>
        </div>
      </div>
      <motion.ul initial="hidden" whileInView="show" viewport={{ once: true, margin: "-40px" }} variants={stagger}>
        {extras.map((p) => {
          const live = liveData.byHandle[p.id];
          const g = guidance({ usage: live?.usage, when: "", tags: tagsFor(p.id) });
          return (
          <motion.li key={p.id} variants={fadeUp}>
            <ProductCard item={{ ...p, handle: p.id }} live={live} liveStatus={liveData.status} storeUrl={liveData.storeUrl} onOpen={() => onOpen({ handle: p.id })}
              eyebrow={`Extra${p.step && p.routineStep !== "unassigned" ? ` · ${p.step}` : ""}`}
              details={(
                <dl className="mt-4 grid gap-2.5 text-[13px] leading-relaxed">
                  <div className={ROW}><dt className="font-semibold text-ink">When</dt><dd className="text-ink-soft" title={g.source}>{g.extra}</dd></div>
                  {p.howToUse && <div className={ROW}><dt className="font-semibold text-ink">How</dt><dd className="text-ink-soft">{p.howToUse}</dd></div>}
                  <ProductCopy benefits={p.benefits} keyBenefit={p.keyBenefit} ingredients={p.ingredients} />
                  <div className={ROW}><dt className="font-semibold text-ink">Why</dt><dd className="text-ink-soft">{p.reason}</dd></div>
                  {live && <div className={ROW}><dt className="font-semibold text-ink">Use consistently</dt><dd className="text-ink-soft">{[g.wear, g.review].filter(Boolean).join(" ")}</dd></div>}
                </dl>
              )} />
          </motion.li>
          );
        })}
      </motion.ul>
    </section>
  );
}

// One message per failure kind (routinePlan.routineState). None of them is ever shown as "balanced".
const ERROR_COPY = {
  "matching-error": { title: "We couldn't find matching YuriWoori products for this result.", body: "Your skin analysis is complete, but no matching YuriWoori products came back for it. Please retry, or scan again." },
  "server-error": { title: "We couldn't load your personalized routine right now.", body: "The YuriWoori server didn't respond. Your skin analysis is saved; please retry." },
  "data-error": { title: "We received an incomplete routine result.", body: "Please try again. If this keeps happening, scan again." },
};

/** The routine couldn't be produced: no product match, a server failure, or missing/unusable analysis data. */
function RoutineError({ kind, onRetry, retrying, retryFailed, go }) {
  const copy = ERROR_COPY[kind] ?? ERROR_COPY["data-error"];
  return (
    <div className="mx-auto mb-10 max-w-2xl rounded-[24px] border border-[#f0dedd] bg-[#fcf4f3] p-6 text-center sm:p-8" role="alert">
      <AlertCircle size={32} className="mx-auto mb-3 text-[#8a2e2e]" strokeWidth={1.5} aria-hidden="true" />
      <h3 className="mb-2 font-display text-2xl text-ink">{copy.title}</h3>
      <p className="text-sm leading-relaxed text-ink-soft">{copy.body}{retryFailed ? " The last attempt didn't succeed either." : ""}</p>
      <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
        {onRetry && (
          <button type="button" onClick={onRetry} disabled={retrying} className={BTN_PRIMARY}>
            {retrying ? <Loader2 size={16} className="animate-spin" aria-hidden="true" /> : <RotateCcw size={16} aria-hidden="true" />}{retrying ? "Retrying…" : "Retry"}
          </button>
        )}
        <button type="button" onClick={() => go("start")} className={BTN_SECONDARY}>Scan again</button>
      </div>
    </div>
  );
}

export default function Routine({ go, analysis, setAnalysis }) {
  const routine = analysis?.routine;
  const flags = analysis?.compatibility ?? [];
  const { count, setOpen } = useCart();
  const onOpen = (s) => trackProductClick(analysis?.scanId, s.handle); // best-effort engagement tracking
  // Every product once: morning + evening merged by product (services/routinePlan.js).
  const targeted = routine ? mergeRoutine(routine) : [];
  const extras = optionalExtras(analysis?.recommendations, targeted);
  // ready | maintenance | balanced | matching-error | server-error | data-error — "maintenance"/"balanced" only on
  // the backend's explicit balanced verdict (routinePlan.routineState)
  const state = routineState(analysis, targeted, extras);
  // A balanced scan's maintenance routine (real catalogue products) is shown in the same layout as a targeted one.
  const shown = state === "maintenance" ? analysis.maintenance : routine;
  const entries = state === "maintenance" ? mergeRoutine(shown) : targeted;
  const withRoutine = state === "ready" || state === "maintenance";
  const hasProtect = shown?.AM.some((s) => s.step === "Protect");
  const matches = shown ? [...new Set([...shown.AM, ...shown.PM].map((s) => splitReason(s.reason)[1]))] : [];
  const sharedMatch = matches.length === 1 && matches[0] ? matches[0] : null;
  const handles = [...entries.map((e) => e.step.handle), ...extras.map((p) => p.id)].filter(Boolean);

  const [retrying, setRetrying] = useState(false);
  const [retryFailed, setRetryFailed] = useState(false);
  const retry = async () => {
    setRetrying(true);
    setRetryFailed(false);
    try {
      const matched = await loadRecommendations(analysis.scanId);
      setAnalysis((current) => applyRecommendations(current ?? analysis, matched));
      if (matched.errors.length) setRetryFailed(true);
    } catch {
      setRetryFailed(true);
    } finally {
      setRetrying(false);
    }
  };

  // Which concern(s) each product was matched to (backend recommendations), for its review wording.
  const matchedTags = Object.fromEntries((analysis?.recommendations ?? []).map((p) => [p.id, p.matched.map((m) => m.tag)]));
  const scanTags = Object.keys(analysis?.activeConcerns ?? {});
  const tagsFor = (handle) => matchedTags[handle] ?? scanTags;

  const [liveData, setLiveData] = useState({ storeUrl: null, byHandle: {}, status: "idle" });
  const [liveAttempt, setLiveAttempt] = useState(0);
  const handleKey = handles.join(",");
  useEffect(() => {
    if (!handleKey) return;
    let alive = true;
    setLiveData((d) => ({ ...d, status: "loading" }));
    fetchLiveProducts(handleKey.split(","))
      .then((d) => { if (alive) setLiveData({ ...d, status: "ready" }); })
      .catch(() => { if (alive) setLiveData((d) => ({ ...d, status: "error" })); });
    return () => { alive = false; };
  }, [handleKey, liveAttempt]);
  // What was offered is recorded once per scan for the admin report (backend engagement events).
  useEffect(() => { if (handleKey) trackRecommendationsShown(analysis?.scanId); }, [handleKey, analysis?.scanId]);

  const overview = withRoutine && entries.length > 0 && (
    <div className={`${CARD} p-6`}>
      <Kicker className="mb-4">Your routine at a glance</Kicker>
      <ul className="grid grid-cols-2 gap-3">
        {[{ t: "Morning", i: Sun, n: shown.AM.length }, { t: "Evening", i: Moon, n: shown.PM.length }].map((x) => (
          <li key={x.t} className={`${SOFT} p-4`}>
            <x.i size={18} className="text-jade" strokeWidth={1.6} aria-hidden="true" />
            <p className="mt-2 font-display text-3xl leading-none text-[#004647] tabular-nums">{x.n}</p>
            <p className="mt-1 text-[12px] text-ink-soft">{x.t} step{x.n === 1 ? "" : "s"}</p>
          </li>
        ))}
      </ul>
      <p className="mt-4 text-[12px] leading-relaxed text-ink-soft">Follow the numbered order: each step prepares the skin for the next. Add products to your cart straight from each step.</p>
    </div>
  );

  return (
    <div className="flex-1 w-full max-w-6xl mx-auto px-4 sm:px-8 py-8 sm:py-10">
      <ResultHero eyebrow="Personalized routine" title="Your daily YuriWoori ritual." aside={overview || undefined}>
        <p>What to use, when, and in what order. For each step — cleanse, tone, treat, moisturize, and protect in the morning only — the YuriWoori product that best matches your scan is chosen; steps with no match are left out.</p>
        {state === "ready" && sharedMatch && <p className="mt-3 text-[13px] font-medium text-[#004647]">{sharedMatch}</p>}
      </ResultHero>

      {state.endsWith("-error") && (
        <RoutineError kind={state} onRetry={analysis?.scanId ? retry : null} retrying={retrying} retryFailed={retryFailed} go={go} />
      )}

      {state === "balanced" && (
        <div className="mb-10">
          <ResultNotice reason="balanced">
            <button type="button" onClick={() => go("profile")} className={BTN_SECONDARY}>See my measured values</button>
            <button type="button" onClick={() => go("start")} className={BTN_SECONDARY}><RotateCcw size={16} aria-hidden="true" />Scan again</button>
          </ResultNotice>
        </div>
      )}

      {state === "maintenance" && (
        <div className="mb-10"><ResultNotice reason="maintenance" /></div>
      )}

      {withRoutine && liveData.status === "error" && (
        <div className={`${SOFT} mx-auto mb-8 flex max-w-3xl flex-col gap-3 p-4 text-[13px] text-ink-soft sm:flex-row sm:items-center sm:justify-between`} role="alert">
          <p className="flex items-start gap-3"><Info size={15} className="mt-0.5 shrink-0 text-jade" aria-hidden="true" />
            Live prices from yuriwoori.com couldn't be loaded right now, so products can't be added to the cart yet. Product pages still open on the official store.</p>
          <button type="button" onClick={() => setLiveAttempt((n) => n + 1)} className={`${BTN_SECONDARY} shrink-0`}><RotateCcw size={16} aria-hidden="true" />Try again</button>
        </div>
      )}

      {withRoutine && liveData.status === "ready" && liveData.stale && (
        <div className={`${SOFT} mx-auto mb-8 flex max-w-3xl flex-col gap-3 p-4 text-[13px] text-ink-soft sm:flex-row sm:items-center sm:justify-between`} role="status">
          <p className="flex items-start gap-3"><Info size={15} className="mt-0.5 shrink-0 text-jade" aria-hidden="true" />
            yuriwoori.com couldn't be reached just now, so prices and availability are as of {asOf(liveData.fetchedAt)}. They are confirmed again at checkout.</p>
          <button type="button" onClick={() => setLiveAttempt((n) => n + 1)} className={`${BTN_SECONDARY} shrink-0`}><RotateCcw size={16} aria-hidden="true" />Refresh</button>
        </div>
      )}

      {withRoutine && entries.length > 0 && <DailyRoutine entries={entries} hideMatch={!!sharedMatch} liveData={liveData} onOpen={onOpen} tagsFor={tagsFor} />}
      {withRoutine && entries.length > 0 && <RoutinePrice entries={entries} liveData={liveData} />}

      {state === "ready" && <OptionalExtras extras={extras} liveData={liveData} onOpen={onOpen} tagsFor={tagsFor} />}

      {/* The daily routine loaded but the catalogue recommendations didn't: say so instead of silently dropping extras. */}
      {state === "ready" && analysis.matchErrors?.includes("recommendations") && (
        <div className={`${SOFT} mx-auto mb-10 flex max-w-3xl flex-col gap-3 p-4 text-[13px] text-ink-soft sm:flex-row sm:items-center sm:justify-between`} role="alert">
          <p className="flex items-start gap-3"><Info size={15} className="mt-0.5 shrink-0 text-jade" aria-hidden="true" />
            Optional extras couldn't be loaded right now. Your daily routine above is complete.</p>
          <button type="button" onClick={retry} disabled={retrying} className={`${BTN_SECONDARY} shrink-0`}>
            {retrying ? <Loader2 size={16} className="animate-spin" aria-hidden="true" /> : <RotateCcw size={16} aria-hidden="true" />}Try again
          </button>
        </div>
      )}

      {state === "ready" && entries.length > 0 && routine.AM.length > 0 && !hasProtect && (
        <p className={`mx-auto mb-10 flex max-w-3xl items-start gap-3 ${SOFT} px-5 py-4 text-[13px] leading-relaxed text-ink-soft`}>
          <Info size={15} className="mt-0.5 shrink-0 text-jade" aria-hidden="true" />No sun-protection product matched the concerns in this scan, so the morning routine has no protect step.
        </p>
      )}

      {withRoutine && <ResultsDelivery scanId={analysis?.scanId} />}

      {flags.length > 0 && (
        <section className="mb-10">
          <SectionHeading kicker="Ingredients" title="Ingredients in this routine" />
          <ul className="flex flex-col gap-3">
            {flags.map((f, i) => {
              const t = INTERACTION[f.type] ?? INTERACTION.caution;
              return (
                <li key={i} className={`rounded-2xl border p-4 ${t.cls}`}>
                  <p className={`flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] ${t.tone}`}><TriangleAlert size={12} aria-hidden="true" />{t.title}</p>
                  <p className="mt-1 text-sm font-semibold text-ink">{f.a} + {f.b}</p>
                  <p className="mt-1 text-sm leading-relaxed text-ink-soft">{f.text}</p>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {/* The journey ends here: ask the coach, or review the cart and check out on yuriwoori.com */}
      <nav aria-label="Next steps" className="mt-4 flex flex-col-reverse items-stretch gap-3 border-t border-sage-light/70 pt-7 sm:flex-row sm:items-center sm:justify-end">
        <button type="button" onClick={() => go("assistant")} className={BTN_SECONDARY}><MessageCircle size={16} aria-hidden="true" />Ask Yuri</button>
        <button type="button" onClick={() => setOpen(true)} className={BTN_PRIMARY}>
          <ShoppingBag size={16} aria-hidden="true" />View cart{count > 0 ? ` (${count})` : ""}
        </button>
      </nav>
    </div>
  );
}
