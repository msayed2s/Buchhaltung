# Buchhaltung Desktop

Eigenständige Windows-Anwendung für Buchhaltung, Rechnungen, Fahrtkosten und
eine deutsche Einkommensteuer-Schätzung (Tarif 2026) — Nachbau von
`buchhaltung_2.jsx` als lokale Desktop-App ohne Server, ohne Internet,
mit einer lokalen Datenbankdatei statt Cloud-Speicher.

## Funktionen

- **Übersicht (Dashboard):** Saldo, Einnahmen/Ausgaben, Monatschart
- **Buchungen:** Einnahmen/Ausgaben erfassen, Belege anhängen, filtern, löschen
- **Kunden:** Kundenstamm anlegen, bearbeiten, löschen
- **Rechnungen:** Rechnungen mit Positionen erstellen, als PDF exportieren
  (inkl. Firmenlogo, Kleinunternehmerregelung §19 UStG oder mit MwSt.),
  Status offen/bezahlt verwalten
- **Fahrtkosten:** Fahrten mit Kilometerpauschale erfassen, Excel-Export
  je Jahr
- **Berichte:** BWA-artige Auswertung nach Kategorien, Monatschart, offene
  Posten
- **Steuern:** Schätzung der zusätzlichen Einkommensteuer durch Gewerbe/
  Nebeneinkommen — Ehegattensplitting, Kinderfreibetrag vs. Kindergeld
  (Günstigerprüfung), Werbungskosten (Pendlerpauschale, Homeoffice-Pauschale),
  Bewirtungskosten (nur 70 % abziehbar), Steuerermäßigung §35a EStG
  (Handwerker/Haushalt/Minijob)
- **Einstellungen:** Firmendaten, Logo, IBAN, Zahlungsziel, Besteuerungsart
- **Datensicherung:** Komplett-Backup als JSON, Wiederherstellung

Alle Daten liegen lokal in einer SQLite-Datei unter
`%APPDATA%\Buchhaltung\buchhaltung.db` (Windows). Belegfotos und das Logo
werden als Dateien im selben Ordner abgelegt. Es wird keine Internetverbindung
benötigt und es werden keine Daten an Dritte gesendet.

> Hinweis: Die automatische Beleg-Erkennung per Foto (KI-Analyse über die
> Anthropic-API) aus dem Original ist in dieser Offline-Version bewusst nicht
> enthalten, da eine .exe ohne eigenen API-Schlüssel nicht sinnvoll online
> Bilder auswerten kann. Belege lassen sich stattdessen ganz normal als
> Datei an eine Buchung anhängen.

## Die .exe selbst bauen

Eine fertige .exe kann nicht plattformübergreifend aus einer Linux-Umgebung
heraus erzeugt werden — Windows-Programme müssen unter Windows gebaut werden.
Der Vorgang ist aber mit einem Doppelklick erledigt:

1. Python 3.11+ von https://python.org installieren (Haken bei "Add to PATH"
   setzen).
2. Diesen Ordner auf den Windows-PC kopieren.
3. `build_exe.bat` per Doppelklick ausführen.
4. Nach 1–2 Minuten liegt die fertige Datei unter `dist\Buchhaltung.exe` —
   diese Datei ist die eigenständige Anwendung und kann verschoben,
   umbenannt und weitergegeben werden.

## Manuell starten (ohne Build), z. B. zum Testen

```
pip install -r requirements.txt
python main.py
```

## Projektstruktur

```
main.py             Hauptfenster, Navigation
db.py                SQLite-Datenbankschicht
tax.py               Steuerberechnungen (Tarif 2026, §35a, Werbungskosten …)
pdf_invoice.py        PDF-Rechnungserstellung
excel_export.py      Excel-Export für Fahrtkosten
utils.py              Formatierung, Hilfsfunktionen
pages/                Eine Datei je Ansicht/Tab
```
