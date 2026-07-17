"""
Buchhaltung Desktop — modernes, eigenständiges Buchhaltungs- und Rechnungstool
für Kleinunternehmer und Nebengewerbe (Windows-Desktop-App).

Start: python main.py
Build:  siehe build_exe.bat
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ttkbootstrap as ttb
from ttkbootstrap.constants import *
from ttkbootstrap.scrolled import ScrolledFrame

from db import Database
from utils import eur
from pages.dashboard import DashboardPage
from pages.transactions import TransactionsPage
from pages.customers import CustomersPage
from pages.invoices import InvoicesPage
from pages.trips import TripsPage
from pages.reports import ReportsPage
from pages.taxpage import TaxPage
from pages.settings_page import SettingsPage
from pages.backup_page import BackupPage

INK = "#1F2A24"
INK_SOFT = "#5B655D"
GOLD = "#A9812F"
PAPER = "#EEF0EA"

NAV_ITEMS = [
    ("dashboard", "🏠  Übersicht"),
    ("transactions", "🧾  Buchungen"),
    ("customers", "👥  Kunden"),
    ("invoices", "📄  Rechnungen"),
    ("trips", "🚗  Fahrtkosten"),
    ("reports", "📊  Berichte"),
    ("tax", "🧮  Steuern"),
    ("settings", "⚙️  Einstellungen"),
    ("backup", "💾  Datensicherung"),
]


class App(ttb.Window):
    def __init__(self):
        super().__init__(title="Buchhaltung", themename="flatly", size=(1180, 760))
        self.minsize(980, 640)
        try:
            self.state("zoomed")
        except Exception:
            pass

        self.db = Database()

        try:
            import template_letter
            template_letter.ensure_external_files()
        except Exception:
            pass

        self._build_header()
        self._build_body()
        self.show_page("dashboard")

    # ---------- layout ----------
    def _build_header(self):
        header = ttb.Frame(self, padding=(20, 14))
        header.pack(fill="x")
        left = ttb.Frame(header)
        left.pack(side="left")
        ttb.Label(left, text="BUCHHALTUNG · KLEINUNTERNEHMEN", font=("Segoe UI", 8, "bold"),
                   foreground=INK_SOFT).pack(anchor="w")
        ttb.Label(left, text=self.db.get_company().get("name", "Meine Firma"),
                   font=("Georgia", 18, "bold"), foreground=INK).pack(anchor="w")

        self.balance_label = ttb.Label(header, text="", font=("Consolas", 13, "bold"), foreground=INK)
        self.balance_label.pack(side="right")
        ttb.Label(header, text="SALDO", font=("Segoe UI", 8, "bold"), foreground=INK_SOFT).pack(
            side="right", padx=(0, 8))
        ttb.Separator(self).pack(fill="x")

    def _build_body(self):
        body = ttb.Frame(self)
        body.pack(fill="both", expand=True)

        sidebar = ttb.Frame(body, padding=(10, 16), bootstyle="light")
        sidebar.pack(side="left", fill="y")

        self.nav_buttons = {}
        for key, label in NAV_ITEMS:
            btn = ttb.Button(sidebar, text=label, bootstyle="light",
                              command=lambda k=key: self.show_page(k), width=20)
            btn.pack(fill="x", pady=2)
            self.nav_buttons[key] = btn

        ttb.Separator(body, orient="vertical").pack(side="left", fill="y")

        self.content = ttb.Frame(body)
        self.content.pack(side="left", fill="both", expand=True)

        self.pages = {}

    # ---------- navigation ----------
    def show_page(self, key):
        for w in self.content.winfo_children():
            w.destroy()

        for k, btn in self.nav_buttons.items():
            btn.configure(bootstyle="dark" if k == key else "light")

        scroll = ScrolledFrame(self.content, autohide=True)
        scroll.pack(fill="both", expand=True)

        page_classes = {
            "dashboard": DashboardPage,
            "transactions": TransactionsPage,
            "customers": CustomersPage,
            "invoices": InvoicesPage,
            "trips": TripsPage,
            "reports": ReportsPage,
            "tax": TaxPage,
            "settings": SettingsPage,
        }
        if key == "backup":
            page = BackupPage(scroll, self.db, on_restore=lambda: self.show_page("dashboard"))
        else:
            page = page_classes[key](scroll, self.db)
        page.pack(fill="both", expand=True)
        self._update_balance()

    def _update_balance(self):
        transactions = self.db.list_transactions()
        income = sum(t["amount"] for t in transactions if t["type"] == "income")
        expense = sum(t["amount"] for t in transactions if t["type"] == "expense")
        self.balance_label.configure(text=eur(income - expense))


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
