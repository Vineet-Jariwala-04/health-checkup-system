"""Simple, clean, good-looking PDF report (reportlab, built-in fonts only)."""
import io
from datetime import datetime
from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

from .data import CHECKUPS, FLAG, TITLES, clean

ASSETS = Path(__file__).resolve().parent.parent / "assets"
W, H = A4

INK, MUTED, LINE = colors.HexColor("#0f2a33"), colors.HexColor("#5b727a"), colors.HexColor("#d6e6ea")
DEEP, TEAL, SOFT = colors.HexColor("#053b48"), colors.HexColor("#0e7490"), colors.HexColor("#f1f8fa")
KIND = {  # kind -> (strong, tint)
    "ok": (colors.HexColor("#047857"), colors.HexColor("#dcfce7")),
    "warn": (colors.HexColor("#b45309"), colors.HexColor("#fef3c7")),
    "bad": (colors.HexColor("#b91c1c"), colors.HexColor("#fee2e2")),
}
LEVEL = {"high": ("bad", "HIGH RISK"), "moderate": ("warn", "MODERATE RISK"),
         "mild": ("warn", "MILD RISK"), "low": ("ok", "LOW RISK")}
STEPS = {
    "high": ["Share this report with a doctor soon and book a proper check-up.",
             "Do not wait for symptoms - high-risk results deserve a clinical review.",
             "Repeat these checkups after your appointment to track progress."],
    "moderate": ["Book a routine check-up and discuss the highlighted areas.",
                 "Review diet, daily activity and sleep over the coming weeks.",
                 "Repeat the checkups in a few weeks to see if anything changes."],
    "mild": ["Keep an eye on the borderline result and recheck it regularly.",
             "Small habit changes (walking, less salt and sugar) go a long way.",
             "Mention this report at your next routine visit."],
    "low": ["Keep up your current healthy habits.",
            "Repeat checkups periodically, especially if your routine changes.",
            "Keep this report as a baseline for future comparison."],
}


def _style(name, **kw):
    base = dict(fontName="Helvetica", fontSize=10, leading=14, textColor=INK)
    base.update(kw)
    return ParagraphStyle(name, **base)


def _page(canvas, doc):
    canvas.saveState()
    # header band
    canvas.setFillColor(DEEP)
    canvas.rect(0, H - 3.7 * cm, W, 3.7 * cm, stroke=0, fill=1)
    canvas.setFillColor(TEAL)
    canvas.rect(W * 0.55, H - 3.7 * cm, W * 0.45, 3.7 * cm, stroke=0, fill=1)
    canvas.setFillColor(colors.HexColor("#22d3ee"))
    canvas.rect(0, H - 3.7 * cm - 0.12 * cm, W, 0.12 * cm, stroke=0, fill=1)
    logo = ASSETS / "logo-dark.png"
    if logo.exists():
        canvas.drawImage(str(logo), 1.6 * cm, H - 3.35 * cm, width=2.9 * cm, height=2.9 * cm,
                         preserveAspectRatio=True, mask="auto")
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 21)
    canvas.drawString(4.9 * cm, H - 1.95 * cm, "Health Checkup Report")
    canvas.setFont("Helvetica", 10)
    canvas.setFillColor(colors.HexColor("#bfeaf2"))
    canvas.drawString(4.9 * cm, H - 2.6 * cm, "Combined risk summary  |  AHV Hospital - Full body check-up")
    # footer
    canvas.setStrokeColor(LINE)
    canvas.line(2 * cm, 1.75 * cm, W - 2 * cm, 1.75 * cm)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(2 * cm, 1.25 * cm, "Statistical estimate and AI-generated suggestions only - not a diagnosis or a real prescription. "
                                         "Please consult a doctor.")
    canvas.drawRightString(W - 2 * cm, 1.25 * cm, f"Page {doc.page}")
    canvas.restoreState()


def build_report_pdf(user, checkups, level, message, insights=None):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=4.5 * cm, bottomMargin=2.3 * cm,
                            leftMargin=2 * cm, rightMargin=2 * cm, title="Health Checkup Report",
                            author="AHV Hospital")
    full = W - 4 * cm
    label = _style("label", fontSize=7.5, textColor=MUTED, fontName="Helvetica-Bold", leading=10)
    value = _style("value", fontSize=10.5, fontName="Helvetica-Bold", leading=14)
    h2 = _style("h2", fontSize=12.5, fontName="Helvetica-Bold", textColor=DEEP, leading=16, spaceAfter=6)
    body = _style("body", leading=15)

    els = []

    # --- patient details -------------------------------------------------
    def cell(k, v):
        return [Paragraph(k.upper(), label), Paragraph(clean(v) or "-", value)]
    info = Table([[cell("Patient", user.get("name", "")), cell("Age", user.get("age", "")),
                   cell("Email", user.get("email", "")),
                   cell("Generated", datetime.now().strftime("%d %b %Y, %I:%M %p"))]],
                 colWidths=[full * 0.26, full * 0.12, full * 0.34, full * 0.28])
    info.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SOFT), ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                              ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 9),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 9), ("LEFTPADDING", (0, 0), (-1, -1), 10)]))
    els += [info, Spacer(1, 16)]

    if not checkups:
        els.append(Paragraph("No checkups have been completed yet. Run the Heart, Diabetes, Sugar or Blood "
                             "Pressure checkups and generate the report again.", body))
        doc.build(els, onFirstPage=_page, onLaterPages=_page)
        return buf.getvalue()

    # --- overall level ----------------------------------------------------
    kind, tag = LEVEL.get(level, ("ok", "LOW RISK"))
    strong, tint = KIND[kind]
    head = Paragraph(f'<font color="{strong.hexval().replace("0x", "#")}"><b>Overall: {tag}</b></font>',
                     _style("lv", fontSize=14, leading=18))
    box = Table([[head], [Paragraph(clean(message), body)]], colWidths=[full - 0.35 * cm])
    box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), tint), ("LEFTPADDING", (0, 0), (-1, -1), 14),
                             ("RIGHTPADDING", (0, 0), (-1, -1), 14), ("TOPPADDING", (0, 0), (-1, 0), 12),
                             ("BOTTOMPADDING", (0, -1), (-1, -1), 12), ("TOPPADDING", (0, 1), (-1, 1), 0)]))
    wrap = Table([["", box]], colWidths=[0.35 * cm, full - 0.35 * cm])
    wrap.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), strong), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    els += [wrap, Spacer(1, 18), Paragraph("Your results", h2)]

    # --- results ----------------------------------------------------------
    pill_base = dict(fontName="Helvetica-Bold", fontSize=8, leading=10, alignment=TA_CENTER)
    rows, cmds = [], [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 11),
                      ("BOTTOMPADDING", (0, 0), (-1, -1), 11), ("LEFTPADDING", (1, 0), (1, -1), 12),
                      ("LINEBELOW", (0, 0), (-1, -2), 0.5, LINE), ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                      ("LEFTPADDING", (0, 0), (0, -1), 0), ("RIGHTPADDING", (0, 0), (0, -1), 0)]
    r = 0
    for key, _, _ in CHECKUPS:
        c = checkups.get(key)
        if not c:
            continue
        k, name = FLAG.get(c["flag"], FLAG[0])
        strong, tint = KIND[k]
        pill = Paragraph(name.upper(), ParagraphStyle(f"p{r}", textColor=strong, backColor=tint,
                                                      borderPadding=(4, 8, 4, 8), **pill_base))
        text = [Paragraph(f"<b>{TITLES[key]}</b>", _style(f"t{r}", fontSize=11, leading=14)),
                Paragraph(clean(c.get("detail")) or "-", _style(f"d{r}", textColor=MUTED, fontSize=9.5, leading=13)),
                Paragraph(str(c.get("updated_at", "")), _style(f"w{r}", textColor=MUTED, fontSize=8, leading=11))]
        rows.append(["", text, pill])
        cmds.append(("BACKGROUND", (0, r), (0, r), strong))
        r += 1
    t = Table(rows, colWidths=[0.28 * cm, full - 0.28 * cm - 3.2 * cm, 3.2 * cm])
    t.setStyle(TableStyle(cmds))
    els += [t, Spacer(1, 18)]

    # --- explainable results (one line each) ----------------------------------
    expl = (insights or {}).get("explanations") or {}
    reasons = [(key, expl[key]["reason"]) for key, _, _ in CHECKUPS if key in expl and expl[key].get("reason")]
    if reasons:
        small = _style("small", fontSize=8.5, textColor=MUTED, leading=12)
        els += [Paragraph("Why you got these results", h2),
                Paragraph("A short reason for each result, from the AI model. An approximate explanation, not a medical finding.", small),
                Spacer(1, 6)]
        for key, text in reasons:
            els.append(Paragraph(f"<b>{TITLES[key]}:</b> {escape(clean(text))}",
                                 _style(f"why{key}", fontSize=10, leading=14, spaceAfter=3)))
        els.append(Spacer(1, 14))

    # --- AI-generated draft prescription ---------------------------------------
    rx = (insights or {}).get("prescription")
    if rx:
        warn_style = _style("rxw", fontName="Helvetica-Bold", fontSize=9.5, leading=13, textColor=KIND["bad"][0])
        warn = Table([[Paragraph(escape(rx["disclaimer"]), warn_style)]], colWidths=[full])
        warn.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), KIND["bad"][1]), ("BOX", (0, 0), (-1, -1), 0.8, KIND["bad"][0]),
                                  ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                                  ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
        els += [KeepTogether([Paragraph("AI-generated prescription (draft)", h2), warn, Spacer(1, 8),
                              Paragraph(escape(rx["summary"]), body)]), Spacer(1, 6)]
        kinds = {"test": ("TEST", "ok"), "medicine": ("MEDICINE", "warn"), "followup": ("FOLLOW-UP", "ok"),
                 "urgent": ("URGENT", "bad"), "caution": ("CAUTION", "warn")}
        rrows, rcmds = [], [("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 8),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("LINEBELOW", (0, 0), (-1, -2), 0.5, LINE),
                            ("BOX", (0, 0), (-1, -1), 0.6, LINE), ("LEFTPADDING", (0, 0), (0, -1), 6)]
        for i, it in enumerate(rx["items"]):
            label, kind = kinds.get(it["kind"], (it["kind"].upper(), "ok"))
            strong, tint = KIND[kind]
            tag = Paragraph(label, ParagraphStyle(f"rt{i}", textColor=strong, backColor=tint, borderPadding=(3, 5, 3, 5),
                                                  fontName="Helvetica-Bold", fontSize=7.5, leading=10, alignment=TA_CENTER))
            rxmark = ' <font color="#b45309" size="7"><b>[Rx only]</b></font>' if it.get("rx") else ""
            text = [Paragraph(f"<b>{escape(it['title'])}</b>{rxmark}", _style(f"ri{i}", fontSize=10, leading=13)),
                    Paragraph(escape(it["detail"]), _style(f"rd{i}", fontSize=9, leading=12.5, textColor=MUTED))]
            rrows.append([tag, text])
        if rrows:
            rt = Table(rrows, colWidths=[2.6 * cm, full - 2.6 * cm])
            rt.setStyle(TableStyle(rcmds))
            els.append(rt)
        els += [Spacer(1, 8),
                Paragraph("<b>Please consult a doctor too. This prescription is AI generated - do not trust it blindly.</b>",
                          _style("rxend", fontSize=10, leading=14, textColor=KIND["bad"][0])),
                Spacer(1, 16)]

    # --- next steps ---------------------------------------------------------
    steps = [Paragraph("What you can do next", h2)] + [
        Paragraph(f'<font color="#0e7490"><b>{i}.</b></font>&nbsp;&nbsp;{s}', _style(f"s{i}", leading=16, leftIndent=0))
        for i, s in enumerate(STEPS.get(level, STEPS["low"]), 1)]
    els.append(KeepTogether(steps))
    doc.build(els, onFirstPage=_page, onLaterPages=_page)
    return buf.getvalue()
