import ttkbootstrap as ttb
from tkinter import messagebox

from utils import is_valid_email, anrede

INK_SOFT = "#5B655D"

# Textfelder (zweispaltig dargestellt)
FIELDS = [
    ("kundennummer", "Kundennummer"),
    ("firma", "Firma"),
    ("ansprechpartner", "Ansprechpartner"),
    ("ust_id", "USt-IdNr"),
    ("address_line1", "Adresse Zeile 1"),
    ("address_line2", "Adresse Zeile 2 (PLZ Ort)"),
    ("email", "E-Mail"),
    ("phone", "Telefon"),
]

GENDER_OPTIONS = [("herr", "Herr"), ("frau", "Frau"), ("", "keine Angabe")]


class CustomersPage(ttb.Frame):
    def __init__(self, master, db):
        super().__init__(master, padding=18)
        self.db = db
        self.editing_id = None
        self.vars = {key: ttb.StringVar() for key, _ in FIELDS}
        self.gender_var = ttb.StringVar(value="")
        # optionaler manueller Anrede-Text (überschreibt die Automatik)
        self.salutation_var = ttb.StringVar()
        self._build()
        self.refresh()

    def _build(self):
        form_panel = ttb.Labelframe(self, text="Kunde anlegen / bearbeiten", padding=14)
        form_panel.pack(fill="x", pady=(0, 14))
        grid = ttb.Frame(form_panel)
        grid.pack(fill="x")
        grid.columnconfigure((0, 1), weight=1)
        for i, (key, label) in enumerate(FIELDS):
            r, c = divmod(i, 2)
            ttb.Label(grid, text=label).grid(row=r * 2, column=c, sticky="w", padx=4)
            ttb.Entry(grid, textvariable=self.vars[key]).grid(row=r * 2 + 1, column=c, sticky="ew", padx=4, pady=(0, 8))

        # Anrede / Geschlecht
        anrede_row = ttb.Frame(form_panel)
        anrede_row.pack(fill="x", pady=(4, 0))
        ttb.Label(anrede_row, text="Anrede:").pack(side="left")
        for value, label in GENDER_OPTIONS:
            ttb.Radiobutton(anrede_row, text=label, value=value,
                            variable=self.gender_var, command=self._update_preview).pack(side="left", padx=(10, 0))
        self.preview_label = ttb.Label(form_panel, text="", foreground=INK_SOFT, font=("Segoe UI", 8, "italic"))
        self.preview_label.pack(anchor="w", pady=(4, 0))

        ttb.Label(form_panel, text="Anrede-Text manuell überschreiben (optional)",
                  foreground=INK_SOFT, font=("Segoe UI", 8)).pack(anchor="w", pady=(6, 0))
        ent = ttb.Entry(form_panel, textvariable=self.salutation_var)
        ent.pack(fill="x")
        self.salutation_var.trace_add("write", lambda *a: self._update_preview())
        for key in ("ansprechpartner",):
            self.vars[key].trace_add("write", lambda *a: self._update_preview())

        btn_row = ttb.Frame(form_panel)
        btn_row.pack(fill="x", pady=(10, 0))
        self.save_btn = ttb.Button(btn_row, text="＋ Kunde speichern", bootstyle="dark", command=self._save)
        self.save_btn.pack(side="left")
        ttb.Button(btn_row, text="Abbrechen", bootstyle="secondary-outline",
                    command=self._reset_form).pack(side="left", padx=(8, 0))

        list_panel = ttb.Labelframe(self, text="Kunden", padding=14)
        list_panel.pack(fill="both", expand=True)
        self.list_container = ttb.Frame(list_panel)
        self.list_container.pack(fill="both", expand=True)

    def _current_customer_dict(self):
        data = {k: v.get() for k, v in self.vars.items()}
        data["gender"] = self.gender_var.get()
        data["salutation"] = self.salutation_var.get()
        return data

    def _update_preview(self):
        self.preview_label.configure(text=f"Anrede auf der Rechnung:  „{anrede(self._current_customer_dict())},“")

    def _reset_form(self):
        self.editing_id = None
        for v in self.vars.values():
            v.set("")
        self.gender_var.set("")
        self.salutation_var.set("")
        self.save_btn.configure(text="＋ Kunde speichern")
        self._update_preview()

    def _save(self):
        if not self.vars["firma"].get().strip():
            messagebox.showerror("Fehlende Angabe", "Bitte mindestens den Firmennamen eingeben.")
            return
        email = self.vars["email"].get().strip()
        if email and not is_valid_email(email):
            messagebox.showerror("Ungültige E-Mail",
                                 f"„{email}“ ist keine gültige E-Mail-Adresse.\n"
                                 "Bitte im Format name@domain.de eingeben.")
            return
        data = self._current_customer_dict()
        if self.editing_id:
            data["id"] = self.editing_id
        self.db.save_customer(data)
        self._reset_form()
        self.refresh()

    def _edit(self, customer):
        self.editing_id = customer["id"]
        for k, v in self.vars.items():
            v.set(customer.get(k, "") or "")
        self.gender_var.set(customer.get("gender", "") or "")
        self.salutation_var.set(customer.get("salutation", "") or "")
        self.save_btn.configure(text="Änderungen speichern")
        self._update_preview()

    def _delete(self, cid):
        if messagebox.askyesno("Löschen", "Diesen Kunden wirklich löschen?"):
            self.db.delete_customer(cid)
            self.refresh()

    def refresh(self):
        for w in self.list_container.winfo_children():
            w.destroy()
        customers = self.db.list_customers()
        if not customers:
            ttb.Label(self.list_container, text="Noch keine Kunden angelegt.",
                       foreground=INK_SOFT, font=("Segoe UI", 9, "italic")).pack(anchor="w")
            return
        for c in customers:
            row = ttb.Frame(self.list_container)
            row.pack(fill="x", pady=4)
            info = ttb.Frame(row)
            info.pack(side="left", fill="x", expand=True)
            ttb.Label(info, text=c["firma"] or "(ohne Firma)", font=("Segoe UI", 10, "bold")).pack(anchor="w")
            parts = [c.get("ansprechpartner"), c.get("email"), c.get("phone")]
            if c.get("ust_id"):
                parts.append(f"USt-IdNr {c['ust_id']}")
            sub = " · ".join(filter(None, parts))
            ttb.Label(info, text=sub, foreground=INK_SOFT, font=("Segoe UI", 8)).pack(anchor="w")
            ttb.Button(row, text="Bearbeiten", bootstyle="secondary-outline",
                        command=lambda cust=c: self._edit(cust)).pack(side="right", padx=(4, 0))
            ttb.Button(row, text="🗑", bootstyle="link",
                        command=lambda cid=c["id"]: self._delete(cid)).pack(side="right")
