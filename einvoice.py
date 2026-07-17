"""
E-Rechnung: Factur-X / ZUGFeRD 2.x (Profil BASIC, EN 16931) — XML-Erzeugung und
Einbettung in ein PDF (ZUGFeRD-Ausgabe).

- ``build_cii_xml``  erzeugt die CII-XML (CrossIndustryInvoice).
- ``export_xml``     schreibt die reine XML-Datei.
- ``export_zugferd`` erzeugt das Rechnungs-PDF und bettet die XML als
                     ``factur-x.xml`` ein (hybride ZUGFeRD-Datei).
"""
import os
from datetime import datetime
from xml.sax.saxutils import escape

from pdf_invoice import generate_invoice_pdf, invoice_net, invoice_total

RSM = "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
RAM = "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
UDT = "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"

GUIDELINE_BASIC = "urn:cen.eu:en16931:2017#compliant#urn:factur-x.eu:1p0:basic"


def _num(v):
    return f"{float(v or 0):.2f}"


def _iso_compact(iso):
    try:
        return datetime.strptime((iso or "")[:10], "%Y-%m-%d").strftime("%Y%m%d")
    except ValueError:
        return datetime.now().strftime("%Y%m%d")


def build_cii_xml(invoice, items, company, customer):
    net = invoice_net(items)
    kleinunternehmer = bool(invoice.get("kleinunternehmer"))
    rate = 0.0 if kleinunternehmer else float(invoice.get("tax_rate") or 0)
    tax_amount = 0.0 if kleinunternehmer else round(net * rate / 100, 2)
    grand = round(net + tax_amount, 2)

    if kleinunternehmer:
        tax_category = "E"  # steuerbefreit
        exemption = "Steuerbefreiung gemäß § 19 UStG (Kleinunternehmer)"
    else:
        tax_category = "S"  # Regelsteuersatz
        exemption = ""

    def e(x):
        return escape(str(x or ""))

    lines = []
    for idx, it in enumerate(items, start=1):
        qty = float(it.get("qty") or 0)
        price = float(it.get("price") or 0)
        line_total = round(qty * price, 2)
        lines.append(f"""    <ram:IncludedSupplyChainTradeLineItem>
      <ram:AssociatedDocumentLineDocument>
        <ram:LineID>{idx}</ram:LineID>
      </ram:AssociatedDocumentLineDocument>
      <ram:SpecifiedTradeProduct>
        <ram:Name>{e(it.get('description', ''))}</ram:Name>
      </ram:SpecifiedTradeProduct>
      <ram:SpecifiedLineTradeAgreement>
        <ram:NetPriceProductTradePrice>
          <ram:ChargeAmount>{_num(price)}</ram:ChargeAmount>
        </ram:NetPriceProductTradePrice>
      </ram:SpecifiedLineTradeAgreement>
      <ram:SpecifiedLineTradeDelivery>
        <ram:BilledQuantity unitCode="{e(_unit_code(it.get('unit')))}">{qty:.2f}</ram:BilledQuantity>
      </ram:SpecifiedLineTradeDelivery>
      <ram:SpecifiedLineTradeSettlement>
        <ram:ApplicableTradeTax>
          <ram:TypeCode>VAT</ram:TypeCode>
          <ram:CategoryCode>{tax_category}</ram:CategoryCode>
          <ram:RateApplicablePercent>{_num(rate)}</ram:RateApplicablePercent>
        </ram:ApplicableTradeTax>
        <ram:SpecifiedTradeSettlementLineMonetarySummation>
          <ram:LineTotalAmount>{_num(line_total)}</ram:LineTotalAmount>
        </ram:SpecifiedTradeSettlementLineMonetarySummation>
      </ram:SpecifiedLineTradeSettlement>
    </ram:IncludedSupplyChainTradeLineItem>""")

    tax_block = f"""        <ram:ApplicableTradeTax>
          <ram:CalculatedAmount>{_num(tax_amount)}</ram:CalculatedAmount>
          <ram:TypeCode>VAT</ram:TypeCode>
          {f'<ram:ExemptionReason>{e(exemption)}</ram:ExemptionReason>' if exemption else ''}
          <ram:BasisAmount>{_num(net)}</ram:BasisAmount>
          <ram:CategoryCode>{tax_category}</ram:CategoryCode>
          <ram:RateApplicablePercent>{_num(rate)}</ram:RateApplicablePercent>
        </ram:ApplicableTradeTax>"""

    seller_addr_line = e(company.get("addressLine1", ""))
    seller_city = e(company.get("addressLine2", ""))
    buyer_name = e(customer.get("firma") or customer.get("ansprechpartner") or "")

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice xmlns:rsm="{RSM}" xmlns:ram="{RAM}" xmlns:udt="{UDT}">
  <rsm:ExchangedDocumentContext>
    <ram:GuidelineSpecifiedDocumentContextParameter>
      <ram:ID>{GUIDELINE_BASIC}</ram:ID>
    </ram:GuidelineSpecifiedDocumentContextParameter>
  </rsm:ExchangedDocumentContext>
  <rsm:ExchangedDocument>
    <ram:ID>{e(invoice.get('number', ''))}</ram:ID>
    <ram:TypeCode>380</ram:TypeCode>
    <ram:IssueDateTime>
      <udt:DateTimeString format="102">{_iso_compact(invoice.get('date'))}</udt:DateTimeString>
    </ram:IssueDateTime>
  </rsm:ExchangedDocument>
  <rsm:SupplyChainTradeTransaction>
{chr(10).join(lines)}
    <ram:ApplicableHeaderTradeAgreement>
      <ram:SellerTradeParty>
        <ram:Name>{e(company.get('name', ''))}</ram:Name>
        <ram:PostalTradeAddress>
          <ram:LineOne>{seller_addr_line}</ram:LineOne>
          <ram:CityName>{seller_city}</ram:CityName>
          <ram:CountryID>DE</ram:CountryID>
        </ram:PostalTradeAddress>
        {f'<ram:SpecifiedTaxRegistration><ram:ID schemeID="VA">{e(company.get("ustId",""))}</ram:ID></ram:SpecifiedTaxRegistration>' if company.get('ustId') else ''}
      </ram:SellerTradeParty>
      <ram:BuyerTradeParty>
        <ram:Name>{buyer_name}</ram:Name>
        <ram:PostalTradeAddress>
          <ram:LineOne>{e(customer.get('address_line1', ''))}</ram:LineOne>
          <ram:CityName>{e(customer.get('address_line2', ''))}</ram:CityName>
          <ram:CountryID>DE</ram:CountryID>
        </ram:PostalTradeAddress>
        {f'<ram:SpecifiedTaxRegistration><ram:ID schemeID="VA">{e(customer.get("ust_id",""))}</ram:ID></ram:SpecifiedTaxRegistration>' if customer.get('ust_id') else ''}
      </ram:BuyerTradeParty>
    </ram:ApplicableHeaderTradeAgreement>
    <ram:ApplicableHeaderTradeDelivery/>
    <ram:ApplicableHeaderTradeSettlement>
      <ram:InvoiceCurrencyCode>EUR</ram:InvoiceCurrencyCode>
{tax_block}
      <ram:SpecifiedTradeSettlementHeaderMonetarySummation>
        <ram:LineTotalAmount>{_num(net)}</ram:LineTotalAmount>
        <ram:TaxBasisTotalAmount>{_num(net)}</ram:TaxBasisTotalAmount>
        <ram:TaxTotalAmount currencyID="EUR">{_num(tax_amount)}</ram:TaxTotalAmount>
        <ram:GrandTotalAmount>{_num(grand)}</ram:GrandTotalAmount>
        <ram:DuePayableAmount>{_num(grand)}</ram:DuePayableAmount>
      </ram:SpecifiedTradeSettlementHeaderMonetarySummation>
    </ram:ApplicableHeaderTradeSettlement>
  </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>
"""
    return xml


def _unit_code(unit):
    # Mapping auf UN/ECE-Einheitencodes
    return {
        "h": "HUR", "Stk": "C62", "Tag": "DAY", "pauschal": "C62", "km": "KMT",
    }.get(unit, "C62")


def export_xml(path, invoice, items, company, customer):
    xml = build_cii_xml(invoice, items, company, customer)
    with open(path, "w", encoding="utf-8") as f:
        f.write(xml)
    return path


def export_zugferd(pdf_path, invoice, items, company, customer):
    """Erzeugt das Rechnungs-PDF und bettet die Factur-X-XML ein."""
    import pikepdf

    generate_invoice_pdf(pdf_path, invoice, items, company, customer)
    xml = build_cii_xml(invoice, items, company, customer).encode("utf-8")

    pdf = pikepdf.open(pdf_path, allow_overwriting_input=True)
    filespec = pikepdf.AttachedFileSpec(pdf, xml, mime_type="application/xml",
                                        description="Factur-X/ZUGFeRD Rechnungsdaten")
    pdf.attachments["factur-x.xml"] = filespec
    # AFRelationship = Alternative (Kernanforderung ZUGFeRD/Factur-X)
    try:
        ef = pdf.attachments["factur-x.xml"].obj
        ef.AFRelationship = pikepdf.Name("/Alternative")
        af = pdf.make_indirect(pikepdf.Array([ef]))
        pdf.Root.AF = af
    except Exception:
        pass
    pdf.save(pdf_path)
    pdf.close()
    return pdf_path
