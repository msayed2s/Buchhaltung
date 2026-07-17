"""
Steuerberechnungen — portiert aus dem Original (buchhaltung_2.jsx).
Tarif 2026 (§32a EStG, Steuerfortentwicklungsgesetz), Entfernungspauschale 2026,
Bewirtungskosten (§4 Abs. 5 Nr. 2 EStG), Steuerermäßigung §35a EStG,
Günstigerprüfung Kindergeld/Kinderfreibetrag.
"""
import math

TAX_TARIFF_2026 = {
    "year": 2026,
    "grundfreibetrag": 12348,
    "zone2End": 17799,
    "zone3End": 69878,
    "zone4End": 277825,
    "zones": [
        ("bis 12.348 € (Grundfreibetrag)", "0 %"),
        ("12.349 – 17.799 €", "14 % → 24 % (progressiv)"),
        ("17.800 – 69.878 €", "24 % → 42 % (progressiv)"),
        ("69.879 – 277.825 €", "42 % (Spitzensteuersatz)"),
        ("ab 277.826 €", "45 % (Reichensteuer)"),
    ],
}

KINDERFREIBETRAG_PRO_KIND = 9756
KINDERGELD_PRO_KIND_JAHR = 3108

ENTFERNUNGSPAUSCHALE = 0.38
ARBEITNEHMER_PAUSCHBETRAG = 1230
HOMEOFFICE_PRO_TAG = 6
HOMEOFFICE_MAX_TAGE = 210

BEWIRTUNG_ABZUGSFAEHIG = 0.7

P35A_TYPES = {
    "handwerker": {"label": "Handwerkerleistung (Renovierung, Wartung, Modernisierung)", "cap": 1200},
    "haushalt": {"label": "Haushaltsnahe Dienstleistung (Reinigung, Garten, Winterdienst …)", "cap": 4000},
    "minijob": {"label": "Haushaltsnaher Minijob (Haushaltshilfe)", "cap": 510},
}


def income_tax_base(zve):
    x = math.floor(max(0, zve))
    t = TAX_TARIFF_2026
    if x <= t["grundfreibetrag"]:
        return 0
    if x <= t["zone2End"]:
        y = (x - t["grundfreibetrag"]) / 10000
        return math.floor((914.51 * y + 1400) * y)
    if x <= t["zone3End"]:
        z = (x - t["zone2End"]) / 10000
        return math.floor((173.1 * z + 2397) * z + 1034.87)
    if x <= t["zone4End"]:
        return math.floor(0.42 * x - 11135.63)
    return math.floor(0.45 * x - 19470.38)


def income_tax(zve, splitting):
    if splitting:
        return 2 * income_tax_base(zve / 2)
    return income_tax_base(zve)


def pendlerpauschale(days, km):
    return max(0, float(days or 0)) * max(0, float(km or 0)) * ENTFERNUNGSPAUSCHALE


def homeoffice_pauschale(days):
    return min(HOMEOFFICE_MAX_TAGE, max(0, float(days or 0))) * HOMEOFFICE_PRO_TAG


def werbungskosten(days, km, ho_days, sonstige):
    summe = pendlerpauschale(days, km) + homeoffice_pauschale(ho_days) + max(0, float(sonstige or 0))
    return max(ARBEITNEHMER_PAUSCHBETRAG, summe)


def bewirtung_nicht_abziehbar(transactions):
    total = 0.0
    for t in transactions:
        if t.get("type") == "expense" and t.get("category") == "Bewirtungskosten":
            total += (float(t.get("amount") or 0)) * (1 - BEWIRTUNG_ABZUGSFAEHIG)
    return total


def p35a_bonus(handwerker, haushalt, minijob):
    bonus = 0.0
    bonus += min(P35A_TYPES["handwerker"]["cap"], 0.2 * float(handwerker or 0))
    bonus += min(P35A_TYPES["haushalt"]["cap"], 0.2 * float(haushalt or 0))
    bonus += min(P35A_TYPES["minijob"]["cap"], 0.2 * float(minijob or 0))
    return bonus


def effective_tax(zve, splitting, children):
    kids = max(0, int(children or 0))
    with_kindergeld = income_tax(zve, splitting)
    if kids == 0:
        return {"tax": with_kindergeld, "freibetrag_applied": False}
    with_freibetrag = income_tax(max(0, zve - kids * KINDERFREIBETRAG_PRO_KIND), splitting) + kids * KINDERGELD_PRO_KIND_JAHR
    if with_freibetrag < with_kindergeld:
        return {"tax": with_freibetrag, "freibetrag_applied": True}
    return {"tax": with_kindergeld, "freibetrag_applied": False}
