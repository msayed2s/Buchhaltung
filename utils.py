import re
from datetime import datetime, date

INCOME_CATEGORIES = ["Rechnung", "Verkauf", "Dienstleistung", "Beratung", "Sonstiges"]
EXPENSE_CATEGORIES = ["Material", "Personal", "Marketing", "Software", "Bewirtungskosten",
                      "Hardware", "Reisekosten", "Sonstiges"]
UNITS = ["h", "Stk", "Tag", "pauschal", "km"]


def eur(n):
    try:
        n = float(n or 0)
    except (TypeError, ValueError):
        n = 0.0
    s = f"{n:,.2f}"
    s = s.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{s} €"


def fmt_date(iso):
    """ISO-Datum (YYYY-MM-DD, intern gespeichert) → deutsche Anzeige TT.MM.JJJJ."""
    if not iso:
        return ""
    try:
        d = datetime.strptime(iso[:10], "%Y-%m-%d")
        return d.strftime("%d.%m.%Y")
    except ValueError:
        return iso


def today_iso():
    return date.today().isoformat()


def today_de():
    """Heutiges Datum im deutschen Format TT.MM.JJJJ (für Eingabefelder)."""
    return date.today().strftime("%d.%m.%Y")


def parse_de(s):
    """Deutsches Datum (TT.MM.JJJJ, auch mit - oder / oder ISO) → ISO YYYY-MM-DD.

    Gibt "" bei leerer Eingabe und None bei ungültiger Eingabe zurück.
    """
    if not s:
        return ""
    s = str(s).strip()
    for fmt in ("%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d.%m.%y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def add_days(iso, days):
    from datetime import timedelta
    if not iso:
        return ""
    d = datetime.strptime(iso[:10], "%Y-%m-%d") + timedelta(days=int(days or 0))
    return d.strftime("%Y-%m-%d")


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(addr):
    return bool(EMAIL_RE.match((addr or "").strip()))


def anrede(customer):
    """Erzeugt die Briefanrede aus Geschlecht + Ansprechpartner.

    'herr' → 'Sehr geehrter Herr …', 'frau' → 'Sehr geehrte Frau …',
    sonst die neutrale Anrede. Ein manuell hinterlegter Text in 'salutation'
    hat Vorrang.
    """
    override = (customer.get("salutation") or "").strip()
    if override:
        return override
    gender = (customer.get("gender") or "").strip().lower()
    name = (customer.get("ansprechpartner") or "").strip()
    if gender == "herr" and name:
        return f"Sehr geehrter Herr {name}"
    if gender == "frau" and name:
        return f"Sehr geehrte Frau {name}"
    return "Sehr geehrte Damen und Herren"


def month_label(key):
    y, m = key.split("-")
    d = date(int(y), int(m), 1)
    monate = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
    return f"{monate[d.month - 1]} {str(d.year)[2:]}"
