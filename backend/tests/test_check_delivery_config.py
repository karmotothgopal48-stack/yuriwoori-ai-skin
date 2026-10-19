"""scripts/check_delivery_config.py sends nothing unless asked, and a test email only to a listed test address."""

import importlib.util
import os

import pytest

from app.core.config import settings
from app.services import delivery

_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "check_delivery_config.py")
_spec = importlib.util.spec_from_file_location("check_delivery_config", _path)
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)


@pytest.fixture
def sent(monkeypatch):
    calls = []
    monkeypatch.setattr(delivery, "send_email", lambda to, subject, text, html=None, attachments=(), message_id=None, reply_to=None:
                        (calls.append({"to": to, "subject": subject, "reply_to": reply_to}), "<test@example.com>")[1])
    monkeypatch.setattr(settings, "delivery_test_emails", "Tester@Example.com, other@example.com")
    monkeypatch.setattr(settings, "delivery_reply_to", "support@example.com")
    return calls


def test_a_test_email_goes_only_to_a_listed_address(sent, capsys):
    check.send_test_email("stranger@example.com", email_ok=True)
    assert sent == [] and "must be listed in DELIVERY_TEST_EMAILS" in capsys.readouterr().out
    check.send_test_email("tester@example.com", email_ok=True)  # case-insensitive match
    assert sent == [{"to": "tester@example.com", "subject": "YuriWoori email test", "reply_to": "support@example.com"}]
    assert "accepted by the SMTP server" in capsys.readouterr().out


def test_no_test_email_when_the_settings_are_not_working(sent, capsys):
    check.send_test_email("tester@example.com", email_ok=False)
    assert sent == [] and "fix the email settings above first" in capsys.readouterr().out


def test_a_refused_test_email_is_reported_not_claimed(sent, monkeypatch, capsys):
    def refused(*a, **k):
        raise delivery.DeliveryError("SMTP: SMTPAuthenticationError: 535")
    monkeypatch.setattr(delivery, "send_email", refused)
    check.send_test_email("tester@example.com", email_ok=True)
    out = capsys.readouterr().out
    assert "not accepted by the SMTP server" in out and "accepted by the SMTP server for" not in out


@pytest.mark.parametrize("port,mode", [(465, "starttls"), (587, "ssl")])
def test_a_port_that_does_not_match_the_tls_mode_is_reported_before_connecting(monkeypatch, capsys, port, mode):
    import smtplib
    tried = []
    monkeypatch.setattr(smtplib, "SMTP", lambda *a, **k: tried.append(a))
    monkeypatch.setattr(smtplib, "SMTP_SSL", lambda *a, **k: tried.append(a))
    for key, value in (("smtp_host", "smtp.gmail.com"), ("smtp_from", "x@example.com"), ("smtp_username", "x@example.com"),
                       ("smtp_password", "not-a-real-password"), ("smtp_port", port), ("smtp_security", mode)):
        monkeypatch.setattr(settings, key, value)
    assert check.check_email() is False and tried == []
    out = capsys.readouterr().out
    assert "use 587 with starttls, or 465 with ssl" in out and "not-a-real-password" not in out
