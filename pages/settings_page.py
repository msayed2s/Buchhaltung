import os
import shutil

import ttkbootstrap as ttb
from tkinter import filedialog, messagebox

from db import app_data_dir
from utils import is_valid_email

FIELDS = [
    ("name", "Firmenname"), ("owner", "Inhaber"),
    ("ustId", "USt-IdNr (eigene)"), ("phone", "Telefon"),
    ("addressLine1", "Adresse Zeile 1"), ("addressLine2", "Adresse Zeile 2"),
    ("email", "E-Mail"), ("bankName", "Bank"),
    ("bic", "BIC"),
]

SMTP_FIELDS = [
    ("host", "SMTP-Server (Host)"), ("port", "Port"),
    ("user", "Benutzer / Login"), ("from_addr", "Absender-Adresse"),
]

ASSETS_DIR = os.path.join(app_data_dir(), "assets")
os.makedirs(ASSETS_DIR, exist_ok=True)


class SettingsPage(ttb.Frame):
    def __init__(self, master, db):
        super().__init__(master, padding=18)
        self.db = db
        company = db.get_company()
        self.vars = {key: ttb.StringVar(value=str(company.get(key, ""))) for key, _ in FIELDS}
        self.iban_var = ttb.StringVar(value=company.get("iban", ""))
        self.terms_var = ttb.StringVar(value=str(company.get("paymentTermsDays", 14)))
        self.kleinunternehmer_var = ttb.BooleanVar(value=bool(company.get("kleinunternehmer", True)))
        self.logo_path = company.get("logo", "")

        smtp = db.get_smtp()
        self.smtp_vars = {key: ttb.StringVar(value=str(smtp.get(key, ""))) for key, _ in SMTP_FIELDS}
        self.smtp_pw_var = ttb.StringVar(value=smtp.get("password", ""))
        self.smtp_tls_var = ttb.BooleanVar(value=bool(smtp.get("use_tls", True)))
        self.smtp_subject_var = ttb.StringVar(value=smtp.get("subject", ""))
        self.smtp_body_var = ttb.StringVar(value=smtp.get("body", ""))
        self._build()

    def _build(self):
        panel = ttb.Labelframe(self, text="Unternehmensdaten", padding=16)
        panel.pack(fill="x")
        ttb.Label(panel, text="Diese Angaben erscheinen auf deinen Rechnungen.",
                   foreground="#5B655D", font=("Segoe UI", 8)).pack(anchor="w", pady=(0, 10))

        logo_row = ttb.Frame(panel)
        logo_row.pack(fill="x", pady=(0, 10))
        self.logo_label = ttb.Label(logo_row, text=os.path.basename(self.logo_path) if self.logo_path else "Kein Logo")
        self.logo_label.pack(side="left")
        ttb.Button(logo_row, text="Logo hochladen", bootstyle="secondary-outline",
                    command=self._upload_logo).pack(side="left", padx=(10, 0))

        grid = ttb.Frame(panel)
        grid.pack(fill="x")
        grid.columnconfigure((0, 1), weight=1)
        for i, (key, label) in enumerate(FIELDS):
            r, c = divmod(i, 2)
            ttb.Label(grid, text=label).grid(row=r * 2, column=c, sticky="w", padx=4)
            ttb.Entry(grid, textvariable=self.vars[key]).grid(row=r * 2 + 1, column=c, sticky="ew", padx=4, pady=(0, 8))

        r = len(FIELDS) // 2 * 2 + 2
        ttb.Label(grid, text="IBAN").grid(row=r, column=0, columnspan=2, sticky="w", padx=4)
        ttb.Entry(grid, textvariable=self.iban_var).grid(row=r + 1, column=0, columnspan=2, sticky="ew", padx=4, pady=(0, 8))

        r += 2
        ttb.Label(grid, text="Standard-Zahlungsziel (Tage)").grid(row=r, column=0, sticky="w", padx=4)
        ttb.Entry(grid, textvariable=self.terms_var).grid(row=r + 1, column=0, sticky="ew", padx=4, pady=(0, 8))
        ttb.Label(grid, text="Besteuerung").grid(row=r, column=1, sticky="w", padx=4)
        ttb.Checkbutton(grid, text="Kleinunternehmer (§19 UStG)", variable=self.kleinunternehmer_var).grid(
            row=r + 1, column=1, sticky="w", padx=4, pady=(0, 8))

        # ---------- E-Mail / SMTP ----------
        smtp_panel = ttb.Labelframe(self, text="E-Mail-Versand (SMTP)", padding=16)
        smtp_panel.pack(fill="x", pady=(14, 0))
        ttb.Label(smtp_panel, text="Zugangsdaten deines E-Mail-Kontos, um Rechnungen direkt zu versenden. "
                                   "Platzhalter {number} und {date} werden in Betreff/Text ersetzt.",
                   foreground="#5B655D", font=("Segoe UI", 8), wraplength=680,
                   justify="left").pack(anchor="w", pady=(0, 10))
        sgrid = ttb.Frame(smtp_panel)
        sgrid.pack(fill="x")
        sgrid.columnconfigure((0, 1), weight=1)
        for i, (key, label) in enumerate(SMTP_FIELDS):
            r, c = divmod(i, 2)
            ttb.Label(sgrid, text=label).grid(row=r * 2, column=c, sticky="w", padx=4)
            ttb.Entry(sgrid, textvariable=self.smtp_vars[key]).grid(row=r * 2 + 1, column=c, sticky="ew", padx=4, pady=(0, 8))
        r = (len(SMTP_FIELDS) + 1) // 2 * 2
        ttb.Label(sgrid, text="Passwort").grid(row=r, column=0, sticky="w", padx=4)
        ttb.Entry(sgrid, textvariable=self.smtp_pw_var, show="•").grid(row=r + 1, column=0, sticky="ew", padx=4, pady=(0, 8))
        ttb.Checkbutton(sgrid, text="TLS-Verschlüsselung (STARTTLS)", variable=self.smtp_tls_var).grid(
            row=r + 1, column=1, sticky="w", padx=4)

        ttb.Label(smtp_panel, text="Betreff der E-Mail").pack(anchor="w", pady=(6, 0))
        ttb.Entry(smtp_panel, textvariable=self.smtp_subject_var).pack(fill="x")
        ttb.Label(smtp_panel, text="Text der E-Mail").pack(anchor="w", pady=(6, 0))
        ttb.Entry(smtp_panel, textvariable=self.smtp_body_var).pack(fill="x")

        self.saved_label = ttb.Label(self, text="", foreground="#2F6F4E", font=("Segoe UI", 9))
        self.saved_label.pack(anchor="w", pady=(10, 0))
        ttb.Button(self, text="✓ Alles speichern", bootstyle="dark", command=self._save).pack(anchor="w", pady=(8, 0))

    def _upload_logo(self):
        path = filedialog.askopenfilename(title="Logo auswählen",
                                           filetypes=[("Bilder", "*.png *.jpg *.jpeg *.gif")])
        if not path:
            return
        ext = os.path.splitext(path)[1]
        dest = os.path.join(ASSETS_DIR, f"logo{ext}")
        try:
            shutil.copy2(path, dest)
            self.logo_path = dest
            self.logo_label.configure(text=os.path.basename(dest))
        except OSError as e:
            messagebox.showerror("Fehler", str(e))

    def _save(self):
        email = self.vars["email"].get().strip()
        if email and not is_valid_email(email):
            messagebox.showerror("Ungültige E-Mail", f"„{email}“ ist keine gültige E-Mail-Adresse.")
            return
        try:
            terms = int(self.terms_var.get())
        except ValueError:
            terms = 14
        company = {key: self.vars[key].get() for key, _ in FIELDS}
        company["iban"] = self.iban_var.get()
        company["paymentTermsDays"] = terms
        company["kleinunternehmer"] = self.kleinunternehmer_var.get()
        company["logo"] = self.logo_path
        self.db.save_company(company)

        try:
            port = int(self.smtp_vars["port"].get())
        except ValueError:
            port = 587
        smtp = {key: self.smtp_vars[key].get() for key, _ in SMTP_FIELDS}
        smtp["port"] = port
        smtp["password"] = self.smtp_pw_var.get()
        smtp["use_tls"] = self.smtp_tls_var.get()
        smtp["subject"] = self.smtp_subject_var.get()
        smtp["body"] = self.smtp_body_var.get()
        self.db.save_smtp(smtp)

        self.saved_label.configure(text="Gespeichert.")
        self.after(2000, lambda: self.saved_label.configure(text=""))
