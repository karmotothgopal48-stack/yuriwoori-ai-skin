/* YuriWoori's official WhatsApp contact: the single source of truth for WhatsApp links in this app.
   Verified 2026-10-06 on the official store, yuriwoori.com (Shopify shop yuriwoori.myshopify.com): its header
   "Whatsapp" link is https://wa.me/918655954965 on the home, contact and product pages, and its product pages
   use the same number for their own order links. Digits only, in international format (91 = India), as wa.me
   requires. If the store changes its WhatsApp number, update it here only. */
export const YURIWOORI_WHATSAPP_NUMBER = "918655954965";

/** The pre-filled enquiry for one product: its official name and official product page. */
export const productEnquiryMessage = ({ name, url }) =>
  `Hi YuriWoori, I'm interested in ${name}.\n\nProduct:\n${url}\n\nCan you please help me with this product?`;

/** https://wa.me/<official number>?text=<encoded enquiry>, or null without a real product name and URL. */
export function whatsappProductLink(product) {
  if (!product?.name || !product?.url) return null;
  return `https://wa.me/${YURIWOORI_WHATSAPP_NUMBER}?text=${encodeURIComponent(productEnquiryMessage(product))}`;
}
