import os
from datetime import date

import ttkbootstrap as ttb
from tkinter import messagebox, filedialog

from utils import eur, fmt_date, today_de, parse_de, today_iso
from excel_export import export_trips_excel
import template_letter

INK_SOFT = "#5B655D"
GREEN = "#2F6F4E"
INK = "#1F2A24"


class TripsPage(ttb.Frame):
    def __init__(self, master, db):
        super().__init__(master, padding=18)
        self.db = db
        self.year_var = ttb.StringVar(value=str(date.today().year))
        self.selected = {}   # trip id -> BooleanVar
        self._build()
        self.refresh()

    def _build(self):
        self.stats_row = ttb.Frame(self)
        self.stats_row.pack(fill="x", pady=(0, 14))

        form_panel = ttb.Labelframe(self, text="Neue Fahrt erfassen", padding=14)
        form_panel.pack(fill="x", pady=(0, 14))
        grid = ttb.Frame(form_panel)
        grid.pack(fill="x")
        grid.columnconfigure((0, 1), weight=1)

        self.date_var = ttb.StringVar(value=today_de())
        self.purpose_var = ttb.StringVar()
        self.from_var = ttb.StringVar()
        self.to_var = ttb.StringVar()
        self.km_var = ttb.StringVar()
        self.rate_var = ttb.StringVar(value="0.30")

        ttb.Label(grid, text="Datum (TT.MM.JJJJ)").grid(row=0, column=0, sticky="w")
        ttb.Entry(grid, textvariable=self.date_var).grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=(0, 8))
        ttb.Label(grid, text="Anlass / Zweck (Pflicht fürs Finanzamt)").grid(row=0, column=1, sticky="w")
        ttb.Entry(grid, textvariable=self.purpose_var).grid(row=1, column=1, sticky="ew", pady=(0, 8))
        ttb.Label(grid, text="Start-Adresse").grid(row=2, column=0, sticky="w")
        ttb.Entry(grid, textvariable=self.from_var).grid(row=3, column=0, sticky="ew", padx=(0, 6), pady=(0, 8))
        ttb.Label(grid, text="Ziel-Adresse").grid(row=2, column=1, sticky="w")
        ttb.Entry(grid, textvariable=self.to_var).grid(row=3, column=1, sticky="ew", pady=(0, 8))
        ttb.Label(grid, text="Gefahrene km (hin + zurück)").grid(row=4, column=0, sticky="w")
        ttb.Entry(grid, textvariable=self.km_var).grid(row=5, column=0, sticky="ew", padx=(0, 6))
        ttb.Label(grid, text="Satz €/km").grid(row=4, column=1, sticky="w")
        ttb.Entry(grid, textvariable=self.rate_var).grid(row=5, column=1, sticky="ew")

        ttb.Label(form_panel, text="⚠ Bitte die tatsächlich gefahrenen Kilometer für Hin- UND Rückfahrt eintragen.",
                   foreground="#A63D40", font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(6, 0))

        ttb.Button(form_panel, text="＋ Fahrt hinzufügen", bootstyle="dark",
                    command=self._add_trip).pack(anchor="w", pady=(10, 0))

        list_panel = ttb.Labelframe(self, text="Fahrten", padding=14)
        list_panel.pack(fill="both", expand=True)
        header = ttb.Frame(list_panel)
        header.pack(fill="x", pady=(0, 6))
        ttb.Label(header, text="Jahr").pack(side="left")
        self.year_combo = ttb.Combobox(header, textvariable=self.year_var, width=8, state="readonly")
        self.year_combo.pack(side="left", padx=(6, 12))
        self.year_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        ttb.Button(header, text="Alle auswählen", bootstyle="secondary-outline",
                    command=lambda: self._select_all(True)).pack(side="left", padx=(0, 4))
        ttb.Button(header, text="Auswahl aufheben", bootstyle="secondary-outline",
                    command=lambda: self._select_all(False)).pack(side="left", padx=(0, 12))
        ttb.Button(header, text="⬇ Excel-Export", bootstyle="secondary-outline",
                    command=self._export_excel).pack(side="left", padx=(0, 4))
        ttb.Button(header, text="⬇ PDF-Export (Vorlage)", bootstyle="secondary-outline",
                    command=self._export_pdf).pack(side="left")

        ttb.Label(list_panel, text="Tipp: Häkchen setzen, um nur einzelne Fahrten zu exportieren. "
                                   "Ohne Auswahl werden alle Fahrten des Jahres exportiert.",
                   foreground=INK_SOFT, font=("Segoe UI", 8)).pack(anchor="w", pady=(0, 6))

        self.list_container = ttb.Frame(list_panel)
        self.list_container.pack(fill="both", expand=True)

        ttb.Label(self, text="Die Kilometerpauschale gilt für betrieblich veranlasste Fahrten (z. B. zum Kunden). "
                              "Fahrten zwischen Wohnung und fester Betriebsstätte zählen nicht dazu (Entfernungspauschale).",
                   foreground=INK_SOFT, wraplength=680, justify="left", font=("Segoe UI", 8)).pack(anchor="w", pady=(8, 0))

    def _add_trip(self):
        try:
            km = float(self.km_var.get().replace(",", "."))
            rate = float(self.rate_var.get().replace(",", "."))
        except ValueError:
            messagebox.showerror("Ungültige Eingabe", "Bitte gültige Zahlen für km und Satz eingeben.")
            return
        if km <= 0 or not self.purpose_var.get().strip():
            messagebox.showerror("Fehlende Angabe", "Bitte km und Anlass angeben.")
            return
        iso_date = parse_de(self.date_var.get())
        if iso_date is None:
            messagebox.showerror("Ungültiges Datum", "Bitte ein gültiges Datum im Format TT.MM.JJJJ eingeben.")
            return
        self.db.add_trip({
            "date": iso_date or today_iso(),
            "purpose": self.purpose_var.get(),
            "origin": self.from_var.get(),
            "destination": self.to_var.get(),
            "km": km,
            "rate": rate,
        })
        self.purpose_var.set("")
        self.from_var.set("")
        self.to_var.set("")
        self.km_var.set("")
        self.refresh()

    def _delete(self, tid):
        if messagebox.askyesno("Löschen", "Diese Fahrt wirklich löschen?"):
            self.db.delete_trip(tid)
            self.refresh()

    def _select_all(self, value):
        for var in self.selected.values():
            var.set(value)

    def _year_trips(self):
        trips = [t for t in self.db.list_trips() if (t["date"] or "").startswith(self.year_var.get())]
        trips.sort(key=lambda t: t["date"] or "", reverse=True)
        return trips

    def _chosen_trips(self):
        """Ausgewählte Fahrten; wenn keine ausgewählt sind, alle des Jahres."""
        year_trips = self._year_trips()
        chosen = [t for t in year_trips if self.selected.get(t["id"]) and self.selected[t["id"]].get()]
        return chosen if chosen else year_trips

    def _export_excel(self):
        trips = self._chosen_trips()
        if not trips:
            messagebox.showinfo("Keine Daten", "Keine Fahrten in diesem Jahr.")
            return
        company = self.db.get_company()
        default_name = f"Fahrtkosten_{company.get('name','Firma')}_{self.year_var.get()}.xlsx".replace(" ", "_")
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile=default_name,
                                             filetypes=[("Excel", "*.xlsx")])
        if not path:
            return
        export_trips_excel(path, trips, self.year_var.get(), company)
        messagebox.showinfo("Erstellt", f"Excel-Datei gespeichert ({len(trips)} Fahrten): {os.path.basename(path)}")

    def _export_pdf(self):
        trips = self._chosen_trips()
        if not trips:
            messagebox.showinfo("Keine Daten", "Keine Fahrten in diesem Jahr.")
            return
        company = self.db.get_company()
        props = template_letter.load_properties()
        default_name = f"Fahrtkosten_{self.year_var.get()}.docx"
        path = filedialog.asksaveasfilename(defaultextension=".docx", initialfile=default_name,
                                             filetypes=[("Word-Dokument", "*.docx")])
        if not path:
            return

        trips_sorted = sorted(trips, key=lambda t: t.get("date") or "")
        total_km = sum(float(t.get("km") or 0) for t in trips_sorted)
        total_eur = sum(float(t.get("km") or 0) * float(t.get("rate") or 0) for t in trips_sorted)
        lines = [props.get("text_fahrten", "nachfolgend die Aufstellung der betrieblichen Fahrten:"), ""]
        for t in trips_sorted:
            km = float(t.get("km") or 0)
            rate = float(t.get("rate") or 0)
            strecke = " → ".join(filter(None, [t.get("origin"), t.get("destination")]))
            lines.append(f"{fmt_date(t.get('date'))} · {t.get('purpose','')} · {strecke} · "
                         f"{km:g} km (hin + zurück) × {eur(rate)} = {eur(km * rate)}")
        lines.append("")
        lines.append(f"Summe: {total_km:g} km · {eur(total_eur)}")
        lines.append("")
        lines.append("Hinweis: Die angegebenen Kilometer sind die tatsächlich gefahrene Strecke (Hin- und Rückfahrt).")

        values = {
            "name": company.get("name", ""),
            "strasse": company.get("addressLine1", ""),
            "plz_ort": company.get("addressLine2", ""),
            "datum": today_de(),
            "betreff": f"{props.get('betreff_fahrten', 'Fahrtkostenaufstellung')} {self.year_var.get()}",
            "text": "\n".join(lines),
            "anrede": None,
        }
        try:
            template_letter.fill_template(values, path)
            if messagebox.askyesno("PDF erzeugen?",
                                    "Word-Datei gespeichert.\n\nSoll zusätzlich eine PDF-Version aus der Vorlage "
                                    "erzeugt werden? (benötigt Word oder LibreOffice)"):
                pdf_path = os.path.splitext(path)[0] + ".pdf"
                try:
                    template_letter.convert_to_pdf(path, pdf_path)
                    messagebox.showinfo("Erstellt", f"Gespeichert:\n{os.path.basename(path)}\n{os.path.basename(pdf_path)}")
                    return
                except Exception as e:
                    messagebox.showwarning("PDF nicht erzeugt", str(e))
            messagebox.showinfo("Erstellt", f"Fahrtkosten-Dokument gespeichert: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Fehler", f"Dokument konnte nicht erstellt werden:\n{e}")

    def refresh(self):
        trips = self.db.list_trips()
        years = sorted({(t["date"] or "")[:4] for t in trips if t["date"]}, reverse=True)
        current_year = str(date.today().year)
        if current_year not in years:
            years.insert(0, current_year)
        self.year_combo["values"] = years
        if self.year_var.get() not in years:
            self.year_var.set(current_year)

        year_trips = self._year_trips()
        total_km = sum(t["km"] for t in year_trips)
        total_eur = sum(t["km"] * t["rate"] for t in year_trips)

        for w in self.stats_row.winfo_children():
            w.destroy()
        from pages.dashboard import StatCard
        StatCard(self.stats_row, f"Kilometer {self.year_var.get()}",
                  f"{total_km:,.0f} km".replace(",", "."), INK).pack(side="left", expand=True, fill="x", padx=4)
        StatCard(self.stats_row, f"Fahrtkosten {self.year_var.get()}", eur(total_eur), GREEN).pack(
            side="left", expand=True, fill="x", padx=4)

        for w in self.list_container.winfo_children():
            w.destroy()
        self.selected = {}
        if not year_trips:
            ttb.Label(self.list_container, text="Noch keine Fahrten in diesem Jahr erfasst.",
                       foreground=INK_SOFT, font=("Segoe UI", 9, "italic")).pack(anchor="w")
            return
        for t in year_trips:
            row = ttb.Frame(self.list_container)
            row.pack(fill="x", pady=3)
            var = ttb.BooleanVar(value=False)
            self.selected[t["id"]] = var
            ttb.Checkbutton(row, variable=var).pack(side="left", padx=(0, 6))
            ttb.Label(row, text=fmt_date(t["date"]), width=11,
                       foreground=INK_SOFT, font=("Consolas", 9)).pack(side="left")
            info = ttb.Frame(row)
            info.pack(side="left", fill="x", expand=True, padx=(6, 0))
            ttb.Label(info, text=t["purpose"]).pack(anchor="w")
            sub = " → ".join(filter(None, [t["origin"], t["destination"]]))
            sub += f" · {t['km']:,.1f} km (hin + zurück) × {eur(t['rate'])}".replace(",", ".")
            ttb.Label(info, text=sub, foreground=INK_SOFT, font=("Consolas", 8)).pack(anchor="w")
            ttb.Label(row, text=eur(t["km"] * t["rate"]), foreground=GREEN,
                       font=("Consolas", 9, "bold")).pack(side="right", padx=(6, 0))
            ttb.Button(row, text="🗑", bootstyle="link",
                        command=lambda tid=t["id"]: self._delete(tid)).pack(side="right")
