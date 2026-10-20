"""Customer contact details: WhatsApp numbers in international format, and masked forms for logs/UI."""

import re

DEFAULT_COUNTRY_CODE = "91"  # the store sells in India (INR): a bare 10-digit mobile number is Indian


def normalize_whatsapp(raw: str | None) -> str | None:
    """'+91 98765-43210', '098765 43210', '9876543210' -> '+919876543210'. None when it isn't a plausible
    international mobile number (8-15 digits including the country code, E.164)."""
    if not raw:
        return None
    text = raw.strip()
    if re.search(r"[^\d\s()+\-.]", text):
        return None
    has_plus = text.startswith("+") or text.startswith("00")
    digits = re.sub(r"\D", "", text)
    if text.startswith("00"):
        digits = digits[2:]
    if not has_plus:  # without + or 00 only an Indian number is accepted; others need their country code
        if len(digits) == 11 and digits.startswith("0"):  # national trunk prefix
            digits = digits[1:]
        if len(digits) == 10 and digits[0] in "6789":  # Indian mobile without the country code
            digits = DEFAULT_COUNTRY_CODE + digits
        elif not (len(digits) == 12 and digits.startswith(DEFAULT_COUNTRY_CODE)):
            return None
    if not 8 <= len(digits) <= 15 or digits.startswith("0"):
        return None
    if digits.startswith(DEFAULT_COUNTRY_CODE) and len(digits) != 12:  # India: +91 and 10 digits
        return None
    return "+" + digits


def mask_phone(number: str | None) -> str | None:
    """'+919876543210' -> '+91•••••••210'."""
    if not number:
        return None
    return number[:3] + "•" * max(len(number) - 6, 0) + number[-3:]


def mask_email(email: str | None) -> str | None:
    """'priya.sharma@example.com' -> 'p•••@example.com'."""
    if not email or "@" not in email:
        return None
    local, domain = email.split("@", 1)
    return f"{local[:1]}•••@{domain}"
