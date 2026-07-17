"""Erstellt eine professionell gestaltete Rechnung als PDF (analog zum InvoiceView im Original)."""
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle, Paragraph,
                                 Spacer, Image, HRFlowable)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_LEFT

from utils import eur, fmt_date, anrede

INVOICE_TITLES = {
    "normal": "RECHNUNG",
    "abschlag": "ABSCHLAGSRECHNUNG",
    "schluss": "SCHLUSSRECHNUNG",
}

INK = colors.HexColor("#1F2A24")
INK_SOFT = colors.HexColor("#5B655D")
RULE = colors.HexColor("#C9CFC3")
GOLD = colors.HexColor("#A9812F")


def invoice_net(items):
    return sum(float(i["qty"] or 0) * float(i["price"] or 0) for i in items)


def invoice_total(invoice, items):
    net = invoice_net(items)
    if invoice.get("kleinunternehmer"):
        return net
    return net * (1 + float(invoice.get("tax_rate") or 0) / 100)


def generate_invoice_pdf(path, invoice, items, company, customer, abschlag_info=None):
    styles = getSampleStyleSheet()
    normal = ParagraphStyle("normal", parent=styles["Normal"], fontName="Helvetica",
                             fontSize=9.5, leading=14, textColor=INK)
    small = ParagraphStyle("small", parent=normal, fontSize=8, textColor=INK_SOFT)
    heading = ParagraphStyle("heading", parent=styles["Heading1"], fontSize=17,
                              textColor=INK, spaceAfter=10)
    title = ParagraphStyle("title", parent=normal, fontSize=9, textColor=INK_SOFT,
                            alignment=TA_RIGHT)

    doc = SimpleDocTemplate(path, pagesize=A4, topMargin=22 * mm, bottomMargin=20 * mm,
                             leftMargin=20 * mm, rightMargin=20 * mm)
    story = []

    # Kopf: Logo links, "RECHNUNG" rechts
    logo_path = company.get("logo") or ""
    if logo_path and os.path.exists(logo_path):
        head_table = Table(
            [[Image(logo_path, width=45 * mm, height=22 * mm, kind="proportional"),
              Paragraph("RECHNUNG", title)]],
            colWidths=[110 * mm, 60 * mm],
        )
    else:
        head_table = Table([["", Paragraph("RECHNUNG", title)]], colWidths=[110 * mm, 60 * mm])
    head_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(head_table)
    story.append(Spacer(1, 8 * mm))

    addr_left = "<br/>".join(filter(None, [
        company.get("name"), company.get("owner"),
        company.get("addressLine1"), company.get("addressLine2"),
        "", customer.get("firma"), customer.get("ansprechpartner"),
        customer.get("address_line1"), customer.get("address_line2"),
    ]))
    meta_rows = [
        ["Rechnungsnummer:", invoice.get("number", "")],
        ["Rechnungsdatum:", fmt_date(invoice.get("date", ""))],
        ["Zahlungsbedingungen:", f"{invoice.get('payment_terms_days', '')} Tage"],
        ["Fälligkeitsdatum:", fmt_date(invoice.get("due_date", ""))],
        ["Kundennummer:", customer.get("kundennummer", "")],
    ]
    meta_table = Table(meta_rows, colWidths=[35 * mm, 40 * mm])
    meta_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("TEXTCOLOR", (0, 0), (0, -1), INK_SOFT),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (1, -1), "LEFT"),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    top_row = Table([[Paragraph(addr_left, normal), meta_table]], colWidths=[100 * mm, 70 * mm])
    top_row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(top_row)

    story.append(Spacer(1, 10 * mm))
    title_text = INVOICE_TITLES.get(invoice.get("invoice_type") or "normal", "RECHNUNG")
    story.append(Paragraph(title_text, heading))
    story.append(Paragraph(f"{anrede(customer)},", normal))
    if invoice.get("intro_text"):
        story.append(Paragraph(invoice["intro_text"], normal))
    story.append(Spacer(1, 6 * mm))

    # Positionstabelle
    data = [["Beschreibung", "Zeitraum", "Menge", "Einheit", "Einzelpreis", "Betrag"]]
    for it in items:
        amount = float(it["qty"] or 0) * float(it["price"] or 0)
        data.append([it.get("description", ""), it.get("zeitraum", ""),
                     str(it.get("qty", "")), it.get("unit", ""),
                     eur(it.get("price", 0)), eur(amount)])
    tbl = Table(data, colWidths=[55 * mm, 30 * mm, 18 * mm, 18 * mm, 25 * mm, 24 * mm])
    tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("LINEBELOW", (0, 0), (-1, 0), 1, INK),
        ("LINEBELOW", (0, 1), (-1, -2), 0.4, RULE),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 4 * mm))

    net = invoice_net(items)
    total = invoice_total(invoice, items)
    summary_rows = []
    if not invoice.get("kleinunternehmer"):
        summary_rows.append(["Nettobetrag", eur(net)])
        rate = float(invoice.get("tax_rate") or 0)
        summary_rows.append([f"MwSt. ({rate:g}%)", eur(net * rate / 100)])
    summary_rows.append(["Gesamtsumme", eur(total)])
    summary = Table(summary_rows, colWidths=[35 * mm, 30 * mm])
    style = [
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 1, INK),
    ]
    summary.setStyle(TableStyle(style))
    wrapper = Table([["", summary]], colWidths=[130 * mm, 65 * mm])
    story.append(wrapper)

    if abschlag_info:
        story.append(Spacer(1, 6 * mm))
        rows = [["Auftragssumme (gesamt)", eur(abschlag_info.get("gesamtsumme", 0))]]
        if abschlag_info.get("billed_before"):
            rows.append(["abzüglich bereits berechneter Abschläge", "− " + eur(abschlag_info["billed_before"])])
        rows.append(["dieser " + ("Schlussrechnung" if invoice.get("invoice_type") == "schluss" else "Abschlag"),
                     eur(total)])
        rows.append(["verbleibender Auftragsrest", eur(abschlag_info.get("remaining", 0))])
        info_tbl = Table(rows, colWidths=[80 * mm, 35 * mm])
        info_tbl.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("TEXTCOLOR", (0, 0), (0, -1), INK_SOFT),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("LINEABOVE", (0, 0), (-1, 0), 0.5, RULE),
            ("LINEBELOW", (0, -1), (-1, -1), 0.5, RULE),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(Table([[info_tbl, ""]], colWidths=[120 * mm, 30 * mm]))

    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(
        f"Zahlbar innerhalb von {invoice.get('payment_terms_days', '')} Tagen ab Rechnungsstellung", normal))
    if invoice.get("kleinunternehmer"):
        story.append(Paragraph("Umsatzsteuerfreie Leistung gemäß §19 UStG", normal))

    story.append(Spacer(1, 14 * mm))
    story.append(HRFlowable(width="100%", color=RULE, thickness=0.5))
    footer_lines = []
    addr_footer = f"Adresse {company.get('addressLine1', '')} {company.get('addressLine2', '')}"
    if company.get("email"):
        addr_footer += f" • E-Mail {company['email']}"
    if company.get("phone"):
        addr_footer += f" • Tel. {company['phone']}"
    footer_lines.append(addr_footer)
    bank_footer = company.get("bankName", "")
    if company.get("bic"):
        bank_footer += f" • SWIFT/BIC {company['bic']}"
    if company.get("iban"):
        bank_footer += f" • IBAN {company['iban']}"
    footer_lines.append(bank_footer)
    footer_lines.append(f"Kontoinhaber {company.get('owner', '')}")
    for line in footer_lines:
        story.append(Paragraph(line, small))

    doc.build(story)
    return path
