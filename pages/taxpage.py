from datetime import date

import ttkbootstrap as ttb
from tkinter import messagebox

from utils import eur
import tax as taxmod

INK = "#1F2A24"
INK_SOFT = "#5B655D"
GREEN = "#2F6F4E"
RED = "#A63D40"
RUST = "#A63D40"


class TaxPage(ttb.Frame):
    def __init__(self, master, db):
        super().__init__(master, padding=18)
        self.db = db
        settings = db.get_tax_settings()
        self.vars = {}
        for key, val in settings.items():
            if isinstance(val, bool):
                self.vars[key] = ttb.BooleanVar(value=val)
            else:
                self.vars[key] = ttb.StringVar(value=str(val))
        self._build()
        self.refresh()

    def _field(self, parent, key, label, row, col):
        ttb.Label(parent, text=label).grid(row=row, column=col, sticky="w", padx=4)
        ttb.Entry(parent, textvariable=self.vars[key]).grid(row=row + 1, column=col, sticky="ew", padx=4, pady=(0, 8))

    def _build(self):
        form_panel = ttb.Labelframe(self, text="Angaben zur Steuerschätzung", padding=14)
        form_panel.pack(fill="x", pady=(0, 14))

        top = ttb.Frame(form_panel)
        top.pack(fill="x", pady=(0, 8))
        ttb.Checkbutton(top, text="Ehegattensplitting anwenden", variable=self.vars["splitting"],
                         command=self.refresh).pack(side="left")
        ttb.Label(top, text="Kinder").pack(side="left", padx=(20, 4))
        ttb.Entry(top, textvariable=self.vars["children"], width=5).pack(side="left")

        grid = ttb.Frame(form_panel)
        grid.pack(fill="x")
        grid.columnconfigure((0, 1), weight=1)

        self._field(grid, "salarySelf", "Bruttogehalt (du) €/Jahr", 0, 0)
        self._field(grid, "commuteDaysSelf", "Pendeltage/Jahr (du)", 2, 0)
        self._field(grid, "commuteKmSelf", "Entfernung einfach km (du)", 4, 0)
        self._field(grid, "homeofficeDaysSelf", "Homeoffice-Tage/Jahr (du)", 6, 0)
        self._field(grid, "otherWkSelf", "Sonstige Werbungskosten (du) €", 8, 0)

        self.partner_widgets = []
        r0 = 0
        for key, label, r in [
            ("salaryPartner", "Bruttogehalt (Partnerin) €/Jahr", 0),
            ("commuteDaysPartner", "Pendeltage/Jahr (Partnerin)", 2),
            ("commuteKmPartner", "Entfernung einfach km (Partnerin)", 4),
            ("homeofficeDaysPartner", "Homeoffice-Tage/Jahr (Partnerin)", 6),
            ("otherWkPartner", "Sonstige Werbungskosten (Partnerin) €", 8),
        ]:
            lbl = ttb.Label(grid, text=label)
            lbl.grid(row=r, column=1, sticky="w", padx=4)
            ent = ttb.Entry(grid, textvariable=self.vars[key])
            ent.grid(row=r + 1, column=1, sticky="ew", padx=4, pady=(0, 8))
            self.partner_widgets += [lbl, ent]

        p35a_panel = ttb.Labelframe(form_panel, text="§35a EStG — Haushalt & Handwerker (20 % Steuerbonus)", padding=10)
        p35a_panel.pack(fill="x", pady=(8, 0))
        p35a_panel.columnconfigure((0, 1, 2), weight=1)
        self._field(p35a_panel, "handwerkerKosten", "Handwerkerleistungen € (Arbeitskosten, Kappung 1.200 €)", 0, 0)
        self._field(p35a_panel, "haushaltKosten", "Haushaltsnahe Dienstleistungen € (Kappung 4.000 €)", 0, 1)
        self._field(p35a_panel, "minijobKosten", "Haushaltsnaher Minijob € (Kappung 510 €)", 0, 2)

        neben_panel = ttb.Labelframe(form_panel, text="Nebengewerbe — Stundenlohn", padding=10)
        neben_panel.pack(fill="x", pady=(8, 0))
        ttb.Label(neben_panel, text="Im Nebengewerbe geleistete Arbeitsstunden pro Jahr").grid(row=0, column=0, sticky="w", padx=4)
        ttb.Entry(neben_panel, textvariable=self.vars["nebenHours"], width=12).grid(row=1, column=0, sticky="w", padx=4, pady=(0, 4))
        ttb.Label(neben_panel, text="Daraus berechnet die App den Brutto-/Netto-Stundenlohn und den "
                                    "tatsächlichen Steuersatz, der auf deinen Stundenlohn entfällt.",
                   foreground=INK_SOFT, font=("Segoe UI", 8), wraplength=560, justify="left").grid(
            row=2, column=0, sticky="w", padx=4)

        ttb.Button(form_panel, text="✓ Speichern", bootstyle="dark",
                    command=self._save).pack(anchor="w", pady=(8, 0))

        self.result_panel = ttb.Labelframe(self, text="Geschätzte Steuerlast durch das Gewerbe", padding=14)
        self.result_panel.pack(fill="both", expand=True, pady=(0, 14))

        tariff_panel = ttb.Labelframe(self, text=f"Hinterlegter Tarif {taxmod.TAX_TARIFF_2026['year']} (§32a EStG)", padding=14)
        tariff_panel.pack(fill="x")
        for label, rate in taxmod.TAX_TARIFF_2026["zones"]:
            row = ttb.Frame(tariff_panel)
            row.pack(fill="x", pady=1)
            ttb.Label(row, text=label).pack(side="left")
            ttb.Label(row, text=rate, font=("Consolas", 9)).pack(side="right")
        ttb.Label(tariff_panel,
                   text="Beim Ehegattensplitting wird das gemeinsame Einkommen halbiert, die Steuer darauf berechnet "
                        "und verdoppelt. Für Kinder rechnet die App automatisch die Günstigerprüfung "
                        "(Kinderfreibetrag gegen Kindergeld). Nicht enthalten: Vorsorgeaufwendungen, Sonderausgaben, "
                        "Soli, Kirchensteuer. Verbindliche Berechnung: Steuerberater oder Finanzamt.",
                   foreground=INK_SOFT, wraplength=680, justify="left", font=("Segoe UI", 8)).pack(anchor="w", pady=(8, 0))

        self._toggle_partner_fields()

    def _toggle_partner_fields(self):
        state = "normal" if self.vars["splitting"].get() else "disabled"
        for w in self.partner_widgets:
            try:
                w.configure(state=state)
            except Exception:
                pass

    def _collect(self):
        data = {}
        for k, v in self.vars.items():
            if isinstance(v, ttb.BooleanVar):
                data[k] = v.get()
            else:
                raw = v.get().strip().replace(",", ".")
                try:
                    data[k] = float(raw) if raw else 0
                except ValueError:
                    data[k] = 0
        return data

    def _save(self):
        self.db.save_tax_settings(self._collect())
        self.refresh()
        messagebox.showinfo("Gespeichert", "Angaben wurden gespeichert.")

    def refresh(self):
        self._toggle_partner_fields()
        form = self._collect()
        splitting = bool(form["splitting"])
        kids = int(form["children"])

        transactions = self.db.list_transactions()
        trips = self.db.list_trips()
        year = str(date.today().year)
        year_tx = [t for t in transactions if (t["date"] or "").startswith(year)]
        year_trips = [t for t in trips if (t["date"] or "").startswith(year)]
        income = sum(t["amount"] for t in year_tx if t["type"] == "income")
        expense = sum(t["amount"] for t in year_tx if t["type"] == "expense")
        trip_costs = sum(t["km"] * t["rate"] for t in year_trips)
        bewirtung_korrektur = taxmod.bewirtung_nicht_abziehbar(year_tx)
        profit = income - expense - trip_costs + bewirtung_korrektur

        wk_self = taxmod.werbungskosten(form["commuteDaysSelf"], form["commuteKmSelf"],
                                         form["homeofficeDaysSelf"], form["otherWkSelf"])
        wk_partner = taxmod.werbungskosten(form["commuteDaysPartner"], form["commuteKmPartner"],
                                            form["homeofficeDaysPartner"], form["otherWkPartner"]) if splitting else 0

        zve_without = max(0, form["salarySelf"] - wk_self + (form["salaryPartner"] - wk_partner if splitting else 0))
        zve_with = zve_without + profit

        res_without = taxmod.effective_tax(zve_without, splitting, kids)
        res_with = taxmod.effective_tax(zve_with, splitting, kids)
        p35a_bonus = taxmod.p35a_bonus(form["handwerkerKosten"], form["haushaltKosten"], form["minijobKosten"])
        tax_without = res_without["tax"]
        tax_with = max(0, res_with["tax"] - p35a_bonus)
        extra_tax = tax_with - tax_without
        net_profit = profit - extra_tax
        effective_rate_on_profit = (extra_tax / profit * 100) if profit > 0 else 0
        marginal = (taxmod.income_tax(zve_with + 100, splitting) - taxmod.income_tax(zve_with, splitting))
        avg_rate = (tax_with / zve_with * 100) if zve_with > 0 else 0

        hours = form.get("nebenHours") or 0
        brutto_stundenlohn = (profit / hours) if hours > 0 else 0
        steuer_je_stunde = (extra_tax / hours) if hours > 0 else 0
        netto_stundenlohn = (net_profit / hours) if hours > 0 else 0

        for w in self.result_panel.winfo_children():
            w.destroy()

        top = ttb.Frame(self.result_panel)
        top.pack(fill="x", pady=(0, 10))
        box1 = ttb.Frame(top, bootstyle="light", padding=12)
        box1.configure(relief="solid", borderwidth=1)
        box1.pack(side="left", expand=True, fill="x", padx=(0, 6))
        ttb.Label(box1, text="ZUSÄTZLICHE EINKOMMENSTEUER AUF DEN GEWINN", font=("Segoe UI", 8, "bold"),
                   foreground=INK_SOFT).pack(anchor="w")
        ttb.Label(box1, text=eur(extra_tax), font=("Segoe UI", 16, "bold"), foreground=RUST).pack(anchor="w")
        ttb.Label(box1, text=f"≈ {effective_rate_on_profit:.1f} % deines Gewinns von {eur(profit)}",
                   foreground=INK_SOFT, font=("Segoe UI", 8)).pack(anchor="w")

        box2 = ttb.Frame(top, bootstyle="light", padding=12)
        box2.configure(relief="solid", borderwidth=1)
        box2.pack(side="left", expand=True, fill="x", padx=(6, 6))
        ttb.Label(box2, text="GEWINN NACH STEUERN (NETTO)", font=("Segoe UI", 8, "bold"),
                   foreground=INK_SOFT).pack(anchor="w")
        ttb.Label(box2, text=eur(net_profit), font=("Segoe UI", 16, "bold"), foreground=GREEN).pack(anchor="w")

        box3 = ttb.Frame(top, bootstyle="light", padding=12)
        box3.configure(relief="solid", borderwidth=1)
        box3.pack(side="left", expand=True, fill="x", padx=(6, 0))
        ttb.Label(box3, text="TATSÄCHLICHER STEUERSATZ AUF DEN STUNDENLOHN", font=("Segoe UI", 8, "bold"),
                   foreground=INK_SOFT).pack(anchor="w")
        ttb.Label(box3, text=f"{effective_rate_on_profit:.1f} %", font=("Segoe UI", 16, "bold"),
                   foreground=RUST).pack(anchor="w")
        if hours > 0:
            ttb.Label(box3, text=f"{eur(steuer_je_stunde)} Steuer je Stunde",
                       foreground=INK_SOFT, font=("Segoe UI", 8)).pack(anchor="w")
        else:
            ttb.Label(box3, text="Arbeitsstunden oben eintragen für den Stundenlohn",
                       foreground=INK_SOFT, font=("Segoe UI", 8)).pack(anchor="w")

        def row(label, value, bold=False, color=INK):
            r = ttb.Frame(self.result_panel)
            r.pack(fill="x", pady=1)
            ttb.Label(r, text=label, font=("Segoe UI", 9, "bold" if bold else "normal")).pack(side="left")
            ttb.Label(r, text=value, font=("Consolas", 9), foreground=color).pack(side="right")

        total_salary = form["salarySelf"] + (form["salaryPartner"] if splitting else 0)
        row("Bruttogehälter gesamt", eur(total_salary))
        row("− Werbungskosten (du)", eur(wk_self))
        if splitting:
            row("− Werbungskosten (Partnerin)", eur(wk_partner))
        row("= Zu versteuerndes Einkommen ohne Gewerbe", eur(zve_without))
        row("+ Gewinn aus Gewerbe (nach Fahrtkosten)", eur(profit))
        if bewirtung_korrektur > 0:
            row("Darin enthalten: nicht abziehbare Bewirtungskosten (30 %)", f"+{eur(bewirtung_korrektur)}")
        row("= Zu versteuerndes Einkommen gesamt", eur(zve_with), bold=True)
        if kids > 0:
            row(f"Kinderfreibeträge ({kids} × {eur(taxmod.KINDERFREIBETRAG_PRO_KIND)})",
                eur(kids * taxmod.KINDERFREIBETRAG_PRO_KIND))
            row("Günstigerprüfung (automatisch)",
                "Kinderfreibetrag angesetzt" if res_with["freibetrag_applied"] else "Kindergeld ist günstiger")
        row("Steuerbelastung ohne Gewerbe", eur(tax_without))
        row("Steuerbelastung mit Gewerbe", eur(tax_with))
        if p35a_bonus > 0:
            row("Darin abgezogen: Steuerermäßigung §35a", f"−{eur(p35a_bonus)}")
        row("Grenzsteuersatz (nächster Euro)", f"{marginal:.1f} %")
        row("Durchschnittssteuersatz gesamt", f"{avg_rate:.1f} %")
        if hours > 0:
            ttb.Separator(self.result_panel).pack(fill="x", pady=6)
            row(f"Arbeitsstunden im Nebengewerbe", f"{hours:g} h")
            row("Brutto-Stundenlohn (vor Steuer)", eur(brutto_stundenlohn), bold=True)
            row("− Steuer je Stunde", eur(steuer_je_stunde), color=RUST)
            row("= Netto-Stundenlohn (nach Steuer)", eur(netto_stundenlohn), bold=True, color=GREEN)
