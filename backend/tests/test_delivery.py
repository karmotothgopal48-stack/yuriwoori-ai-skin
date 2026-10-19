"""Results delivery providers and message (app/services/delivery.py). No network, no mail server."""

import httpx
import pytest

from app.core.config import settings
from app.services import delivery

def test_channels_are_off_until_configured(monkeypatch):
    for key in ("smtp_host", "smtp_from", "whatsapp_access_token", "whatsapp_phone_number_id", "whatsapp_otp_template", "whatsapp_results_template"):
        monkeypatch.setattr(settings, key, "")
    assert not delivery.configured("email") and not delivery.configured("whatsapp")
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_from", "YuriWoori <care@example.com>")
    assert delivery.configured("email")


def test_report_messages_carry_the_summary_prices_and_the_secure_link(monkeypatch):
    from tests_support import report_content
    content = report_content(monkeypatch)
    link = "https://skin.yuriwoori.com/report#t=abc"
    m = delivery.report_messages(content, link)
    assert "Hi Priya," in m["text"] and "attached as a PDF" in m["text"] and link in m["text"]
    assert "calm visible redness" in m["text"] and "automatic discount YWPL1500, no code needed -Rs. 1,500" in m["text"] and "total payable Rs. 4,440" in m["text"]
    assert f'<a href="{link}">' in m["html"]
    assert len(m["whatsapp"]) == 5 and m["whatsapp"][0] == "Priya" and m["whatsapp"][4] == link
    assert all("\n" not in v for v in m["whatsapp"])  # WhatsApp template variables are one line each


def test_whatsapp_template_request_follows_the_cloud_api_format(monkeypatch):
    sent = {}

    def post(url, json, headers, timeout):
        sent.update(url=url, json=json, headers=headers)
        return httpx.Response(200, json={"messaging_product": "whatsapp", "messages": [{"id": "wamid.ABC"}]})

    monkeypatch.setattr(delivery.httpx, "post", post)
    for key, value in (("whatsapp_access_token", "secret-token"), ("whatsapp_phone_number_id", "1234567890"),
                       ("whatsapp_api_version", "v21.0"), ("whatsapp_template_language", "en")):
        monkeypatch.setattr(settings, key, value)
    assert delivery.send_whatsapp_template("+919876543210", "yuriwoori_code", ["123456"], button_param="123456") == "wamid.ABC"
    assert sent["url"] == "https://graph.facebook.com/v21.0/1234567890/messages"
    assert sent["headers"] == {"Authorization": "Bearer secret-token"}
    assert sent["json"] == {
        "messaging_product": "whatsapp", "recipient_type": "individual", "to": "919876543210", "type": "template",
        "template": {"name": "yuriwoori_code", "language": {"code": "en"}, "components": [
            {"type": "body", "parameters": [{"type": "text", "text": "123456"}]},
            {"type": "button", "sub_type": "url", "index": "0", "parameters": [{"type": "text", "text": "123456"}]}]},
    }


def test_whatsapp_errors_are_reported_without_the_token(monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_access_token", "secret-token")
    monkeypatch.setattr(delivery.httpx, "post", lambda *a, **k: httpx.Response(400, json={"error": {"code": 132001, "message": "Template name does not exist"}}))
    with pytest.raises(delivery.DeliveryError) as err:
        delivery.send_whatsapp_template("+919876543210", "missing", ["x"])
    assert "132001" in str(err.value) and "secret-token" not in str(err.value)


def test_email_is_handed_to_the_smtp_server_with_starttls_and_login(monkeypatch):
    calls = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            calls.append(("connect", host, port))

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self, context):
            calls.append(("starttls",))

        def login(self, user, password):
            calls.append(("login", user))

        def send_message(self, msg):
            attachments = [(a.get_filename(), a.get_content_type(), len(a.get_content())) for a in msg.iter_attachments()]
            calls.append(("send", msg["To"], msg["Subject"], msg.is_multipart(), msg["Message-ID"], attachments))
            return {}

    monkeypatch.setattr(delivery.smtplib, "SMTP", FakeSMTP)
    for key, value in (("smtp_host", "smtp.example.com"), ("smtp_port", 587), ("smtp_username", "mailer"), ("smtp_password", "pw"),
                       ("smtp_from", "YuriWoori <care@example.com>"), ("smtp_security", "starttls")):
        monkeypatch.setattr(settings, key, value)
    message_id = delivery.send_email("priya@example.com", "Subject", "text", "<p>html</p>",
                                     attachments=[("report.pdf", b"%PDF-1.4 test", "application/pdf")], message_id="<report-1@example.com>")
    assert message_id == "<report-1@example.com>"  # the same id on a retry: mail clients show one message
    assert calls == [("connect", "smtp.example.com", 587), ("starttls",), ("login", "mailer"),
                     ("send", "priya@example.com", "Subject", True, "<report-1@example.com>", [("report.pdf", "application/pdf", 13)])]


def test_smtp_failures_become_delivery_errors(monkeypatch):
    class Down:
        def __init__(self, *a, **k):
            raise OSError("connection refused")

    monkeypatch.setattr(delivery.smtplib, "SMTP", Down)
    monkeypatch.setattr(settings, "smtp_security", "starttls")
    with pytest.raises(delivery.DeliveryError):
        delivery.send_email("priya@example.com", "Subject", "text")


def test_whatsapp_webhooks_must_be_signed_with_the_app_secret(monkeypatch):
    import hashlib
    import hmac
    body = b'{"entry": []}'
    monkeypatch.setattr(settings, "whatsapp_app_secret", "")
    assert not delivery.valid_signature(body, "sha256=anything")  # no secret configured: nothing is trusted
    monkeypatch.setattr(settings, "whatsapp_app_secret", "app-secret")
    good = "sha256=" + hmac.new(b"app-secret", body, hashlib.sha256).hexdigest()
    assert delivery.valid_signature(body, good)
    assert not delivery.valid_signature(body + b" ", good) and not delivery.valid_signature(body, None)
    assert not delivery.valid_signature(body, good.replace("sha256=", "sha1="))


def test_whatsapp_pdf_is_uploaded_as_media_then_sent_as_the_template_document(monkeypatch):
    calls = []

    def post(url, **kw):
        calls.append((url, kw))
        if url.endswith("/media"):
            return httpx.Response(200, json={"id": "MEDIA123"})
        return httpx.Response(200, json={"messages": [{"id": "wamid.DOC"}]})

    monkeypatch.setattr(delivery.httpx, "post", post)
    for key, value in (("whatsapp_access_token", "secret-token"), ("whatsapp_phone_number_id", "1234567890"), ("whatsapp_api_version", "v21.0")):
        monkeypatch.setattr(settings, key, value)
    media_id = delivery.upload_whatsapp_media(b"%PDF-1.4 report", "YuriWoori-skin-report.pdf")
    url, kw = calls[0]
    assert media_id == "MEDIA123" and url == "https://graph.facebook.com/v21.0/1234567890/media"
    assert kw["data"] == {"messaging_product": "whatsapp", "type": "application/pdf"}
    assert kw["files"]["file"] == ("YuriWoori-skin-report.pdf", b"%PDF-1.4 report", "application/pdf")
    assert kw["headers"] == {"Authorization": "Bearer secret-token"}

    delivery.send_whatsapp_template("+919876543210", "yuriwoori_report", ["a", "b", "c", "d", "e"],
                                    header_document={"id": media_id, "filename": "YuriWoori-skin-report.pdf"})
    components = calls[1][1]["json"]["template"]["components"]
    assert components[0] == {"type": "header", "parameters": [{"type": "document", "document": {"id": "MEDIA123", "filename": "YuriWoori-skin-report.pdf"}}]}
    assert components[1]["type"] == "body" and len(components[1]["parameters"]) == 5


def test_a_refused_media_upload_is_an_error_not_a_send(monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_access_token", "secret-token")
    monkeypatch.setattr(delivery.httpx, "post", lambda url, **kw: httpx.Response(400, json={"error": {"code": 131053, "message": "Media upload error"}}))
    with pytest.raises(delivery.DeliveryError) as err:
        delivery.upload_whatsapp_media(b"%PDF", "r.pdf")
    assert "131053" in str(err.value) and "secret-token" not in str(err.value)


def test_report_emails_send_replies_to_the_team(monkeypatch):
    from tests_support import report_content
    sent = []

    class FakeSMTP:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *e): return False
        def starttls(self, context): pass
        def login(self, u, p): pass
        def send_message(self, msg):
            sent.append(msg)
            return {}

    monkeypatch.setattr(delivery.smtplib, "SMTP", FakeSMTP)
    for key, value in (("smtp_host", "smtp.example.com"), ("smtp_from", "YuriWoori <automation@example.com>"), ("smtp_security", "starttls")):
        monkeypatch.setattr(settings, key, value)
    delivery.send_email("priya@example.com", "Subject", "text", reply_to="support@example.com")
    assert sent[0]["Reply-To"] == "support@example.com"
    delivery.send_email("priya@example.com", "Subject", "text")
    assert sent[1]["Reply-To"] is None  # verification codes etc.: no Reply-To unless given

    m = delivery.report_messages(report_content(monkeypatch), "https://x/report#t=a", reply_to="support@example.com")
    assert "Just reply to this email - it reaches our team at support@example.com." in m["text"] and "support@example.com" in m["html"]
    assert "reply to this email" not in delivery.report_messages(report_content(monkeypatch), "https://x/report#t=a")["text"].lower()


@pytest.mark.parametrize("mode", ["tls", "STARTTLS_typo", "", "plain"])
def test_an_unknown_smtp_mode_is_refused_instead_of_sending_unencrypted(monkeypatch, mode):
    connected = []
    monkeypatch.setattr(delivery.smtplib, "SMTP", lambda *a, **k: connected.append(a))
    monkeypatch.setattr(settings, "smtp_security", mode)
    with pytest.raises(delivery.DeliveryError, match="SMTP_SECURITY must be starttls"):
        delivery.send_email("priya@example.com", "Subject", "text")
    assert connected == []  # never connected, so nothing (and no password) was sent


def test_the_mode_is_case_insensitive_and_no_login_goes_out_unencrypted(monkeypatch):
    monkeypatch.setattr(settings, "smtp_security", " StartTLS ")
    assert delivery.smtp_mode() == "starttls"
    monkeypatch.setattr(settings, "smtp_security", "SSL")
    assert delivery.smtp_mode() == "ssl"
    monkeypatch.setattr(settings, "smtp_security", "none")
    monkeypatch.setattr(settings, "smtp_username", "mailer@example.com")
    with pytest.raises(delivery.DeliveryError, match="without encryption"):
        delivery.smtp_mode()


def test_an_email_the_server_accepted_is_not_reported_failed_when_only_the_goodbye_fails(monkeypatch):
    """A failure after the server took the message (QUIT) must not mark it failed: a retry would send it twice."""
    class QuitFails:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            raise delivery.smtplib.SMTPResponseException(421, b"closing")

        def starttls(self, context):
            pass

        def login(self, user, password):
            pass

        def send_message(self, msg):
            return {}

    monkeypatch.setattr(delivery.smtplib, "SMTP", QuitFails)
    for key, value in (("smtp_host", "smtp.example.com"), ("smtp_port", 587), ("smtp_username", ""),
                       ("smtp_from", "YuriWoori <care@example.com>"), ("smtp_security", "starttls")):
        monkeypatch.setattr(settings, key, value)
    assert delivery.send_email("priya@example.com", "Subject", "text", message_id="<r@example.com>") == "<r@example.com>"


def test_whatsapp_template_variables_are_cleaned_and_bounded():
    assert delivery.template_text("a\nb\t c      d") == "a b c d"  # WhatsApp refuses new lines, tabs and 5+ spaces
    assert delivery.template_text("") == "-"  # and empty variables
    long = ", ".join(f"Product {i}" for i in range(100))
    short = delivery.template_text(long, delivery.TEMPLATE_PARAM_MAX)
    assert len(short) <= delivery.TEMPLATE_PARAM_MAX and short.endswith("…")


def test_a_whatsapp_timeout_says_the_message_may_have_been_sent(monkeypatch):
    for key, value in (("whatsapp_access_token", "t"), ("whatsapp_phone_number_id", "1")):
        monkeypatch.setattr(settings, key, value)

    def read_timeout(*a, **k):
        raise httpx.ReadTimeout("slow")
    monkeypatch.setattr(delivery.httpx, "post", read_timeout)
    with pytest.raises(delivery.DeliveryError, match="may have been sent"):
        delivery.send_whatsapp_template("+919876543210", "tpl", ["x"])

    def refused(*a, **k):
        raise httpx.ConnectError("refused")
    monkeypatch.setattr(delivery.httpx, "post", refused)
    with pytest.raises(delivery.DeliveryError) as exc:
        delivery.send_whatsapp_template("+919876543210", "tpl", ["x"])
    assert "may have been sent" not in str(exc.value)
