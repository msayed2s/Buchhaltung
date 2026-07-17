"""
Datenbankschicht (SQLite) für die Buchhaltungs-App.
Alle Daten liegen in einer einzigen Datei im Benutzerverzeichnis, sodass die
App als portable .exe ohne Server funktioniert.
"""
import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime


def app_data_dir():
    """Plattformunabhängiges Verzeichnis für die Datenbankdatei."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.path.expanduser("~/.local/share")
    path = os.path.join(base, "Buchhaltung")
    os.makedirs(path, exist_ok=True)
    return path


DB_PATH = os.path.join(app_data_dir(), "buchhaltung.db")


def uid():
    return uuid.uuid4().hex[:12]


def now_iso():
    return datetime.now().strftime("%Y-%m-%d")


SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,            -- income | expense
    date TEXT NOT NULL,
    category TEXT,
    description TEXT,
    amount REAL NOT NULL,
    receipt_path TEXT
);

CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY,
    kundennummer TEXT,
    firma TEXT,
    ansprechpartner TEXT,
    salutation TEXT,
    gender TEXT,                    -- herr | frau | ''
    ust_id TEXT,                    -- USt-IdNr des Kunden
    address_line1 TEXT,
    address_line2 TEXT,
    email TEXT,
    phone TEXT
);

CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    number TEXT,
    customer_id TEXT,
    date TEXT,
    due_date TEXT,
    payment_terms_days INTEGER,
    intro_text TEXT,
    tax_rate REAL,
    kleinunternehmer INTEGER,
    status TEXT DEFAULT 'open',     -- open | paid
    betreff TEXT,                   -- Betreff für Vorlage/Anschreiben
    body_text TEXT,                 -- freier Text des Schreibens (Vorlage)
    invoice_type TEXT DEFAULT 'normal',  -- normal | abschlag | schluss
    parent_id TEXT,                 -- Verweis auf Hauptauftrag (Abschlagsrechnung)
    gesamtsumme REAL                -- Auftragssumme (Hauptsumme) bei Abschlagsrechnung
);

CREATE TABLE IF NOT EXISTS invoice_items (
    id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    description TEXT,
    zeitraum TEXT,
    qty REAL,
    unit TEXT,
    price REAL,
    FOREIGN KEY(invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS trips (
    id TEXT PRIMARY KEY,
    date TEXT,
    purpose TEXT,
    origin TEXT,
    destination TEXT,
    km REAL,
    rate REAL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

DEFAULT_COMPANY = {
    "name": "Meine Firma",
    "owner": "",
    "ustId": "",
    "addressLine1": "",
    "addressLine2": "",
    "email": "",
    "phone": "",
    "bankName": "",
    "bic": "",
    "iban": "",
    "paymentTermsDays": 14,
    "kleinunternehmer": True,
    "logo": "",  # Dateipfad zum Logo
}

DEFAULT_SMTP = {
    "host": "",
    "port": 587,
    "user": "",
    "password": "",
    "from_addr": "",
    "use_tls": True,
    "subject": "Ihre Rechnung {number}",
    "body": "Guten Tag,\n\nanbei erhalten Sie die Rechnung {number} vom {date}.\n\nMit freundlichen Grüßen",
}

DEFAULT_TAX_SETTINGS = {
    "splitting": False,
    "children": 0,
    "salarySelf": 0,
    "salaryPartner": 0,
    "commuteDaysSelf": 0,
    "commuteKmSelf": 0,
    "homeofficeDaysSelf": 0,
    "otherWkSelf": 110,
    "commuteDaysPartner": 0,
    "commuteKmPartner": 0,
    "homeofficeDaysPartner": 0,
    "otherWkPartner": 110,
    "handwerkerKosten": 0,
    "haushaltKosten": 0,
    "minijobKosten": 0,
    "nebenHours": 0,
}


class Database:
    def __init__(self, path=DB_PATH):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()
        self._migrate()
        self._ensure_defaults()

    def _migrate(self):
        """Fügt neue Spalten zu bereits bestehenden Datenbanken hinzu."""
        needed = {
            "customers": [("gender", "TEXT"), ("ust_id", "TEXT")],
            "invoices": [("betreff", "TEXT"), ("body_text", "TEXT"),
                         ("invoice_type", "TEXT DEFAULT 'normal'"),
                         ("parent_id", "TEXT"), ("gesamtsumme", "REAL")],
        }
        for table, cols in needed.items():
            existing = {r["name"] for r in self.conn.execute(f"PRAGMA table_info({table})")}
            for name, decl in cols:
                if name not in existing:
                    self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")
        self.conn.commit()

    # ---------- settings (key/value JSON) ----------
    def _ensure_defaults(self):
        if self.get_setting("company") is None:
            self.set_setting("company", DEFAULT_COMPANY)
        if self.get_setting("tax_settings") is None:
            self.set_setting("tax_settings", DEFAULT_TAX_SETTINGS)
        if self.get_setting("smtp") is None:
            self.set_setting("smtp", DEFAULT_SMTP)

    def get_smtp(self):
        s = dict(DEFAULT_SMTP)
        s.update(self.get_setting("smtp") or {})
        return s

    def save_smtp(self, smtp):
        self.set_setting("smtp", smtp)

    def get_setting(self, key):
        row = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        if row is None:
            return None
        return json.loads(row["value"])

    def set_setting(self, key, value):
        self.conn.execute(
            "INSERT INTO settings(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(value)),
        )
        self.conn.commit()

    def get_company(self):
        c = dict(DEFAULT_COMPANY)
        c.update(self.get_setting("company") or {})
        return c

    def save_company(self, company):
        self.set_setting("company", company)

    def get_tax_settings(self):
        t = dict(DEFAULT_TAX_SETTINGS)
        t.update(self.get_setting("tax_settings") or {})
        return t

    def save_tax_settings(self, ts):
        self.set_setting("tax_settings", ts)

    # ---------- transactions ----------
    def list_transactions(self):
        rows = self.conn.execute("SELECT * FROM transactions ORDER BY date DESC").fetchall()
        return [dict(r) for r in rows]

    def add_transaction(self, t):
        t = dict(t)
        t.setdefault("id", uid())
        self.conn.execute(
            "INSERT INTO transactions (id, type, date, category, description, amount, receipt_path) "
            "VALUES (:id, :type, :date, :category, :description, :amount, :receipt_path)",
            {**{"receipt_path": None}, **t},
        )
        self.conn.commit()
        return t["id"]

    def delete_transaction(self, tid):
        self.conn.execute("DELETE FROM transactions WHERE id=?", (tid,))
        self.conn.commit()

    # ---------- customers ----------
    def list_customers(self):
        rows = self.conn.execute("SELECT * FROM customers ORDER BY firma").fetchall()
        return [dict(r) for r in rows]

    def get_customer(self, cid):
        row = self.conn.execute("SELECT * FROM customers WHERE id=?", (cid,)).fetchone()
        return dict(row) if row else None

    def save_customer(self, c):
        c = dict(c)
        c.setdefault("id", uid())
        cols = ["id", "kundennummer", "firma", "ansprechpartner", "salutation",
                "gender", "ust_id", "address_line1", "address_line2", "email", "phone"]
        for col in cols:
            c.setdefault(col, "")
        placeholders = ", ".join(f":{col}" for col in cols)
        updates = ", ".join(f"{col}=excluded.{col}" for col in cols if col != "id")
        self.conn.execute(
            f"INSERT INTO customers ({', '.join(cols)}) VALUES ({placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET {updates}",
            c,
        )
        self.conn.commit()
        return c["id"]

    def delete_customer(self, cid):
        self.conn.execute("DELETE FROM customers WHERE id=?", (cid,))
        self.conn.commit()

    # ---------- invoices ----------
    def list_invoices(self):
        rows = self.conn.execute("SELECT * FROM invoices ORDER BY date DESC").fetchall()
        invoices = []
        for r in rows:
            inv = dict(r)
            items = self.conn.execute(
                "SELECT * FROM invoice_items WHERE invoice_id=?", (inv["id"],)
            ).fetchall()
            inv["items"] = [dict(i) for i in items]
            invoices.append(inv)
        return invoices

    def next_invoice_number(self):
        year = datetime.now().year
        count = self.conn.execute(
            "SELECT COUNT(*) c FROM invoices WHERE number LIKE ?", (f"{year}-%",)
        ).fetchone()["c"]
        return f"{year}-{count + 1:03d}"

    def save_invoice(self, inv, items):
        inv = dict(inv)
        inv.setdefault("id", uid())
        cols = ["id", "number", "customer_id", "date", "due_date", "payment_terms_days",
                "intro_text", "tax_rate", "kleinunternehmer", "status",
                "betreff", "body_text", "invoice_type", "parent_id", "gesamtsumme"]
        for col in cols:
            inv.setdefault(col, "")
        placeholders = ", ".join(f":{col}" for col in cols)
        updates = ", ".join(f"{col}=excluded.{col}" for col in cols if col != "id")
        self.conn.execute(
            f"INSERT INTO invoices ({', '.join(cols)}) VALUES ({placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET {updates}",
            inv,
        )
        self.conn.execute("DELETE FROM invoice_items WHERE invoice_id=?", (inv["id"],))
        for it in items:
            it = dict(it)
            it.setdefault("id", uid())
            it["invoice_id"] = inv["id"]
            self.conn.execute(
                "INSERT INTO invoice_items (id, invoice_id, description, zeitraum, qty, unit, price) "
                "VALUES (:id, :invoice_id, :description, :zeitraum, :qty, :unit, :price)",
                it,
            )
        self.conn.commit()
        return inv["id"]

    def set_invoice_status(self, iid, status):
        self.conn.execute("UPDATE invoices SET status=? WHERE id=?", (status, iid))
        self.conn.commit()

    def delete_invoice(self, iid):
        self.conn.execute("DELETE FROM invoices WHERE id=?", (iid,))
        self.conn.execute("DELETE FROM invoice_items WHERE invoice_id=?", (iid,))
        self.conn.commit()

    # ---------- trips ----------
    def list_trips(self):
        rows = self.conn.execute("SELECT * FROM trips ORDER BY date DESC").fetchall()
        return [dict(r) for r in rows]

    def add_trip(self, t):
        t = dict(t)
        t.setdefault("id", uid())
        self.conn.execute(
            "INSERT INTO trips (id, date, purpose, origin, destination, km, rate) "
            "VALUES (:id, :date, :purpose, :origin, :destination, :km, :rate)",
            t,
        )
        self.conn.commit()
        return t["id"]

    def delete_trip(self, tid):
        self.conn.execute("DELETE FROM trips WHERE id=?", (tid,))
        self.conn.commit()

    # ---------- backup ----------
    def export_all(self):
        return {
            "format": "buchhaltung-desktop",
            "version": 1,
            "exported_at": datetime.now().isoformat(),
            "company": self.get_company(),
            "tax_settings": self.get_tax_settings(),
            "transactions": self.list_transactions(),
            "customers": self.list_customers(),
            "invoices": self.list_invoices(),
            "trips": self.list_trips(),
        }

    def restore_all(self, backup):
        self.conn.execute("DELETE FROM transactions")
        self.conn.execute("DELETE FROM customers")
        self.conn.execute("DELETE FROM invoices")
        self.conn.execute("DELETE FROM invoice_items")
        self.conn.execute("DELETE FROM trips")
        self.conn.commit()
        for t in backup.get("transactions", []):
            self.add_transaction(t)
        for c in backup.get("customers", []):
            self.save_customer(c)
        for inv in backup.get("invoices", []):
            items = inv.pop("items", [])
            self.save_invoice(inv, items)
        for t in backup.get("trips", []):
            self.add_trip(t)
        if backup.get("company"):
            self.save_company(backup["company"])
        if backup.get("tax_settings"):
            self.save_tax_settings(backup["tax_settings"])
