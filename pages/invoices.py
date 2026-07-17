import os
import tempfile
from datetime import date

import ttkbootstrap as ttb
import tkinter as tk
from tkinter import messagebox, filedialog

from utils import (eur, fmt_date, today_de, parse_de, today_iso, add_days,
                   anrede, is_valid_email, UNITS)
from pdf_invoice import generate_invoice_pdf, invoice_total, invoice_net
import template_letter
import einvoice
import mailer

INK_SOFT = "#5B655D"
GREEN = "#2F6F4E"
RUST = "#A63D40"

INVOICE_TYPES = [
    ("normal", "Normale Rechnung"),
    ("abschlag", "Abschlagsrechnung"),
    ("schluss", "Schlussrechnung"),
]
TYPE_LABELS = {k: v for k, v in INVOICE_TYPES}


def compute_abschlag_info(inv, all_invoices):
    """Berechnet Auftragssumme, bereits berechnete Abschläge und Restbetrag."""
    if (inv.get("invoice_type") or "normal") not in ("abschlag", "schluss"):
        return None
    head_id = inv.get("parent_id") or inv["id"]
    project = [i for i in all_invoices
               if (i.get("parent_id") or i["id"]) == head_id
               and (i.get("invoice_type") or "normal") in ("abschlag", "schluss")]
    gesamt = 0.0
    for i in project:
        try:
            gesamt = max(gesamt, float(i.get("gesamtsumme") or 0))
        except (TypeError, ValueError):
            pass

    def sortkey(i):
        return (i.get("date") or "", i.get("number") or "")

    this_key = sortkey(inv)
    billed_before = sum(invoice_total(i, i.get("items", [])) for i in project
                        if sortkey(i) < this_key)
    this_total = invoice_total(inv, inv.get("items", []))
    remaining = gesamt - billed_before - this_total
    return {"gesamtsumme": gesamt, "billed_before": billed_before,
            "this_total": this_total, "remaining": remaining, "head_id": head_id}


class ItemRow(ttb.Frame):
    def __init__(self, master, on_remove):
        super().__init__(master)
        self.desc = ttb.StringVar()
        self.zeitraum = ttb.StringVar()
        self.qty = ttb.StringVar(value="1")
        self.unit = ttb.StringVar(value=UNITS[0])
        self.price = ttb.StringVar()
        ttb.Entry(self, textvariable=self.desc, width=22).grid(row=0, column=0, padx=2)
        ttb.Entry(self, textvariable=self.zeitraum, width=12).grid(row=0, column=1, padx=2)
        ttb.Entry(self, textvariable=self.qty, width=6).grid(row=0, column=2, padx=2)
        ttb.Combobox(self, textvariable=self.unit, values=UNITS, width=6, state="readonly").grid(row=0, column=3, padx=2)
        ttb.Entry(self, textvariable=self.price, width=8).grid(row=0, column=4, padx=2)
        ttb.Button(self, text="✕", bootstyle="link", command=lambda: on_remove(self)).grid(row=0, column=5, padx=2)

    def data(self):
        try:
            qty = float(self.qty.get().replace(",", "."))
        except ValueError:
            qty = 0
        try:
            price = float(self.price.get().replace(",", "."))
        except ValueError:
            price = 0
        return {"description": self.desc.get(), "zeitraum": self.zeitraum.get(),
                "qty": qty, "unit": self.unit.get(), "price": price}


class InvoicesPage(ttb.Frame):
    def __init__(self, master, db):
        super().__init__(master, padding=18)
        self.db = db
        self.item_rows = []
        self.customer_map = {}
        self.head_map = {}      # Label -> Rechnung (Auftrags-Kopf)
        self.props = template_letter.load_properties()
        self._build()
        self.refresh()

    # ---------- Formular ----------
    def _build(self):
        form_panel = ttb.Labelframe(self, text="Neue Rechnung erstellen", padding=14)
        form_panel.pack(fill="x", pady=(0, 14))

        top = ttb.Frame(form_panel)
        top.pack(fill="x")
        top.columnconfigure((0, 1, 2), weight=1)

        ttb.Label(top, text="Rechnungsart").grid(row=0, column=0, sticky="w")
        self.type_var = ttb.StringVar(value=TYPE_LABELS["normal"])
        type_combo = ttb.Combobox(top, textvariable=self.type_var, state="readonly",
                                  values=[v for _, v in INVOICE_TYPES])
        type_combo.grid(row=1, column=0, sticky="ew", padx=(0, 6))
        type_combo.bind("<<ComboboxSelected>>", lambda e: self._on_type_change())

        ttb.Label(top, text="Kunde").grid(row=0, column=1, sticky="w")
        self.customer_var = ttb.StringVar()
        self.customer_combo = ttb.Combobox(top, textvariable=self.customer_var, state="readonly")
        self.customer_combo.grid(row=1, column=1, sticky="ew", padx=6)
        self.customer_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_heads())

        ttb.Label(top, text="Rechnungsdatum (TT.MM.JJJJ)").grid(row=0, column=2, sticky="w")
        self.date_var = ttb.StringVar(value=today_de())
        ttb.Entry(top, textvariable=self.date_var).grid(row=1, column=2, sticky="ew", padx=(6, 0))

        # Abschlags-Bereich (nur bei Abschlags-/Schlussrechnung)
        self.abschlag_frame = ttb.Frame(form_panel)
        af = self.abschlag_frame
        af.columnconfigure((0, 1, 2), weight=1)
        ttb.Label(af, text="Gehört zu Auftrag").grid(row=0, column=0, sticky="w", pady=(10, 0))
        self.head_var = ttb.StringVar()
        self.head_combo = ttb.Combobox(af, textvariable=self.head_var, state="readonly")
        self.head_combo.grid(row=1, column=0, sticky="ew", padx=(0, 6))
        self.head_combo.bind("<<ComboboxSelected>>", lambda e: self._on_head_change())
        ttb.Label(af, text="Auftragssumme gesamt (€)").grid(row=0, column=1, sticky="w", pady=(10, 0))
        self.gesamt_var = ttb.StringVar()
        self.gesamt_entry = ttb.Entry(af, textvariable=self.gesamt_var)
        self.gesamt_entry.grid(row=1, column=1, sticky="ew", padx=6)
        self.gesamt_var.trace_add("write", lambda *a: self._update_abschlag_hint())
        self.abschlag_hint = ttb.Label(af, text="", foreground=INK_SOFT, font=("Segoe UI", 8))
        self.abschlag_hint.grid(row=1, column=2, sticky="w", padx=(6, 0))

        self._betreff_label = ttb.Label(form_panel, text="Betreff")
        self._betreff_label.pack(anchor="w", pady=(10, 0))
        self.betreff_var = ttb.StringVar(value=self.props.get("betreff", ""))
        ttb.Entry(form_panel, textvariable=self.betreff_var).pack(fill="x")

        ttb.Label(form_panel, text="Einleitungstext / Text des Schreibens").pack(anchor="w", pady=(8, 0))
        self.intro_var = ttb.StringVar(value=self.props.get("text", "").replace("\n", " "))
        ttb.Entry(form_panel, textvariable=self.intro_var).pack(fill="x")

        ttb.Label(top, text="Zahlungsziel (Tage)").grid(row=2, column=0, sticky="w", pady=(8, 0))
        company = self.db.get_company()
        self.terms_var = ttb.StringVar(value=str(company.get("paymentTermsDays", 14)))
        ttb.Entry(top, textvariable=self.terms_var).grid(row=3, column=0, sticky="ew", padx=(0, 6))

        items_panel = ttb.Frame(form_panel)
        items_panel.pack(fill="x", pady=(12, 0))
        header = ttb.Frame(items_panel)
        header.pack(fill="x")
        for text, w in [("Beschreibung", 22), ("Zeitraum", 12), ("Menge", 6), ("Einheit", 6), ("Preis €", 8), ("", 2)]:
            ttb.Label(header, text=text, width=w, foreground=INK_SOFT,
                       font=("Segoe UI", 8, "bold")).pack(side="left", padx=2)
        self.items_container = ttb.Frame(items_panel)
        self.items_container.pack(fill="x")
        ttb.Button(items_panel, text="＋ Position hinzufügen", bootstyle="secondary-outline",
                    command=self._add_item_row).pack(anchor="w", pady=(6, 0))
        self._add_item_row()

        bottom = ttb.Frame(form_panel)
        bottom.pack(fill="x", pady=(12, 0))
        self.tax_rate_var = ttb.StringVar(value="19")
        self.kleinunternehmer_var = ttb.BooleanVar(value=bool(company.get("kleinunternehmer", True)))
        ttb.Checkbutton(bottom, text="Kleinunternehmer (§19 UStG, keine MwSt.)",
                         variable=self.kleinunternehmer_var).pack(side="left")
        ttb.Label(bottom, text="MwSt.-Satz %").pack(side="left", padx=(20, 4))
        ttb.Entry(bottom, textvariable=self.tax_rate_var, width=6).pack(side="left")
        ttb.Button(bottom, text="Rechnung erstellen", bootstyle="dark",
                    command=self._create_invoice).pack(side="right")

        list_panel = ttb.Labelframe(self, text="Alle Rechnungen", padding=14)
        list_panel.pack(fill="both", expand=True)
        self.list_container = ttb.Frame(list_panel)
        self.list_container.pack(fill="both", expand=True)

    # ---------- Rechnungsart / Abschlag ----------
    def _type_key(self):
        return {v: k for k, v in TYPE_LABELS.items()}.get(self.type_var.get(), "normal")

    def _on_type_change(self):
        if self._type_key() in ("abschlag", "schluss"):
            self.abschlag_frame.pack(fill="x", before=self._betreff_label)
            self._refresh_heads()
        else:
            self.abschlag_frame.pack_forget()

    def _refresh_heads(self):
        cid = self.customer_map.get(self.customer_var.get())
        heads = []
        if cid:
            for inv in self.db.list_invoices():
                if (inv.get("invoice_type") or "normal") in ("abschlag", "schluss") \
                        and not inv.get("parent_id") and inv.get("customer_id") == cid:
                    heads.append(inv)
        self.head_map = {}
        labels = ["— neuer Auftrag —"]
        for h in heads:
            lbl = f"{h['number']} · Auftrag {eur(h.get('gesamtsumme') or 0)}"
            self.head_map[lbl] = h
            labels.append(lbl)
        self.head_combo["values"] = labels
        if self.head_var.get() not in labels:
            self.head_var.set(labels[0])
        self._on_head_change()

    def _on_head_change(self):
        head = self.head_map.get(self.head_var.get())
        if head:
            self.gesamt_var.set(f"{float(head.get('gesamtsumme') or 0):.2f}")
            self.gesamt_entry.configure(state="disabled")
        else:
            self.gesamt_entry.configure(state="normal")
        self._update_abschlag_hint()

    def _update_abschlag_hint(self):
        try:
            gesamt = float((self.gesamt_var.get() or "0").replace(",", "."))
        except ValueError:
            gesamt = 0
        head = self.head_map.get(self.head_var.get())
        billed = 0.0
        if head:
            head_id = head["id"]
            for inv in self.db.list_invoices():
                if (inv.get("parent_id") or inv["id"]) == head_id \
                        and (inv.get("invoice_type") or "normal") in ("abschlag", "schluss"):
                    billed += invoice_total(inv, inv.get("items", []))
        remaining = gesamt - billed
        self.abschlag_hint.configure(
            text=f"bereits berechnet: {eur(billed)} · noch offen: {eur(remaining)}")

    # ---------- Positionen ----------
    def _add_item_row(self):
        row = ItemRow(self.items_container, self._remove_item_row)
        row.pack(fill="x", pady=2)
        self.item_rows.append(row)

    def _remove_item_row(self, row):
        if len(self.item_rows) <= 1:
            return
        self.item_rows.remove(row)
        row.destroy()

    # ---------- Erstellen ----------
    def _create_invoice(self):
        if self.customer_var.get() not in self.customer_map:
            messagebox.showerror("Kunde fehlt", "Bitte einen Kunden auswählen.")
            return
        items = [r.data() for r in self.item_rows if r.data()["description"]]
        if not items:
            messagebox.showerror("Positionen fehlen", "Bitte mindestens eine Position eingeben.")
            return
        iso_date = parse_de(self.date_var.get())
        if iso_date is None:
            messagebox.showerror("Ungültiges Datum", "Bitte ein gültiges Datum im Format TT.MM.JJJJ eingeben.")
            return
        iso_date = iso_date or today_iso()
        try:
            terms = int(self.terms_var.get())
        except ValueError:
            terms = 14

        itype = self._type_key()
        parent_id = None
        gesamtsumme = None
        if itype in ("abschlag", "schluss"):
            head = self.head_map.get(self.head_var.get())
            if head:
                parent_id = head["id"]
                gesamtsumme = float(head.get("gesamtsumme") or 0)
            else:
                try:
                    gesamtsumme = float((self.gesamt_var.get() or "0").replace(",", "."))
                except ValueError:
                    gesamtsumme = 0
                if gesamtsumme <= 0:
                    messagebox.showerror("Auftragssumme fehlt",
                                         "Bitte die Auftragssumme (gesamt) eingeben.")
                    return

        inv = {
            "number": self.db.next_invoice_number(),
            "customer_id": self.customer_map[self.customer_var.get()],
            "date": iso_date,
            "due_date": add_days(iso_date, terms),
            "payment_terms_days": terms,
            "intro_text": self.intro_var.get(),
            "tax_rate": float(self.tax_rate_var.get() or 0),
            "kleinunternehmer": int(self.kleinunternehmer_var.get()),
            "status": "open",
            "betreff": self.betreff_var.get(),
            "body_text": self.intro_var.get(),
            "invoice_type": itype,
            "parent_id": parent_id,
            "gesamtsumme": gesamtsumme,
        }
        self.db.save_invoice(inv, items)
        for r in list(self.item_rows):
            r.destroy()
        self.item_rows = []
        self._add_item_row()
        self.refresh()
        messagebox.showinfo("Erstellt", f"{TYPE_LABELS[itype]} {inv['number']} wurde erstellt.")

    # ---------- Liste ----------
    def refresh(self):
        customers = self.db.list_customers()
        self.customer_map = {f"{c['firma']} ({c.get('kundennummer','')})": c["id"] for c in customers}
        self.customer_combo["values"] = list(self.customer_map.keys())
        self._refresh_heads()

        for w in self.list_container.winfo_children():
            w.destroy()
        invoices = self.db.list_invoices()
        invoices.sort(key=lambda i: i["date"] or "", reverse=True)
        if not invoices:
            ttb.Label(self.list_container, text="Noch keine Rechnungen vorhanden.",
                       foreground=INK_SOFT, font=("Segoe UI", 9, "italic")).pack(anchor="w")
            return
        cust_by_id = {c["id"]: c for c in customers}
        for inv in invoices:
            cust = cust_by_id.get(inv["customer_id"], {})
            row = ttb.Frame(self.list_container)
            row.pack(fill="x", pady=4)
            info = ttb.Frame(row)
            info.pack(side="left", fill="x", expand=True)
            itype = inv.get("invoice_type") or "normal"
            head = inv["number"] + ("" if itype == "normal" else f"  ·  {TYPE_LABELS[itype]}")
            ttb.Label(info, text=head, font=("Consolas", 9, "bold")).pack(anchor="w")
            paid = inv["status"] == "paid"
            overdue = not paid and inv["due_date"] and inv["due_date"] < date.today().isoformat()
            status_text = "bezahlt" if paid else ("überfällig" if overdue else "offen")
            status_color = GREEN if paid else (RUST if overdue else INK_SOFT)
            ttb.Label(info, text=f"{cust.get('firma','—')} · {fmt_date(inv['date'])} · {status_text}",
                       foreground=status_color, font=("Segoe UI", 8)).pack(anchor="w")
            ttb.Label(row, text=eur(invoice_total(inv, inv["items"])), font=("Consolas", 9, "bold")).pack(side="right", padx=(6, 0))
            ttb.Button(row, text="🗑", bootstyle="link",
                        command=lambda iid=inv["id"]: self._delete(iid)).pack(side="right")

            export_mb = ttb.Menubutton(row, text="Export ▾", bootstyle="secondary-outline")
            menu = tk.Menu(export_mb, tearoff=0)
            menu.add_command(label="PDF (Vorlage-Optik)", command=lambda i=inv, c=cust: self._export_vorlage_pdf(i, c))
            menu.add_command(label="PDF (tabellarisch)", command=lambda i=inv, c=cust: self._export_pdf(i, c))
            menu.add_command(label="Word (.docx, Vorlage)", command=lambda i=inv, c=cust: self._export_word(i, c))
            menu.add_command(label="XML (E-Rechnung / Factur-X)", command=lambda i=inv, c=cust: self._export_xml(i, c))
            menu.add_command(label="ZUGFeRD (PDF mit XML)", command=lambda i=inv, c=cust: self._export_zugferd(i, c))
            export_mb["menu"] = menu
            export_mb.pack(side="right", padx=4)

            ttb.Button(row, text="✉ E-Mail", bootstyle="info-outline",
                        command=lambda i=inv, c=cust: self._email_invoice(i, c)).pack(side="right", padx=4)
            toggle_text = "Als offen markieren" if paid else "Als bezahlt markieren"
            ttb.Button(row, text=toggle_text, bootstyle="success-outline" if not paid else "secondary-outline",
                        command=lambda iid=inv["id"], s=inv["status"]: self._toggle(iid, s)).pack(side="right", padx=4)

    def _toggle(self, iid, current):
        self.db.set_invoice_status(iid, "open" if current == "paid" else "paid")
        self.refresh()

    def _delete(self, iid):
        if messagebox.askyesno("Löschen", "Diese Rechnung wirklich löschen?"):
            self.db.delete_invoice(iid)
            self.refresh()

    # ---------- Ausgaben ----------
    def _abschlag_info(self, inv):
        return compute_abschlag_info(inv, self.db.list_invoices())

    def _build_vorlage_pdf(self, inv, cust, pdf_path):
        """Füllt die Vorlage und wandelt sie in ein PDF um (Vorlage-Optik)."""
        tmp_docx = os.path.join(tempfile.gettempdir(), f"_vorlage_{inv['number']}.docx")
        template_letter.fill_template(self._template_values(inv, cust), tmp_docx)
        try:
            template_letter.convert_to_pdf(tmp_docx, pdf_path)
        finally:
            try:
                os.remove(tmp_docx)
            except OSError:
                pass
        return pdf_path

    def _export_vorlage_pdf(self, inv, cust):
        default_name = f"Rechnung_{inv['number']}.pdf"
        path = filedialog.asksaveasfilename(defaultextension=".pdf", initialfile=default_name,
                                             filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        try:
            self._build_vorlage_pdf(inv, cust, path)
            messagebox.showinfo("Erstellt", f"PDF (Vorlage-Optik) gespeichert: {os.path.basename(path)}")
        except Exception as e:
            if messagebox.askyesno("PDF aus Vorlage nicht möglich",
                                    f"{e}\n\nSoll stattdessen das tabellarische PDF-Layout erzeugt werden?"):
                try:
                    generate_invoice_pdf(path, inv, inv["items"], self.db.get_company(), cust,
                                         abschlag_info=self._abschlag_info(inv))
                    messagebox.showinfo("Erstellt", f"PDF gespeichert: {os.path.basename(path)}")
                except Exception as e2:
                    messagebox.showerror("Fehler", f"PDF konnte nicht erstellt werden:\n{e2}")

    def _export_pdf(self, inv, cust):
        default_name = f"Rechnung_{inv['number']}_Tabelle.pdf"
        path = filedialog.asksaveasfilename(defaultextension=".pdf", initialfile=default_name,
                                             filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        try:
            generate_invoice_pdf(path, inv, inv["items"], self.db.get_company(), cust,
                                 abschlag_info=self._abschlag_info(inv))
            messagebox.showinfo("Erstellt", f"PDF gespeichert: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Fehler", f"PDF konnte nicht erstellt werden:\n{e}")

    def _letter_body(self, inv, items):
        lines = [inv.get("body_text") or inv.get("intro_text") or "", ""]
        for it in items:
            amount = float(it.get("qty") or 0) * float(it.get("price") or 0)
            zr = f" ({it['zeitraum']})" if it.get("zeitraum") else ""
            lines.append(f"• {it.get('description','')}{zr}: "
                         f"{float(it.get('qty') or 0):g} {it.get('unit','')} × {eur(it.get('price',0))} = {eur(amount)}")
        lines.append("")
        net = invoice_net(items)
        total = invoice_total(inv, items)
        if not inv.get("kleinunternehmer"):
            rate = float(inv.get("tax_rate") or 0)
            lines.append(f"Nettobetrag: {eur(net)}")
            lines.append(f"MwSt. ({rate:g}%): {eur(net * rate / 100)}")
        lines.append(f"Gesamtbetrag: {eur(total)}")
        info = self._abschlag_info(inv)
        if info:
            lines.append("")
            lines.append(f"Auftragssumme gesamt: {eur(info['gesamtsumme'])}")
            if info["billed_before"]:
                lines.append(f"abzüglich bereits berechneter Abschläge: {eur(info['billed_before'])}")
            lines.append(f"verbleibender Auftragsrest: {eur(info['remaining'])}")
        lines.append("")
        lines.append(f"Zahlbar innerhalb von {inv.get('payment_terms_days','')} Tagen ab Rechnungsstellung.")
        if inv.get("kleinunternehmer"):
            lines.append("Umsatzsteuerfreie Leistung gemäß §19 UStG.")
        return "\n".join(lines)

    def _template_values(self, inv, cust):
        return {
            "name": cust.get("firma") or cust.get("ansprechpartner") or "",
            "strasse": cust.get("address_line1", ""),
            "plz_ort": cust.get("address_line2", ""),
            "datum": fmt_date(inv.get("date")),
            "betreff": inv.get("betreff") or f"Rechnung {inv.get('number','')}",
            "text": self._letter_body(inv, inv["items"]),
            "anrede": anrede(cust),
        }

    def _export_word(self, inv, cust):
        default_name = f"Anschreiben_{inv['number']}.docx"
        path = filedialog.asksaveasfilename(defaultextension=".docx", initialfile=default_name,
                                             filetypes=[("Word-Dokument", "*.docx")])
        if not path:
            return
        try:
            template_letter.fill_template(self._template_values(inv, cust), path)
            messagebox.showinfo("Erstellt", f"Word-Datei (Vorlage) gespeichert: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Fehler", f"Word-Datei konnte nicht erstellt werden:\n{e}")

    def _export_xml(self, inv, cust):
        default_name = f"Rechnung_{inv['number']}.xml"
        path = filedialog.asksaveasfilename(defaultextension=".xml", initialfile=default_name,
                                             filetypes=[("XML", "*.xml")])
        if not path:
            return
        try:
            einvoice.export_xml(path, inv, inv["items"], self.db.get_company(), cust)
            messagebox.showinfo("Erstellt", f"XML gespeichert: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Fehler", f"XML konnte nicht erstellt werden:\n{e}")

    def _export_zugferd(self, inv, cust):
        default_name = f"Rechnung_{inv['number']}_ZUGFeRD.pdf"
        path = filedialog.asksaveasfilename(defaultextension=".pdf", initialfile=default_name,
                                             filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        try:
            einvoice.export_zugferd(path, inv, inv["items"], self.db.get_company(), cust)
            messagebox.showinfo("Erstellt", f"ZUGFeRD-PDF gespeichert: {os.path.basename(path)}\n\n"
                                            "Die E-Rechnungs-XML ist in der PDF eingebettet.")
        except Exception as e:
            messagebox.showerror("Fehler", f"ZUGFeRD-Datei konnte nicht erstellt werden:\n{e}")

    def _email_invoice(self, inv, cust):
        to_addr = (cust.get("email") or "").strip()
        if not is_valid_email(to_addr):
            messagebox.showerror("Keine E-Mail",
                                 "Für diesen Kunden ist keine gültige E-Mail-Adresse hinterlegt.")
            return
        smtp = self.db.get_smtp()
        if not (smtp.get("host") or "").strip():
            messagebox.showerror("SMTP fehlt",
                                 "Bitte zuerst unter „Einstellungen“ die E-Mail-/SMTP-Zugangsdaten hinterlegen.")
            return
        if not messagebox.askyesno("E-Mail senden",
                                    f"Rechnung {inv['number']} als PDF an {to_addr} senden?"):
            return
        tmp_pdf = os.path.join(tempfile.gettempdir(), f"Rechnung_{inv['number']}.pdf")
        try:
            # bevorzugt die Vorlage-Optik; falls Word/LibreOffice fehlt, tabellarisches PDF
            try:
                self._build_vorlage_pdf(inv, cust, tmp_pdf)
            except Exception:
                generate_invoice_pdf(tmp_pdf, inv, inv["items"], self.db.get_company(), cust,
                                     abschlag_info=self._abschlag_info(inv))
            subject = (smtp.get("subject") or "Ihre Rechnung {number}").format(
                number=inv["number"], date=fmt_date(inv["date"]))
            body = (smtp.get("body") or "").format(number=inv["number"], date=fmt_date(inv["date"]))
            mailer.send_email(smtp, to_addr, subject, body, attachments=[tmp_pdf])
            messagebox.showinfo("Gesendet", f"Rechnung {inv['number']} wurde an {to_addr} gesendet.")
        except Exception as e:
            messagebox.showerror("Fehler beim Senden", f"Die E-Mail konnte nicht gesendet werden:\n{e}")
        finally:
            try:
                os.remove(tmp_pdf)
            except OSError:
                pass
