"""
The skin-analysis report as a PDF (ReportLab), rendered from a saved report's content (services/reports.py).
Single column, large type: readable on a phone. No face image is included. Product images are fetched from
Shopify's CDN at a small size; one that can't be loaded is left out. Amounts are written "Rs." as on
yuriwoori.com (the standard PDF fonts have no ₹ glyph).
"""

import io
import logging
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from xml.sax.saxutils import escape

import httpx
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

logger = logging.getLogger(__name__)

JADE = colors.HexColor("#004647")
SOFT = colors.HexColor("#5b6b6a")
LINE = colors.HexColor("#d9e3df")
IST = timezone(timedelta(hours=5, minutes=30))
STEP_LABELS = {"cleanse": "Cleanse", "tone": "Tone", "treat": "Treat", "moisturize": "Moisturize", "protect": "Protect", "mask": "Mask"}


def money(value) -> str:
    return f"Rs. {value:,.0f}" if value is not None else ""


def when(iso: str | None) -> str:
    """'2026-10-13T11:20:27Z' -> '13 Oct 2026, 4:50 PM IST'."""
    if not iso:
        return ""
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(IST)
    return dt.strftime("%d %b %Y, %I:%M %p IST").lstrip("0")


@lru_cache(maxsize=128)
def _product_image_png(url: str) -> bytes | None:
    """A small PNG of a Shopify product image, or None."""
    try:
        sized = url + ("&" if "?" in url else "?") + "width=240"
        r = httpx.get(sized, timeout=8, follow_redirects=True)
        r.raise_for_status()
        img = PILImage.open(io.BytesIO(r.content))
        img.thumbnail((240, 240))
        if img.mode not in ("RGB", "L"):
            background = PILImage.new("RGB", img.size, "white")
            background.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[-1])
            img = background
        out = io.BytesIO()
        img.save(out, format="PNG")
        return out.getvalue()
    except Exception as exc:  # any network/decoding problem: the image is simply left out
        logger.warning("Report PDF: product image not loaded (%s)", type(exc).__name__)
        return None


def render(content: dict, report_url: str | None = None, image_loader=None) -> bytes:
    image_loader = image_loader or _product_image_png
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=10.5, leading=15)
    small = ParagraphStyle("small", parent=body, fontSize=9, leading=12.5, textColor=SOFT)
    h1 = ParagraphStyle("h1", parent=styles["Title"], fontSize=22, leading=27, textColor=JADE, alignment=TA_CENTER)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=15, leading=19, textColor=JADE, spaceBefore=12, spaceAfter=6)
    name_style = ParagraphStyle("name", parent=body, fontName="Helvetica-Bold", fontSize=11.5, leading=15, textColor=JADE)
    P = lambda text, style=body: Paragraph(text, style)  # noqa: E731
    e = lambda text: escape(str(text)) if text is not None else ""  # noqa: E731

    story = [P("YuriWoori Skin Analysis Report", h1)]
    who = f"Prepared for <b>{e(content.get('customer_name'))}</b> · " if content.get("customer_name") else ""
    story += [P(f"{who}Analysis of {e(when(content['analysis_date']))}", ParagraphStyle("c", parent=small, alignment=TA_CENTER)),
              Spacer(1, 6 * mm)]

    summary = []
    if content.get("skin_type"):
        summary.append(f"Skin type: <b>{e(content['skin_type'])}</b>")
    if content.get("overall_score") is not None:
        summary.append(f"Overall score: <b>{content['overall_score']}/100</b>")
    if content.get("body_part") == "hand":
        summary.append("Scan: hand")
    if summary:
        story.append(P(" &nbsp;·&nbsp; ".join(summary)))

    # measurements
    story.append(P("Your measurements", h2))
    rows = [[P("<b>Measurement</b>", small), P("<b>Your result</b>", small), P("<b>Typical</b>", small), P("<b>What it measures</b>", small)]]
    for m in content["metrics"]:
        concern = f"<br/><font color='#9a3b35'>Flagged: {e(m['concern'])}</font>" if m.get("concern") else ""
        rows.append([P(f"<b>{e(m['label'])}</b>"), P(f"{m['value']}/100{concern}"), P(str(m["benchmark"]) if m.get("benchmark") is not None else "-"),
                     P(e(m["measures"]), small)])
    table = Table(rows, colWidths=[34 * mm, 34 * mm, 20 * mm, 92 * mm], repeatRows=1)
    table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 5)]))
    story.append(table)
    if content.get("benchmark_note"):
        story.append(P(e(content["benchmark_note"]), small))

    # concerns
    story.append(P("What we noticed", h2))
    if content["concerns"]:
        story.append(P("Your scan crossed our levels for: " + ", ".join(e(c["phrase"]) for c in content["concerns"]) + ". "
                       "The routine below uses YuriWoori products whose own product information addresses these."))
    else:
        story.append(P("None of your measurements crossed our levels for a concern, so this is a simple care routine "
                       "with YuriWoori products made for general care."))

    products = content["products"]

    def product_block(handle: str, heading: str, notes: list[str]):
        p = products[handle]
        price = money(p["price"])
        if p.get("compare_at_price"):
            price += f" <font color='#5b6b6a'><strike>{money(p['compare_at_price'])}</strike> ({p['discount_percent']}% off)</font>"
        if not p.get("available"):
            price += " · <font color='#9a3b35'>currently unavailable</font>"
        text = [P(e(heading), small), P(e(p["name"]), name_style), P(price)]
        text += [P(n, small) for n in notes if n]
        text.append(P(f"<a href='{e(p['url'])}' color='#004647'>{e(p['url'])}</a>", small))
        png = image_loader(p["image_url"]) if p.get("image_url") else None
        left = Image(io.BytesIO(png), width=24 * mm, height=24 * mm, kind="proportional") if png else ""
        block = Table([[left, text]], colWidths=[28 * mm, 152 * mm])
        block.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 7)]))
        return KeepTogether([block])

    for period, title in (("AM", "Morning routine"), ("PM", "Evening routine")):
        steps = content["routine"].get(period) or []
        if not steps:
            continue
        story.append(P(title, h2))
        for s in steps:
            p = products[s["handle"]]
            notes = [e(s["reason"])]
            if p.get("how_to_use"):
                notes.append("<b>How to use:</b> " + e(p["how_to_use"]))
            story.append(product_block(s["handle"], f"Step {s['step_order']} · {STEP_LABELS.get(s['step'], s['step'])}", notes))

    if content.get("extras"):
        story.append(P("Optional extras", h2))
        for x in content["extras"]:
            p = products[x["handle"]]
            notes = [e(x["reason"])]
            if p.get("usage_quote"):
                notes.append("<b>How often:</b> " + e(p["usage_quote"]))
            elif p.get("how_to_use"):
                notes.append("<b>How to use:</b> " + e(p["how_to_use"]))
            story.append(product_block(x["handle"], "Extra", notes))

    # prices, as Shopify priced the routine
    story.append(P("Your routine on yuriwoori.com", h2))
    pricing = content.get("pricing")
    if pricing:
        lines = [[P("Subtotal"), P(money(pricing["subtotal"]))]]
        label = lambda d: f"Coupon code {d['title']}" if d.get("kind") == "code" else f"Automatic discount {d['title']} (no code needed)"  # noqa: E731
        lines += [[P(e(label(d))), P("- " + money(d["amount"]))] for d in pricing["discounts"]]
        lines.append([P("Shipping and taxes"), P("Calculated at Shopify checkout")])
        lines.append([P("<b>Total payable (before shipping)</b>"), P(f"<b>{money(pricing['total'])}</b>")])
        t = Table(lines, colWidths=[120 * mm, 60 * mm])
        t.setStyle(TableStyle([("LINEABOVE", (0, -1), (-1, -1), 0.6, JADE), ("ALIGN", (1, 0), (1, -1), "RIGHT")]))
        story += [t, P(f"For all the routine products, one of each, as priced by Shopify on {e(when(pricing['quoted_at']))} "
                       "with the discounts it applied automatically. Prices and discounts can change: the checkout shows "
                       "the final amount, including shipping.", small)]
    else:
        story.append(P("<b>Final price unavailable - verify at Shopify checkout.</b> Shopify couldn't price the routine "
                       "just now, so no total is shown here.", small))
    if report_url:
        story += [Spacer(1, 3 * mm), P(f"View your report and continue to checkout: <a href='{e(report_url)}' color='#004647'>{e(report_url)}</a>")]

    story += [Spacer(1, 6 * mm), P(e(content["disclaimer"]), small),
              P(f"Report generated {e(when(content['generated_at']))}. Product information and prices from yuriwoori.com.", small)]

    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm, bottomMargin=15 * mm,
                            title="YuriWoori Skin Analysis Report", author="YuriWoori")
    doc.build(story)
    return out.getvalue()
