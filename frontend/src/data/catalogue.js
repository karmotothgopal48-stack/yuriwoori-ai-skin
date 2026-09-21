/* Real YuriWoori catalogue snapshot — source: https://yuriwoori.com/products.json (2026-09-20).
   Names, prices and images are official. Replace with a live catalogue fetch when the backend is connected. */
export const SITE_URL = "https://yuriwoori.com";
export const productUrl = (handle) => `${SITE_URL}/products/${handle}`;

export const CATALOGUE = [
  {
    "handle": "cloud-cream-korean-aqua-hyaluronic-moisture-cream",
    "name": "Aqua Hyaluronic Moisture Cream / Cloud Cream",
    "price": 2025,
    "step": "Moisturize",
    "image": "https://cdn.shopify.com/s/files/1/0842/4865/7954/files/74.webp"
  },
  {
    "handle": "hyaluronic-acid-all-in-one-moisture-ampoule",
    "name": "Hyaluronic Acid All-In One Moisture Ampoule",
    "price": 1710,
    "step": "Treat",
    "image": "https://cdn.shopify.com/s/files/1/0842/4865/7954/files/17_07c9d179-5857-4d04-b396-0e63494ea2fc.webp"
  },
  {
    "handle": "niacinamide-all-in-one-brightening-ampoule",
    "name": "Niacinamide All-In One Brightening Ampoule",
    "price": 1710,
    "step": "Treat",
    "image": "https://cdn.shopify.com/s/files/1/0842/4865/7954/files/111.webp"
  },
  {
    "handle": "aloevera-soothing-gel",
    "name": "Fresh Aloe Soothing Gel",
    "price": 675,
    "step": "Soothe",
    "image": "https://cdn.shopify.com/s/files/1/0842/4865/7954/files/89.webp"
  },
  {
    "handle": "fresh-pink-watermelon-soothing-gel",
    "name": "Fresh Pink Watermelon Soothing Gel",
    "price": 675,
    "step": "Soothe",
    "image": "https://cdn.shopify.com/s/files/1/0842/4865/7954/files/96.webp"
  },
  {
    "handle": "bubble-soothing-toner",
    "name": "Bubble Soothing Toner",
    "price": 765,
    "step": "Tone",
    "image": "https://cdn.shopify.com/s/files/1/0842/4865/7954/files/120.webp"
  },
  {
    "handle": "bubble-anti-aging-toner",
    "name": "Bubble Anti-Aging Toner",
    "price": 765,
    "step": "Tone",
    "image": "https://cdn.shopify.com/s/files/1/0842/4865/7954/files/135.webp"
  },
  {
    "handle": "bubble-brightening-toner",
    "name": "Bubble Brightening Toner",
    "price": 765,
    "step": "Tone",
    "image": "https://cdn.shopify.com/s/files/1/0842/4865/7954/files/128.webp"
  },
  {
    "handle": "intense-water-drop-moisture",
    "name": "Intense Water Drop Moisture Cream",
    "price": 2025,
    "step": "Moisturize",
    "image": "https://cdn.shopify.com/s/files/1/0842/4865/7954/files/103.webp"
  },
  {
    "handle": "hyaluronic-cooling-sun-gel",
    "name": "Hyaluronic Cooling Sun Gel",
    "price": 1620,
    "step": "Protect",
    "image": "https://cdn.shopify.com/s/files/1/0842/4865/7954/files/9_065ae886-3b7c-4bb8-aa9e-5e28bf3684ca.webp"
  },
  {
    "handle": "rice-facial-deep-cleansing-foam",
    "name": "Rice Facial Deep Cleansing Foam",
    "price": 855,
    "step": "Cleanse",
    "image": "https://cdn.shopify.com/s/files/1/0842/4865/7954/files/1_9c5cf8b6-9d8e-41df-b3f4-0f2b872022df.webp"
  },
  {
    "handle": "aloevera-facial-deep-cleansing-foam",
    "name": "Aloevera Facial Deep Cleansing Foam",
    "price": 855,
    "step": "Cleanse",
    "image": "https://cdn.shopify.com/s/files/1/0842/4865/7954/files/153.webp"
  },
  {
    "handle": "vitamin-facial-deep-cleansing-foam",
    "name": "Vitamin Facial Deep Cleansing Foam",
    "price": 855,
    "step": "Cleanse",
    "image": "https://cdn.shopify.com/s/files/1/0842/4865/7954/files/144.webp"
  }
];

export const getProduct = (handle) => CATALOGUE.find((p) => p.handle === handle);
