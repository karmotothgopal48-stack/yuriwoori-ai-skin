# YuriWoori brand sheet

Researched on 19 October 2026 from the live official store, https://yuriwoori.com: the home page, `/collections/all-products`,
four product pages (Cloud Cream, Hyaluronic Acid All-In-One Moisture Ampoule, Bubble Brightening Toner, Real Gold Hydro-Gel
Eye Patch), `/pages/about-us` and `/pages/yw-insights`, plus the public product feed `/products.json`.

Colors and fonts below were read from the CSS the browser actually computed on those pages (headless Chrome), not guessed.
Where something could not be confirmed, it says so.

> The official store runs the Shopify theme "Glowing" 1.2.4. Most of the site uses that theme's styles. The product pages
> use a newer custom layout with its own fonts and colors (noted separately below), which looks like the direction the
> brand is moving in.

---

## 1. Logo

| Item | Finding |
|---|---|
| Official file | `GREEN_LOGO.png` (raster PNG) on the store CDN. Alt text: *"Yuri Woori : Luxury Elixirs Straight From Korea"*. **No SVG version is published.** |
| Lockup | Stacked: Korean glyph 유리 with "KOREA" beneath, heart-leaf mark, "yuri woori" wordmark, and the tagline "LUXURY ELIXIRS, STRAIGHT FROM KOREA" in very small capitals. |
| Color | Single-color deep teal-green (close to `#006968` / `#004E4D`; exact value not readable from a PNG). |
| Light / dark versions | The store only shows the green version on white. This project already has `yuriwoori-logo-green.png` and `yuriwoori-logo-white.png` (812×812 PNG), `yuriwoori-wordmark-green.png`, `yuriwoori-heart-green.png` and `yuriwoori-heart-white.png`. |
| Clear space | No guideline is published. The store leaves at least the height of the heart mark clear around the logo. |
| Small sizes | At header size (~40 px wide) the tagline can't be read. The store keeps the logo ~115 px wide. Below ~80 px, use the logo without the tagline. |

**Needed from you:** the official logo as SVG (or AI/EPS/PDF), with and without the tagline, in green and white.

---

## 2. Color palette (measured)

### Site-wide theme (Glowing theme settings and computed styles)

| Role | Hex | Where it appears |
|---|---|---|
| **Primary action green** | `#006968` | Subscribe button, "Add selected to cart", discount badges ("10%"), button borders. The most used brand color (45 backgrounds and 22 borders on the home page). |
| Deep green | `#004E4D` | Festival banner on product pages, notice toast, accent text |
| Theme "primary" setting | `#4E7661` | Theme variable `--gsp-primary-color` (muted sage-green); small accents |
| Review accent | `#108474` | Judge.me review stars and links (third-party widget) |
| Heading text | `#000000` | All theme headings (h1–h3) |
| Body text | `#7E7E7E` | Theme body text. **Fails WCAG AA on white (4.06:1)**, so don't copy it as-is. |
| Muted text | `#737373`, `#9A9A9A` | Secondary text (`#9A9A9A` is only 2.81:1 on white) |
| Background | `#FFFFFF` | Page |
| Section / footer background | `#EDF1F0` | Footer and tinted sections (pale grey-green) |
| Soft neutral | `#F8F8F8`, `#F5F5F5` | Breadcrumb bar, inputs |
| Border | `#EEEEE0` | Theme border color |

### Product-page layout (newer custom design)

| Role | Hex | Where it appears |
|---|---|---|
| Ink (text) | `#1C2B28` | Main text (191 uses on the Cloud Cream page) |
| Secondary ink | `#4A5B55`, `#5F706B`, `#3A4C46` | Supporting text |
| Deep greens | `#0B3F38`, `#16645A`, `#004E4D` | Banner gradient and accents |
| Mint tints | `#E5F1EB`, `#EAF4F0`, `#DFF0EB` | Chips and soft panels |
| Rice cream | `#F8F4EA` (border `#EFE7D6`, `#DCD4C2`) | "100% Authentic" band and story cards |
| Hairline | `#E4EAE6` | Card borders |
| **Gold** | `#C9A15A` | "골드 리추얼 · THE GOLD RITUAL" eyebrow, rating star (Gold Ritual line) |

### Current app (`frontend/src/index.css`) compared with the official palette

| App token | App value | Closest official | Note |
|---|---|---|---|
| `jade` | `#005C5D` | `#006968` | Slightly darker than the official action green |
| headings (hard-coded 88×) | `#004647` | `#004E4D` | Close; not a token |
| `cream` (page background) | `#F1F5EB` | `#EDF1F0` / `#FFFFFF` | The app is warmer and yellower than the store's grey-green |
| `ink` | `#1C2B2A` | `#1C2B28` | Effectively the same |
| `ink-soft` | `#55676A` | `#4A5B55` | Close (passes AA: 5.38:1 on cream) |
| `sage` | `#528778` | `#4E7661` | Close. **Fails AA as small text on cream (3.73:1)**, yet it's used for 10–11 px eyebrows |

---

## 3. Typography (measured)

| Where | Headings | Body / UI | Notes |
|---|---|---|---|
| Site-wide theme | **Fira Sans** 400, 40 px (h2), 48 px (h1), sentence case, no letter-spacing | **Fira Sans** 400, 15 px, line-height 1.6 | Fira Sans 400/500/600/700 loaded. Main navigation is uppercase Fira Sans 600 with slight tracking. Buttons are 600 weight, not uppercase, letter-spacing 0.8 px. |
| Product pages (newer layout) | **Fraunces** (serif), 600, 36 px product title, 30 px section titles | **Outfit** (sans-serif) | Eyebrows are small uppercase with wide tracking ("THE GOLD RITUAL · YURI WOORI"), sometimes in Korean first ("골드 리추얼"). |
| Current app | DM Serif Display 400 | Montserrat | **Neither font is used on the official site.** |

**Recommendation:** Fraunces for display headings with Outfit for body and UI. That's two families, both on Google Fonts, and it
matches the official product pages. It also keeps the "elegant serif headline" feel the current app has. Your approval is needed (see the audit).

---

## 4. Photography style (observed)

**Product packshots (collection and product pages)**
- Pure white background, product centred, shot straight-on at eye level.
- A soft **mirror reflection** under each product. No hard drop shadow.
- Square crops in grids, all products at a similar scale and centred.
- Even, diffused studio light with gentle highlights on glossy jars and tubes.
- Gallery images also include texture or swatch shots and lifestyle images (5–9 images per product in `/products.json`).

**Campaign and banner photography (home page carousel)**
- Seasonal and promotional: at the time of research, a pink "Flash Sale" banner with a Korean model holding product sachets over a pink beauty bag, in a soft pink studio with window-light shadows.
- Models are East Asian women with natural, dewy makeup and soft daylight.
- Banners have text baked into the image (not live text), in 1905×770 desktop and separate mobile versions.

**Current app imagery** (`frontend/public/assets/`): `hero-portrait.webp` (960×1200, 35 KB) and `permission-portrait.webp`
(800×1000) show a model holding the **Real Gold Hydro-Gel Eye Patch** jar (a real YuriWoori product), on a light background.
**Who shot these and whether there is a model release is unknown. Please confirm.** `ai-skin-analysis-face.png` is 347 KB (PNG,
462×540) and isn't referenced by the current code.

---

## 5. Packaging (from the official product photos)

| Line | Look |
|---|---|
| Hydration and everyday (cleansing foams, Bubble toners, Cloud Cream, Intense Water Drop, Hyaluronic Ampoule, Sun Gel) | Mint or aqua-green frosted or translucent packs with white caps; dark teal 유리 logo and serif product name; tubes, pump bottles, dropper ampoules and round jars |
| Gold Ritual (Real Gold Hydro-Gel Eye Patch) | Black jar with a **gold** lid and gold text |
| Vita-C (eye patch, mask) | Aqua jar; orange and citrus accents on the mask |
| Natural Garden Essence sheet masks (Aloe, Green Tea, Avocado, Pomegranate, Blueberry, Papaya, Black Charcoal) | Flat pouches with fruit or botanical illustrations, one color per ingredient |
| Hand creams (Strawberry, Peach, Avocado) | Small pocket tubes in fruit colors |
| Kits | Pink "beauty bag" (festival / flash-sale kits) |

---

## 6. Brand promises (exact wording found on yuriwoori.com)

| Claim | Found? | Where / exact wording |
|---|---|---|
| Authentic Korean skincare | ✅ | "100% authentic, straight from Korea"; "정품 · 100% AUTHENTIC"; "Made in Korea by Korea Cospack Co., Ltd · Officially imported by Accomplish Trades Solutions, Gurugram · Batch-coded, sealed packs" |
| Vegan | ✅ | "Vegan · Made in Korea"; "Vegan & cruelty-free, certified" (product pages) |
| Cruelty-free | ✅ | "Vegan and cruelty-free, gentle enough for every day"; comparison table: "✓ Vegan · Cruelty-free · Paraben-free" |
| Paraben / sulfate free | ✅ | "✓ Paraben & sulfate free · Vegan-friendly" |
| **VerifEye anti-counterfeit sticker** | ❌ **Not found** | Not on any page I checked (home, collection, 4 product pages, About). Please confirm before we show it. |
| **ISO-certified** | ❌ **Not found** | Not on any page checked. |
| Dermatologist-tested / clinically proven | ❌ Not found | None of those exact words on the pages checked. |
| India-based, Korea-inspired | ✅ | About: founded in 2024 and "operated by 'Accomplish Trades Solutions Private Limited'"; brings "Korean skincare innovation to India while carefully aligning it with the unique needs of Indian skin". Founder Director & CEO: Mrs. Arti Srivastava. |
| Shipping / payment | ✅ | "COD available across India"; "Free shipping over ₹399"; "Ships in 24–48 hrs · Easy Returns"; also sold on Amazon, Nykaa and Myntra. |

---

## 7. Tone of voice

Calm, warm and ritual-based. Phrases from the site:
- "Glow brighter. Hydrate deeper. Radiate naturally." (home)
- "Complete the ritual", "KOREAN BEAUTY RITUAL", "THE GOLD RITUAL", "Daily Korean Essential"
- "gentle enough for every day — all skin types welcome"
- "a morning pair to de-puff before work, or a night pair for repair while you wind down"
- "Packed with bubble wrap, a hand-checked seal and a small thank-you card inside."

Style: sentence case for headings; small uppercase eyebrows; Korean words used as accents (정품, 골드 리추얼); Indian
price format "Rs." in the theme and "₹" on product pages. The brand voice never sounds clinical or medical.

---

## 8. Product taxonomy (from the store navigation)

**Shop by Concern** (`/collections/…`)
Breakouts & Acne · Pores & Oil Control · Dryness · Dullness & Uneven Tone · Dark Spots · Redness & Sensitivity · Fine Lines & Wrinkles

**Shop by Category**
Face Mask · Eye Patch · Hand Cream · Ampoule · Soothing Gel · Toner · Moisturising Cream · Make Up Remover · Sun Gel · Cleanser

**Other:** All Products · Make Your Own Bundle · kits (4-Step Skincare Routine, Mini Kit, Festival Kit, Winter Glow Duo, Hydration Rescue Duo, Hand Care Trio).
The public feed lists **37 products** (`/products.json`); the "All Products" collection shows 29.

---

## 9. Footer and social (official)

Columns: Company (toll-free 1800 202 3307, support@yuriwoori.com) · Useful Links · Information (About Us, YW Insight) ·
Policies (Privacy, Terms, Shipping & Delivery, Return & Refund) · Newsletter (email + "Subscribe").
Social icons: Instagram, X, Facebook, Pinterest, YouTube, WhatsApp, LinkedIn. Payment badges: Visa, Mastercard, Net Banking, UPI.
Note: the footer heading is misspelled on the official site ("Infomation").

**YW Insights blog:** `/pages/yw-insights` currently shows **no content** (an empty page between the breadcrumb and the
footer), and `/blogs/yw-insights` returns 404. There is nothing to research there yet.
