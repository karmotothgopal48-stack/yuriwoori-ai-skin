/* Signup field checks, mirroring the backend (app/services/contact.py, schemas.SignupRequest), so the form
   explains a problem before sending. The backend stays the authority and normalises the number. */

export const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

/** "+91 98765-43210" / "9876543210" -> "+919876543210"; null when it isn't a plausible mobile number. */
export function normalizeWhatsapp(raw) {
  const text = (raw ?? "").trim();
  if (!text || /[^\d\s()+\-.]/.test(text)) return null;
  const hasPlus = text.startsWith("+") || text.startsWith("00");
  let digits = text.replace(/\D/g, "");
  if (text.startsWith("00")) digits = digits.slice(2);
  if (!hasPlus) { // without + or 00 only an Indian number is accepted; others need their country code
    if (digits.length === 11 && digits.startsWith("0")) digits = digits.slice(1);
    if (digits.length === 10 && "6789".includes(digits[0])) digits = `91${digits}`;
    else if (!(digits.length === 12 && digits.startsWith("91"))) return null;
  }
  if (digits.length < 8 || digits.length > 15 || digits.startsWith("0")) return null;
  if (digits.startsWith("91") && digits.length !== 12) return null;
  return `+${digits}`;
}

export const validateSignup = ({ name, whatsapp, email }) => ({
  name: name.trim() ? "" : "Please enter your name",
  whatsapp: normalizeWhatsapp(whatsapp) ? "" : "Please enter a valid WhatsApp number (add the country code if it isn't an Indian number)",
  email: EMAIL_RE.test(email.trim()) ? "" : "Please enter a valid email address",
});

/** 'priya.sharma@example.com' -> 'p•••@example.com' (same as the backend's mask_email), for screens anyone at the
    device can see. */
export const maskEmail = (email) => {
  const at = (email ?? "").indexOf("@");
  return at > 0 ? `${email[0]}•••${email.slice(at)}` : "";
};
