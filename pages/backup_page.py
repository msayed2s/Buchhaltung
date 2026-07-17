import json
import os
from datetime import datetime

import ttkbootstrap as ttb
from tkinter import filedialog, messagebox

from db import app_data_dir


class BackupPage(ttb.Frame):
    def __init__(self, master, db, on_restore=None):
        super().__init__(master, padding=18)
        self.db = db
        self.on_restore = on_restore
        self._build()

    def _build(self):
        panel = ttb.Labelframe(self, text="Datensicherung & Umzug", padding=16)
        panel.pack(fill="x")
        ttb.Label(panel,
                   text="Das Komplett-Backup enthält alle Buchungen, Rechnungen, Kunden und Einstellungen "
                        "als JSON-Datei. Belegfotos liegen als eigene Dateien im Anwendungsordner:\n"
                        f"{app_data_dir()}",
                   foreground="#5B655D", wraplength=640, justify="left", font=("Segoe UI", 8)).pack(anchor="w", pady=(0, 12))

        row = ttb.Frame(panel)
        row.pack(fill="x")
        ttb.Button(row, text="⬇ Komplett-Backup herunterladen", bootstyle="dark",
                    command=self._export).pack(side="left")
        ttb.Button(row, text="⬆ Backup wiederherstellen", bootstyle="secondary-outline",
                    command=self._import).pack(side="left", padx=(10, 0))
        ttb.Button(row, text="📁 Anwendungsordner öffnen", bootstyle="secondary-outline",
                    command=self._open_folder).pack(side="left", padx=(10, 0))

        self.message = ttb.Label(panel, text="", foreground="#1F2A24", font=("Segoe UI", 9))
        self.message.pack(anchor="w", pady=(10, 0))

    def _export(self):
        default_name = f"Buchhaltung_Backup_{datetime.now().strftime('%Y-%m-%d')}.json"
        path = filedialog.asksaveasfilename(defaultextension=".json", initialfile=default_name,
                                             filetypes=[("JSON", "*.json")])
        if not path:
            return
        backup = self.db.export_all()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(backup, f, ensure_ascii=False, indent=2)
        self.message.configure(
            text=f"Backup erstellt: {len(backup['transactions'])} Buchungen, "
                 f"{len(backup['invoices'])} Rechnungen, {len(backup['customers'])} Kunden.")

    def _import(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                backup = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            messagebox.showerror("Fehler", f"Die Datei konnte nicht gelesen werden:\n{e}")
            return
        if backup.get("format") != "buchhaltung-desktop":
            messagebox.showerror("Ungültiges Format", "Das ist keine gültige Backup-Datei dieser App.")
            return
        if not messagebox.askyesno("Backup wiederherstellen",
                                     "Die aktuellen Daten in der App werden dabei überschrieben. Fortfahren?"):
            return
        self.db.restore_all(backup)
        self.message.configure(text="Backup erfolgreich wiederhergestellt.")
        if self.on_restore:
            self.on_restore()

    def _open_folder(self):
        path = app_data_dir()
        if os.name == "nt":
            os.startfile(path)
        else:
            os.system(f'xdg-open "{path}"')
