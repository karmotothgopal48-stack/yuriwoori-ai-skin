# Design audit (Phase 1)

Audit of the local site at `http://localhost:2999` on 19 October 2026, compared with the official brand (`docs/brand-sheet.md`).
Screenshots of every screen at 1440 px (desktop) and 390 px (mobile) are in `docs/audit/before/` (32 images).

**How the screenshots were made.** Headless Chrome drove the real running app. Screens that need a signed-up user and a
scan were filled with real backend responses for a test user, made by the backend's own code inside a database
transaction that was then rolled back, so no user, scan or message was kept. Report creation and Shopify pricing were
blocked during capture. So the "Your routine price" box and the report box show their **unavailable** states in
screenshots 11–12, which is a capture artifact, not a site bug. The selfie in screenshots 08–11 is a stand-in (the
existing `hero-portrait.webp`), not a customer photo.

**No page overflows horizontally at 390 px.** Every screen was checked.

---

## A. Important mismatches between the brief and this project

These need a decision from you before Phase 2, because the brief describes things this codebase doesn't have.

1. **The hero in the brief doesn't exist here.** "Diagnostic Dermatology", "ISO-Certified", "Upload one analyze essential
   skin markers", "94% Hydration", "Pore Balance", "Non-Medical Guidance", a green glass panel, marble and crystals:
   none of these strings or visuals are anywhere in `frontend/`. The current hero is "See what one selfie says about your
   skin." with a model holding the Real Gold Hydro-Gel Eye Patch. Maybe the brief was written for a different design or
   a mock-up. Please send that design if you want it built.
2. **These sections don't exist yet, so they would be new features, not a redesign:** header navigation menu, trust bar,
   Shop by Concern, products / catalogue page, progress tracking, shopping agent UI, user account page, footer,
   ingredients / education, and 404/500 pages. The backend has endpoints for some of them (`/progress`,
   `/shopping-agent/build`, `/passport`, `/catalogue/products`), but the app never calls them.
3. **Some requests conflict with existing rules:**
   - *Progress "before/after photo slider".* This needs saved photos, which the strict **no-selfie-storage** rule forbids.
     Progress can be shown with measurements only (the backend already records `progress_snapshots`, numbers only).
   - *"The user's photo with soft markers" on results.* The analysis measures the whole photo; it doesn't locate
     concerns at points on the face. Markers placed on a customer's own face would suggest findings that weren't
     measured. I suggest no markers on the customer's photo; decorative markers only on brand imagery, labelled "Sample".
   - *Newsletter field in the footer.* There's no newsletter backend. Options: link to the official store's signup, or leave it out.
4. **Claims not found on yuriwoori.com:** "VerifEye anti-counterfeit sticker" and "ISO-Certified". They can't be used
   until you confirm them and give the exact wording. "Vegan", "Cruelty-free", "100% authentic, straight from Korea" and
   "Paraben & sulfate free" are confirmed on the official site.

---

## B. Problems across the whole site

| # | Problem | Evidence | Planned fix |
|---|---|---|---|
| B1 | **Header draws a full box, not a bottom line** | The `.border-hairline` class (`index.css`) sets `border: 1px solid` on all four sides, so `border-b border-hairline` boxes the whole header. Same side-effect on the Ask Yuri panel (hard side borders). Used in 41 places. | Make the hairline class set only the color; use side utilities for width. |
| B2 | **Header step label collides with the logo** | "STEP 1 OF 8 · YOUR DETAILS" overlaps the logo's tiny tagline (all flow screenshots). | Compact logo (no tagline) in the header; step label on its own line or beside the progress bar. |
| B3 | **Two different step numbers on every flow screen** | Header "STEP 2 OF 8 · PERMISSION" vs page eyebrow "STEP 1 · PERMISSION"; Tips 3 vs 2, Camera 4 vs 3, Review 5 vs 4, Analysis 6 vs 5. | One numbering source (the header). Page eyebrows show only the section name. |
| B4 | **Fonts don't match the brand** | App: DM Serif Display + Montserrat. Official: Fira Sans site-wide; Fraunces + Outfit on product pages. | Fraunces (display) + Outfit (body/UI), pending your approval. |
| B5 | **Colors are hard-coded** | 201 hex values in 24 files; `#004647` alone 88 times (not a token); 9 ad-hoc rose/red values for errors. | Tokens in `index.css` (`@theme`), aligned to the official palette; replace every literal. |
| B6 | **Type sizes bypass the scale** | ~200 arbitrary sizes (`text-[10px]` 23×, `[11px]` 34×, `[12px]` 40×, `[13px]` 47×, …) next to an unused fluid scale. | A 7-step type scale in tokens; eyebrows minimum 11–12 px. |
| B7 | **Low-contrast small text** | Sage `#528778` eyebrows on cream = 3.73:1 at 10–11 px (fails WCAG AA); `text-ink-soft/60–80` opacity variants are lower still. | A darker eyebrow color (≥ 4.5:1); no opacity on body text. |
| B8 | **Inconsistent spelling** | "Analyse My Skin" (signup) vs "Analyze My Skin" (review); "PERSONALIZED ROUTINE" vs "personalised" (8×). | Indian/British English throughout (analyse, personalised), as the store uses. |
| B9 | **Images have no responsive setup** | 0 `srcset`; one `loading="lazy"`; one `fetchpriority`; hero is a single 960 px WebP; an unused 347 KB PNG (`ai-skin-analysis-face.png`). Product images come from the Shopify CDN at full size. | `srcset`/`sizes`, fixed ratios, lazy below the fold, Shopify CDN `width=` parameters, skeletons and a fallback image. |
| B10 | **No footer, no 404** | Every page ends without a footer; an unknown URL silently shows the app start. | Footer (official links, social, marketplaces as text, disclaimer) and a 404 screen, if approved (see A2). |
| B11 | **Logo raster only** | PNG logos; the admin header shows the logo on a **white box** against the cream page (`16-admin-login`). | SVG logo when you provide it; a transparent PNG until then. |
| B12 | **Page background differs from the store** | App cream `#F1F5EB` (yellow-green) vs store white / `#EDF1F0` (grey-green). | Decide the base: white plus `#EDF1F0` sections like the store, or keep a warm cream. |

---

## C. Page by page

### 01–02 Start (home)
- ✅ Strong, calm hero; real YuriWoori product in the model's hand; clear CTA; honest privacy and medical lines.
- ❌ Decorative chips ("TEXTURE · TONE", "HYDRATION") and glowing dots on the model read like real measurements. → Add a small "Sample" label or make them clearly decorative.
- ❌ Desktop: the page ends after three small cards, leaving a large empty band and no brand context. → Add confirmed brand promises (vegan, cruelty-free, authentic Korean), a "how it works" strip and a real-product strip from the catalogue API (pending A2).
- ❌ Mobile: chips are hidden but the dots stay, which looks like noise. → Remove the dots on mobile or show the labels.
- ❌ "Continuing as Test (…)" line (signed-in, `02`) is small, low-contrast text. → Readable size and an account chip in the header.

### 03 Signup / 04 About you
- ❌ **Logo shown twice** (header and page) at the same size. → Remove the page logo.
- ❌ Consent text is a 9-line block in 13 px. → Keep the legal wording **unchanged** but split it into a short summary plus "Read full consent" (same checkbox and same meaning). Needs your OK, since this is consent wording.
- ❌ The disabled button (white on `#BDDCCD`, 1.47:1) looks broken rather than disabled. → Clearer disabled style plus the reason ("Fill in your details").
- ❌ Product tiles are small (140 px), with tiny 11 px names and loose spacing. → Larger 4:5 tiles with a consistent crop.
- ⚠️ Gender buttons look like inputs, not choices. → Chip or segmented style with a clear selected state.

### 05 Permission
- ❌ Header says step 2, page says step 1 (B3).
- ❌ Desktop leaves the bottom ~35% empty; the content block sits high. → Vertically centre it, or add the "what happens next" strip.
- ⚠️ The same model photo as the hero, with decorative chips. → Fine to reuse; label chips as sample.

### 06 Tips
- ✅ Clear illustration and copy.
- ❌ 5 cards in a 3 + 2 grid with uneven heights. → Equal-height cards; good vs. bad example images (needs photos, see the image requests in Phase 3).
- ❌ Card titles are in sans 15 px while other cards use the serif. → One card-title style.

### 07 Camera
- (Screenshot uses Chrome's fake camera: the green test pattern is not the app.)
- ❌ Five text styles in one panel: dark pill, light pill, white bold, white small, uppercase links. → Two status styles at most.
- ❌ "Upload a photo instead" is a small uppercase link. → A proper secondary button.
- ⚠️ The frame overlay is a rounded rectangle while Tips teaches an **oval**. → Use the same oval in both.

### 08 Review
- ✅ Good use of the customer's own photo; clear privacy note.
- ❌ "Analyze" vs "Analyse" (B8).
- ⚠️ Mobile: the photo card takes 60% of the first screen, pushing the CTA below the fold. → Smaller photo on mobile with the CTA visible.

### 09 Processing
- ✅ Real progress steps; the customer's photo in the rings.
- ❌ Desktop: the content sits in the middle of a mostly empty page (top ~25% and bottom ~25% blank). → Tighter vertical rhythm.

### 10 Skin profile (results)
- ✅ Clear hierarchy; honest benchmark notes; the customer's own photo (session memory only, shipped earlier today).
- ❌ Seven rows of measurements in small type (labels 10–11 px) with low-contrast "Higher means more of this trait". → Larger labels, bars in brand colors, and score rings optional (the brief asks for them).
- ❌ Concerns aren't linked to products on this page; products appear only on the routine page. → "Recommended for this" link from each flagged measurement to its routine step (no new data: uses the existing recommendations).
- ⚠️ The final dark CTA panel is the only dark section in the whole flow. → Keep it, but match radius and type with the rest.

### 11–12 Your routine
- ❌ **Product cards are text-heavy**: the product image is a 110 px thumbnail while each card has 6 labelled text rows (When / How / Benefits / Ingredients / Why / Use consistently). → Larger image (4:5, from the catalogue API), with the How/Benefits/Why rows collapsed into "Details".
- ❌ Desktop uses a single 700 px column centred under a header that spans 1100 px. → Two columns on desktop (morning | evening), or a wider card with the image on the left.
- ❌ "Optional extras" includes the "4 Step Skincare Routine & Free Beauty Bag" kit at ₹49. That's a promotional kit, not an extra for this routine (data/matching question, **not** a design change; please confirm whether kits should appear).
- ❌ "ASK ON WHATSAPP" and "PRODUCT DETAILS" are uppercase 11 px text links next to a filled button. → Secondary/ghost buttons from the system.
- ⚠️ The price and report boxes show their unavailable states in the screenshot (blocked during capture, see top).

### 13 Ask Yuri
- ❌ The panel's left and right edges are hard dark lines (B1) and the panel is glued to the header.
- ❌ It fills only the top half of the page; the input sits mid-screen on desktop. → Full-height chat column with the input pinned to the bottom.
- ❌ No product cards in answers (the API returns `cited_product_ids`), and no typing indicator. → Product mini-cards with images, plus a typing indicator.

### 14 Cart (drawer)
- ✅ Clear empty state.
- ❌ The empty state is plain text plus a small icon. → An on-brand illustration and a "See your routine" button when a routine exists.

### 15 Report link (invalid / expired)
- ✅ Honest message.
- ❌ The error card uses an ad-hoc rose palette (`#FCF4F3` / `#9A3B35`), and the page is otherwise empty. → Token error colors, plus a "Start a new skin analysis" button.

### 16 Admin login
- ❌ The logo has a white box behind it (B11), and "ADMIN" appears twice (header and eyebrow).
- ✅ Simple and functional. Keep it plain, as the brief asks: tokens only, less decoration.

---

## D. Image inventory (current)

| File | Size | Used | Issue |
|---|---|---|---|
| `hero-portrait.webp` | 960×1200, 35 KB | Start hero | Single size, no `srcset`; licence and model release unknown |
| `permission-portrait.webp` | 800×1000, 28 KB | Permission | Same as above |
| `ai-skin-analysis-face.png` | 462×540, **347 KB** | **Not used** | Remove or convert |
| `yuriwoori-logo-green.png` / `-white.png` | 812×812 | Header / logo | Raster; tagline illegible small |
| `yuriwoori-logo-provided.png` | 170×157 | Admin | Not transparent (white box) |
| `yuriwoori-wordmark-green.png`, `yuriwoori-heart-*.png` | small | Accents | Fine; SVG preferred |
| Product images | Shopify CDN via `/catalogue/*` | Signup, routine, cart | Full-size downloads; no fixed ratio; no fallback |

---

## E. Decisions I need from you before Phase 2

1. **Hero:** keep and improve the current "See what one selfie says about your skin" hero, or send me the design with the green glass panel, marble and crystals that the brief describes?
2. **Fonts:** Fraunces + Outfit (matches the official product pages; my recommendation), Fira Sans only (matches the rest of the store), or keep DM Serif Display + Montserrat?
3. **Background:** white with `#EDF1F0` sections (like the store), or keep the warmer cream?
4. **New sections (A2):** which of these are in scope? Navigation menu, trust bar, Shop by Concern, catalogue page, progress (numbers only), footer, 404, ingredients.
5. **Claims:** do you have proof and exact wording for "VerifEye" and "ISO-Certified"? Until then I won't use them.
6. **Photos:** who owns `hero-portrait.webp` / `permission-portrait.webp`, and is there a model release? Can you send official campaign photos and the SVG logo?
7. **Consent text (Signup):** may I restructure the layout (summary plus expandable full text) without changing the wording?
8. **Kits in "Optional extras":** should promotional kits like "4 Step Skincare Routine & Free Beauty Bag" be recommended?
