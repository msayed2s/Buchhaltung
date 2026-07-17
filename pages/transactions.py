import os
import shutil

import ttkbootstrap as ttb
from tkinter import filedialog, messagebox
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from utils import eur, fmt_date, today_de, parse_de, today_iso, month_label, INCOME_CATEGORIES, EXPENSE_CATEGORIES
from db import app_data_dir

GREEN = "#2F6F4E"
RED = "#A63D40"
INK_SOFT = "#5B655D"
BEWIRTUNG_ABZUGSFAEHIG = 0.7

RECEIPTS_DIR = os.path.join(app_data_dir(), "receipts")
os.makedirs(RECEIPTS_DIR, exist_ok=True)


class TransactionsPage(ttb.Frame):
    def __init__(self, master, db):
        super().__init__(master, padding=18)
        self.db = db
        self.type_var = ttb.StringVar(value="income")
        self.date_var = ttb.StringVar(value=today_de())
        self.category_var = ttb.StringVar(value=INCOME_CATEGORIES[0])
        self.desc_var = ttb.StringVar()
        self.amount_var = ttb.StringVar()
        self.filter_var = ttb.StringVar(value="all")
        self.receipt_path = None
        self._build()
        self.refresh()

    def _build(self):
        form_panel = ttb.Labelframe(self, text="Neue Buchung", padding=14)
        form_panel.pack(fill="x", pady=(0, 14))

        toggle = ttb.Frame(form_panel)
        toggle.pack(fill="x", pady=(0, 10))
        self.btn_income = ttb.Button(toggle, text="Einnahme", bootstyle="success",
                                      command=lambda: self._set_type("income"))
        self.btn_income.pack(side="left", expand=True, fill="x", padx=(0, 4))
        self.btn_expense = ttb.Button(toggle, text="Ausgabe", bootstyle="secondary-outline",
                                       command=lambda: self._set_type("expense"))
        self.btn_expense.pack(side="left", expand=True, fill="x", padx=(4, 0))

        grid = ttb.Frame(form_panel)
        grid.pack(fill="x")
        grid.columnconfigure((0, 1), weight=1)

        ttb.Label(grid, text="Datum (TT.MM.JJJJ)").grid(row=0, column=0, sticky="w")
        ttb.Entry(grid, textvariable=self.date_var).grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=(0, 8))

        ttb.Label(grid, text="Kategorie").grid(row=0, column=1, sticky="w")
        self.category_combo = ttb.Combobox(grid, textvariable=self.category_var,
                                            values=INCOME_CATEGORIES, state="readonly")
        self.category_combo.grid(row=1, column=1, sticky="ew", pady=(0, 8))

        ttb.Label(grid, text="Beschreibung").grid(row=2, column=0, columnspan=2, sticky="w")
        ttb.Entry(grid, textvariable=self.desc_var).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        ttb.Label(grid, text="Betrag (€)").grid(row=4, column=0, sticky="w")
        ttb.Entry(grid, textvariable=self.amount_var).grid(row=5, column=0, sticky="ew", padx=(0, 6))

        self.hint_label = ttb.Label(form_panel, text="", foreground=RED,
                                     wraplength=560, justify="left", font=("Segoe UI", 8))
        self.hint_label.pack(fill="x", pady=(6, 0))
        self.amount_var.trace_add("write", lambda *a: self._update_hint())
        self.category_var.trace_add("write", lambda *a: self._update_hint())

        receipt_row = ttb.Frame(form_panel)
        receipt_row.pack(fill="x", pady=(10, 0))
        ttb.Button(receipt_row, text="📎 Beleg anhängen", bootstyle="secondary-outline",
                    command=self._attach_receipt).pack(side="left")
        self.receipt_label = ttb.Label(receipt_row, text="Kein Beleg angehängt", foreground=INK_SOFT)
        self.receipt_label.pack(side="left", padx=(10, 0))

        ttb.Button(form_panel, text="＋ Buchung hinzufügen", bootstyle="dark",
                    command=self._add_transaction).pack(anchor="w", pady=(12, 0))

        self.chart_panel = ttb.Labelframe(self, text="Einnahmen & Ausgaben im Verlauf", padding=10)
        self.chart_panel.pack(fill="x", pady=(0, 14))

        list_panel = ttb.Labelframe(self, text="Buchungen", padding=14)
        list_panel.pack(fill="both", expand=True)

        filter_row = ttb.Frame(list_panel)
        filter_row.pack(fill="x", pady=(0, 8))
        for key, label in [("all", "Alle"), ("income", "Einnahmen"), ("expense", "Ausgaben")]:
            ttb.Button(filter_row, text=label, bootstyle="secondary-outline",
                        command=lambda k=key: self._set_filter(k)).pack(side="left", padx=(0, 6))

        self.list_container = ttb.Frame(list_panel)
        self.list_container.pack(fill="both", expand=True)

    def _set_type(self, t):
        self.type_var.set(t)
        cats = INCOME_CATEGORIES if t == "income" else EXPENSE_CATEGORIES
        self.category_combo["values"] = cats
        self.category_var.set(cats[0])
        self.btn_income.configure(bootstyle="success" if t == "income" else "secondary-outline")
        self.btn_expense.configure(bootstyle="danger" if t == "expense" else "secondary-outline")
        self._update_hint()

    def _set_filter(self, key):
        self.filter_var.set(key)
        self.refresh()

    def _update_hint(self):
        if self.type_var.get() == "expense" and self.category_var.get() == "Bewirtungskosten":
            try:
                amount = float(self.amount_var.get().replace(",", "."))
            except ValueError:
                amount = 0
            extra = f" — von {eur(amount)} zählen {eur(amount * BEWIRTUNG_ABZUGSFAEHIG)} als Betriebsausgabe" if amount > 0 else ""
            self.hint_label.configure(
                text="Bewirtungskosten sind steuerlich nur zu 70 % abziehbar" + extra +
                     ". Trage den vollen Rechnungsbetrag ein; die App rechnet die 30 % im Steuern-Tab "
                     "automatisch heraus. Bewirtungsbeleg mit Anlass und Teilnehmern aufbewahren.")
        else:
            self.hint_label.configure(text="")

    def _attach_receipt(self):
        path = filedialog.askopenfilename(
            title="Beleg auswählen",
            filetypes=[("Bilder/PDF", "*.png *.jpg *.jpeg *.pdf"), ("Alle Dateien", "*.*")])
        if path:
            self.receipt_path = path
            self.receipt_label.configure(text=os.path.basename(path), foreground="#000")

    def _add_transaction(self):
        try:
            amount = float(self.amount_var.get().replace(",", "."))
        except ValueError:
            messagebox.showerror("Ungültiger Betrag", "Bitte einen gültigen Betrag eingeben.")
            return
        if amount <= 0:
            messagebox.showerror("Ungültiger Betrag", "Der Betrag muss größer als 0 sein.")
            return

        iso_date = parse_de(self.date_var.get())
        if iso_date is None:
            messagebox.showerror("Ungültiges Datum", "Bitte ein gültiges Datum im Format TT.MM.JJJJ eingeben.")
            return
        if not iso_date:
            iso_date = today_iso()

        stored_receipt = None
        if self.receipt_path:
            ext = os.path.splitext(self.receipt_path)[1]
            dest = os.path.join(RECEIPTS_DIR, f"{self.db.__class__ and __import__('uuid').uuid4().hex}{ext}")
            try:
                shutil.copy2(self.receipt_path, dest)
                stored_receipt = dest
            except OSError:
                pass

        self.db.add_transaction({
            "type": self.type_var.get(),
            "date": iso_date,
            "category": self.category_var.get(),
            "description": self.desc_var.get(),
            "amount": amount,
            "receipt_path": stored_receipt,
        })
        self.desc_var.set("")
        self.amount_var.set("")
        self.receipt_path = None
        self.receipt_label.configure(text="Kein Beleg angehängt", foreground=INK_SOFT)
        self.refresh()

    def _draw_chart(self, transactions):
        for w in self.chart_panel.winfo_children():
            w.destroy()
        monthly = {}
        for t in transactions:
            key = (t["date"] or "")[:7]
            if not key:
                continue
            monthly.setdefault(key, {"Einnahmen": 0, "Ausgaben": 0})
            monthly[key]["Einnahmen" if t["type"] == "income" else "Ausgaben"] += t["amount"]
        keys = sorted(monthly.keys())[-12:]
        if not keys:
            ttb.Label(self.chart_panel, text="Noch keine Buchungen — das Diagramm erscheint nach der ersten Buchung.",
                       foreground=INK_SOFT, font=("Segoe UI", 9, "italic")).pack(anchor="w")
            return
        fig = Figure(figsize=(6.6, 2.6), dpi=100)
        ax = fig.add_subplot(111)
        x = range(len(keys))
        width = 0.35
        ax.bar([i - width / 2 for i in x], [monthly[k]["Einnahmen"] for k in keys], width,
               label="Einnahmen", color=GREEN)
        ax.bar([i + width / 2 for i in x], [monthly[k]["Ausgaben"] for k in keys], width,
               label="Ausgaben", color=RED)
        ax.set_xticks(list(x))
        ax.set_xticklabels([month_label(k) for k in keys], fontsize=8)
        ax.tick_params(axis="y", labelsize=8)
        ax.legend(fontsize=8, frameon=False)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=self.chart_panel)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def refresh(self):
        all_transactions = self.db.list_transactions()
        self._draw_chart(all_transactions)

        for w in self.list_container.winfo_children():
            w.destroy()
        transactions = list(all_transactions)
        f = self.filter_var.get()
        if f != "all":
            transactions = [t for t in transactions if t["type"] == f]
        transactions.sort(key=lambda t: t["date"] or "", reverse=True)

        if not transactions:
            ttb.Label(self.list_container, text="Keine Buchungen in dieser Ansicht.",
                       foreground=INK_SOFT, font=("Segoe UI", 9, "italic")).pack(anchor="w")
            return

        for t in transactions:
            row = ttb.Frame(self.list_container)
            row.pack(fill="x", pady=3)
            ttb.Label(row, text=fmt_date(t["date"]), width=11,
                       foreground=INK_SOFT, font=("Consolas", 9)).pack(side="left")
            desc_frame = ttb.Frame(row)
            desc_frame.pack(side="left", fill="x", expand=True, padx=(6, 0))
            ttb.Label(desc_frame, text=t["description"] or t["category"]).pack(anchor="w")
            sub = t["category"]
            if t["type"] == "expense" and t["category"] == "Bewirtungskosten":
                sub += f" · davon 70 % abziehbar ({eur(t['amount'] * BEWIRTUNG_ABZUGSFAEHIG)})"
            ttb.Label(desc_frame, text=sub, foreground=INK_SOFT, font=("Consolas", 8)).pack(anchor="w")
            color = GREEN if t["type"] == "income" else RED
            sign = "+" if t["type"] == "income" else "−"
            ttb.Label(row, text=f"{sign} {eur(t['amount'])}", foreground=color,
                       font=("Consolas", 9, "bold")).pack(side="right", padx=(6, 0))
            if t["receipt_path"]:
                ttb.Button(row, text="📎", bootstyle="link",
                            command=lambda p=t["receipt_path"]: self._open_receipt(p)).pack(side="right")
            ttb.Button(row, text="🗑", bootstyle="link",
                        command=lambda tid=t["id"]: self._delete(tid)).pack(side="right")

    def _open_receipt(self, path):
        if os.path.exists(path):
            os.startfile(path) if os.name == "nt" else os.system(f'xdg-open "{path}"')

    def _delete(self, tid):
        if messagebox.askyesno("Löschen", "Diese Buchung wirklich löschen?"):
            self.db.delete_transaction(tid)
            self.refresh()
