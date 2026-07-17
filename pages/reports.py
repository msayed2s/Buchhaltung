from datetime import date

import ttkbootstrap as ttb
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from utils import eur, fmt_date, month_label
from tax import bewirtung_nicht_abziehbar
from pdf_invoice import invoice_total

INK = "#1F2A24"
INK_SOFT = "#5B655D"
GREEN = "#2F6F4E"
RED = "#A63D40"


class ReportsPage(ttb.Frame):
    def __init__(self, master, db):
        super().__init__(master, padding=18)
        self.db = db
        self.year_var = ttb.StringVar(value=str(date.today().year))
        self._build()
        self.refresh()

    def _build(self):
        header = ttb.Frame(self)
        header.pack(fill="x", pady=(0, 10))
        ttb.Label(header, text="Jahr").pack(side="left")
        self.year_combo = ttb.Combobox(header, textvariable=self.year_var, width=8, state="readonly")
        self.year_combo.pack(side="left", padx=6)
        self.year_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        self.bwa_panel = ttb.Labelframe(self, text="Betriebswirtschaftliche Auswertung (BWA)", padding=14)
        self.bwa_panel.pack(fill="x", pady=(0, 14))

        self.chart_panel = ttb.Labelframe(self, text="Monatsverlauf", padding=10)
        self.chart_panel.pack(fill="x", pady=(0, 14))

        self.open_panel = ttb.Labelframe(self, text="Offene Posten (Forderungen)", padding=14)
        self.open_panel.pack(fill="both", expand=True)

    def _row(self, parent, label, value, bold=False, color=INK):
        row = ttb.Frame(parent)
        row.pack(fill="x", pady=1)
        font = ("Segoe UI", 9, "bold") if bold else ("Segoe UI", 9)
        ttb.Label(row, text=label, font=font).pack(side="left")
        ttb.Label(row, text=value, font=("Consolas", 9, "bold" if bold else "normal"),
                   foreground=color).pack(side="right")

    def refresh(self):
        transactions = self.db.list_transactions()
        trips = self.db.list_trips()
        invoices = self.db.list_invoices()
        customers = {c["id"]: c for c in self.db.list_customers()}

        years = sorted({(t["date"] or "")[:4] for t in transactions} |
                       {(t["date"] or "")[:4] for t in trips} |
                       {(i["date"] or "")[:4] for i in invoices}, reverse=True)
        current_year = str(date.today().year)
        if current_year not in years:
            years.insert(0, current_year)
        years = [y for y in years if y]
        self.year_combo["values"] = years
        if self.year_var.get() not in years:
            self.year_var.set(current_year)
        year = self.year_var.get()

        year_tx = [t for t in transactions if (t["date"] or "").startswith(year)]
        year_trips = [t for t in trips if (t["date"] or "").startswith(year)]

        def by_category(ttype):
            m = {}
            for t in year_tx:
                if t["type"] == ttype:
                    m[t["category"]] = m.get(t["category"], 0) + t["amount"]
            return sorted(m.items(), key=lambda kv: -kv[1])

        income_cats = by_category("income")
        expense_cats = by_category("expense")
        gesamtleistung = sum(v for _, v in income_cats)
        trip_costs = sum(t["km"] * t["rate"] for t in year_trips)
        gesamtkosten = sum(v for _, v in expense_cats) + trip_costs
        betriebsergebnis = gesamtleistung - gesamtkosten
        bewirtung_korrektur = bewirtung_nicht_abziehbar(year_tx)
        steuerlicher_gewinn = betriebsergebnis + bewirtung_korrektur

        def quote(v):
            return f"{(v / gesamtleistung * 100):.1f} %" if gesamtleistung > 0 else "—"

        for w in self.bwa_panel.winfo_children():
            w.destroy()
        ttb.Label(self.bwa_panel, text=f"Geschäftsjahr {year} · Einnahmen-Überschuss-Basis",
                   foreground=INK_SOFT, font=("Segoe UI", 8)).pack(anchor="w", pady=(0, 6))
        self._row(self.bwa_panel, "Erlöse", "Quote", bold=True)
        if not income_cats:
            self._row(self.bwa_panel, "Keine Einnahmen erfasst", "")
        for cat, v in income_cats:
            self._row(self.bwa_panel, cat, f"{eur(v)} · {quote(v)}")
        self._row(self.bwa_panel, "= Gesamtleistung", f"{eur(gesamtleistung)} · 100 %", bold=True)

        ttb.Separator(self.bwa_panel).pack(fill="x", pady=6)
        self._row(self.bwa_panel, "Kostenarten", "")
        if not expense_cats and trip_costs == 0:
            self._row(self.bwa_panel, "Keine Ausgaben erfasst", "")
        for cat, v in expense_cats:
            label = cat + (" (nur 70 % abziehbar)" if cat == "Bewirtungskosten" else "")
            self._row(self.bwa_panel, label, f"{eur(v)} · {quote(v)}")
        if trip_costs > 0:
            self._row(self.bwa_panel, "Fahrtkosten (km-Pauschale)", f"{eur(trip_costs)} · {quote(trip_costs)}")
        self._row(self.bwa_panel, "= Gesamtkosten", f"{eur(gesamtkosten)} · {quote(gesamtkosten)}", bold=True)

        ttb.Separator(self.bwa_panel).pack(fill="x", pady=6)
        self._row(self.bwa_panel, "Betriebsergebnis", f"{eur(betriebsergebnis)} · {quote(betriebsergebnis)}",
                   bold=True, color=GREEN if betriebsergebnis >= 0 else RED)
        if bewirtung_korrektur > 0:
            self._row(self.bwa_panel, "+ nicht abziehbare Bewirtungskosten (30 %)", f"+{eur(bewirtung_korrektur)}")
            self._row(self.bwa_panel, "= Steuerlicher Gewinn (EÜR-Basis)", eur(steuerlicher_gewinn),
                       bold=True, color=GREEN if steuerlicher_gewinn >= 0 else RED)

        for w in self.chart_panel.winfo_children():
            w.destroy()
        monthly = {}
        for m in range(1, 13):
            monthly[f"{m:02d}"] = {"Einnahmen": 0, "Ausgaben": 0}
        for t in year_tx:
            m = (t["date"] or "")[5:7]
            if m in monthly:
                monthly[m]["Einnahmen" if t["type"] == "income" else "Ausgaben"] += t["amount"]
        for t in year_trips:
            m = (t["date"] or "")[5:7]
            if m in monthly:
                monthly[m]["Ausgaben"] += t["km"] * t["rate"]
        has_data = bool(year_tx or year_trips)
        if not has_data:
            ttb.Label(self.chart_panel, text="Noch keine Daten in diesem Jahr.",
                       foreground=INK_SOFT, font=("Segoe UI", 9, "italic")).pack(anchor="w")
        else:
            fig = Figure(figsize=(6.6, 2.6), dpi=100)
            ax = fig.add_subplot(111)
            keys = sorted(monthly.keys())
            x = range(len(keys))
            width = 0.35
            ax.bar([i - width / 2 for i in x], [monthly[k]["Einnahmen"] for k in keys], width,
                   label="Einnahmen", color=GREEN)
            ax.bar([i + width / 2 for i in x], [monthly[k]["Ausgaben"] for k in keys], width,
                   label="Ausgaben", color=RED)
            ax.set_xticks(list(x))
            ax.set_xticklabels([month_label(f"{year}-{k}") for k in keys], fontsize=7)
            ax.tick_params(axis="y", labelsize=8)
            ax.legend(fontsize=8, frameon=False)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            fig.tight_layout()
            canvas = FigureCanvasTkAgg(fig, master=self.chart_panel)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True)

        for w in self.open_panel.winfo_children():
            w.destroy()
        open_invoices = [i for i in invoices if i["status"] != "paid"]
        open_invoices.sort(key=lambda i: i["due_date"] or i["date"] or "")
        if not open_invoices:
            ttb.Label(self.open_panel, text="Keine offenen Rechnungen — alles bezahlt.",
                       foreground=INK_SOFT, font=("Segoe UI", 9, "italic")).pack(anchor="w")
        else:
            today = date.today().isoformat()
            for inv in open_invoices:
                cust = customers.get(inv["customer_id"], {})
                overdue = inv["due_date"] and inv["due_date"] < today
                row = ttb.Frame(self.open_panel)
                row.pack(fill="x", pady=3)
                ttb.Label(row, text=fmt_date(inv["date"]), width=11, foreground=INK_SOFT,
                           font=("Consolas", 9)).pack(side="left")
                info = ttb.Frame(row)
                info.pack(side="left", fill="x", expand=True, padx=(6, 0))
                ttb.Label(info, text=f"{inv['number']} · {cust.get('firma','—')}").pack(anchor="w")
                if overdue:
                    ttb.Label(info, text="Überfällig", foreground=RED, font=("Segoe UI", 8, "bold")).pack(anchor="w")
                ttb.Label(row, text=eur(invoice_total(inv, inv["items"])),
                           font=("Consolas", 9, "bold")).pack(side="right")
