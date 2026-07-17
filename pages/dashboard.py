import ttkbootstrap as ttb
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from utils import eur, fmt_date, month_label

GREEN = "#2F6F4E"
RED = "#A63D40"
INK = "#1F2A24"
INK_SOFT = "#5B655D"


class StatCard(ttb.Frame):
    def __init__(self, master, label, value, color):
        super().__init__(master, bootstyle="light", padding=14)
        self.configure(relief="solid", borderwidth=1)
        ttb.Label(self, text=label.upper(), font=("Segoe UI", 8, "bold"),
                   foreground=INK_SOFT).pack(anchor="w")
        ttb.Label(self, text=value, font=("Segoe UI", 16, "bold"),
                   foreground=color).pack(anchor="w", pady=(2, 0))


class DashboardPage(ttb.Frame):
    def __init__(self, master, db):
        super().__init__(master, padding=18)
        self.db = db
        self.refresh()

    def refresh(self):
        for w in self.winfo_children():
            w.destroy()

        transactions = self.db.list_transactions()
        invoices = self.db.list_invoices()
        income = sum(t["amount"] for t in transactions if t["type"] == "income")
        expense = sum(t["amount"] for t in transactions if t["type"] == "expense")
        open_invoices = sum(
            _invoice_total(i) for i in invoices if i["status"] != "paid"
        )

        cards = ttb.Frame(self)
        cards.pack(fill="x", pady=(0, 16))
        StatCard(cards, "Einnahmen", eur(income), GREEN).pack(side="left", expand=True, fill="x", padx=4)
        StatCard(cards, "Ausgaben", eur(expense), RED).pack(side="left", expand=True, fill="x", padx=4)
        StatCard(cards, "Offene Rechnungen", eur(open_invoices), INK).pack(side="left", expand=True, fill="x", padx=4)

        chart_panel = ttb.Labelframe(self, text="Monatsverlauf", padding=10)
        chart_panel.pack(fill="both", expand=False, pady=(0, 16))
        self._draw_chart(chart_panel, transactions)

        ledger_panel = ttb.Labelframe(self, text="Letzte Buchungen", padding=10)
        ledger_panel.pack(fill="both", expand=True)
        recent = sorted(transactions, key=lambda t: t["date"] or "", reverse=True)[:8]
        if not recent:
            ttb.Label(ledger_panel, text="Noch keine Buchungen erfasst.",
                       foreground=INK_SOFT, font=("Segoe UI", 9, "italic")).pack(anchor="w")
        else:
            for t in recent:
                row = ttb.Frame(ledger_panel)
                row.pack(fill="x", pady=3)
                ttb.Label(row, text=fmt_date(t["date"]), width=11,
                           foreground=INK_SOFT, font=("Consolas", 9)).pack(side="left")
                ttb.Label(row, text=t["description"] or t["category"]).pack(side="left", padx=(6, 0))
                color = GREEN if t["type"] == "income" else RED
                sign = "+" if t["type"] == "income" else "−"
                ttb.Label(row, text=f"{sign} {eur(t['amount'])}", foreground=color,
                           font=("Consolas", 9, "bold")).pack(side="right")

    def _draw_chart(self, parent, transactions):
        monthly = {}
        for t in transactions:
            key = (t["date"] or "")[:7]
            if not key:
                continue
            monthly.setdefault(key, {"Einnahmen": 0, "Ausgaben": 0})
            if t["type"] == "income":
                monthly[key]["Einnahmen"] += t["amount"]
            else:
                monthly[key]["Ausgaben"] += t["amount"]
        keys = sorted(monthly.keys())[-12:]
        if not keys:
            ttb.Label(parent, text="Noch keine Buchungen erfasst. Trage deine erste Einnahme oder Ausgabe ein.",
                       foreground=INK_SOFT, font=("Segoe UI", 9, "italic")).pack(anchor="w")
            return
        fig = Figure(figsize=(6.6, 2.6), dpi=100)
        ax = fig.add_subplot(111)
        x = range(len(keys))
        income_vals = [monthly[k]["Einnahmen"] for k in keys]
        expense_vals = [monthly[k]["Ausgaben"] for k in keys]
        width = 0.35
        ax.bar([i - width / 2 for i in x], income_vals, width, label="Einnahmen", color=GREEN)
        ax.bar([i + width / 2 for i in x], expense_vals, width, label="Ausgaben", color=RED)
        ax.set_xticks(list(x))
        ax.set_xticklabels([month_label(k) for k in keys], fontsize=8)
        ax.tick_params(axis="y", labelsize=8)
        ax.legend(fontsize=8, frameon=False)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)


def _invoice_total(inv):
    net = sum(float(i["qty"] or 0) * float(i["price"] or 0) for i in inv["items"])
    if inv.get("kleinunternehmer"):
        return net
    return net * (1 + float(inv.get("tax_rate") or 0) / 100)
