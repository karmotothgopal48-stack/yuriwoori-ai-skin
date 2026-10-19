"""WhatsApp numbers and masked contact details (app/services/contact.py)."""

import pytest

from app.services.contact import mask_email, mask_phone, normalize_whatsapp


@pytest.mark.parametrize("raw,expected", [
    ("9876543210", "+919876543210"),          # Indian mobile without country code
    ("098765 43210", "+919876543210"),        # national trunk 0
    ("+91 98765-43210", "+919876543210"),
    ("0091 9876543210", "+919876543210"),     # 00 international prefix
    ("+1 (415) 555-0123", "+14155550123"),    # other countries need their code
    ("+44 7700 900123", "+447700900123"),
])
def test_whatsapp_numbers_become_international_format(raw, expected):
    assert normalize_whatsapp(raw) == expected


@pytest.mark.parametrize("raw", ["", None, "12345", "+91 98765", "+91 98765 432101", "abc9876543210", "5876543210",
                                 "+0123456789", "1234567890123456"])
def test_implausible_numbers_are_refused(raw):
    assert normalize_whatsapp(raw) is None


def test_contacts_are_masked_for_logs_and_screens():
    assert mask_phone("+919876543210") == "+91•••••••210"
    assert mask_email("priya.sharma@example.com") == "p•••@example.com"
    assert mask_email(None) is None and mask_phone("") is None
