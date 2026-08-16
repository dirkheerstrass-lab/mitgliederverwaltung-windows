# Mitgliederverwaltung – Windows-Offline-App

Native Windows-Desktop-App (PyQt5) für die Vereins-Mitgliederverwaltung. Läuft
komplett lokal, ohne Server-Abhängigkeit. `mitglieder.py`/`mailer.py`
(Datenlayer: CSV-Persistenz, Validierung, Exporte, SMTP-Versand) stammen
ursprünglich aus der Streamlit-Web-App
([Mitgliederverwaltung](https://github.com/dirkheerstrass-lab/Mitgliederverwaltung))
und wurden für dieses eigenständige Repo übernommen.

**Funktionsumfang:** Mitglieder-CRUD mit allen Feldern (inkl.
Beitragsverwaltung, SEPA-Mandat, gesetzlicher Vertreter), Foto & Anhänge pro
Mitglied, Zahlungshistorie, Mail-Verlauf, vCard-/Mitgliedsausweis-/SEPA-Mandat-
Export, Excel-/PDF-Export der Liste, Geburtstags-/Jubiläumsübersicht,
Filter/Suche, Serienmail- und Beitragsmahnung-Versand per SMTP sowie
Backup/Restore.

**Aktueller Umsetzungsstand:** siehe [PLAN.md](PLAN.md) — dort steht, was
bereits umgesetzt ist und was als Backlog noch offen bleibt (Kalender,
Terminabfrage, Excel-Import, weitere PDF-Exporte, Server-Synchronisation).

---

## 📦 Installation unter Windows

### 1. Voraussetzungen

- **Python 3.9+** installiert
- **Git** (optional, für Updates)

### 2. Repository klonen

```powershell
git clone https://github.com/dirkheerstrass-lab/mitgliederverwaltung-windows
cd mitgliederverwaltung-windows
```

> Der lokale Ordnername ist frei wählbar (z. B. `Mitgliederverwaltung_Windows`)
> — passe den `cd`-Befehl dann entsprechend an. Alle folgenden Befehle in
> dieser Anleitung werden **im Repo-Root** ausgeführt (dort, wo `src/`,
> `tests/`, `build/`, `requirements.txt` direkt liegen).

### 3. Abhängigkeiten installieren

```powershell
pip install -r requirements.txt
```

### 4. App starten

```powershell
python src/main.py
```

Beim ersten Start wird automatisch `%APPDATA%\Mitgliederverwaltung\users.json`
mit einem Standard-Login angelegt:

- **Benutzername:** `admin`
- **Passwort:** `admin123`

Alternativ (nach dem Build, siehe unten):

```powershell
.\dist\Mitgliederverwaltung\Mitgliederverwaltung.exe
```

---

## 🧪 Nutzung

Nach dem Login öffnet sich das Hauptfenster mit fünf Ansichten in der Seitenleiste:

| Ansicht | Funktionen |
|---|---|
| **Übersicht** | Metriken, Geburtstage (30 Tage)/Jubiläen, Filter (Status/Gruppe/Suche), Tabelle, Doppelklick öffnet Bearbeiten-Dialog, Excel-/PDF-Export |
| **Neues Mitglied** | Formular in 3 Tabs — Persönliche Daten, Gruppen & Mitgliedschaft, Konto & SEPA (inkl. IBAN/Kontoinhaber/Mandatsreferenz) —, optional Foto + Anhänge |
| **Serienmail** | Mehrfachauswahl, Betreff/Text mit Platzhaltern (`{Vorname}` etc.), Versand per SMTP, Mail-Log je Mitglied |
| **Beitragsmahnung** | Liste fälliger Mitglieder (berechnet aus letzter Zahlung + Zahlungsrhythmus), Mahnungsversand mit Platzhaltern, „Kassierer benachrichtigen“-Sammelmail |
| **Backup** | Backup als ZIP erstellen/wiederherstellen (mit doppelter Bestätigung), automatische Sicherheits-Backups vor jedem Restore |

Der Bearbeiten-Dialog (aus der Übersicht) enthält zusätzlich: Foto
hinzufügen/löschen, Anhänge hinzufügen/öffnen/löschen, Mail-Verlauf, Zahlung
erfassen + Zahlungsverlauf, vCard-/Mitgliedsausweis-/SEPA-Mandat-Export,
Mitglied löschen (mit Bestätigung).

### Versionsnummer

`VERSION` in `src/gui.py` (unten links in der Seitenleiste angezeigt) wird bei
jedem Fix erhöht: kleine Fixes erhöhen die Nachkommastelle (z. B. 1.00 →
1.01), größere/strukturelle Änderungen die Vorkommastelle (z. B. 1.05 → 2.00,
Nachkommastelle zurück auf 00) — analog zum Muster der Web-App.

### Offline-Modus

- Die App funktioniert **vollständig offline**. Alle Daten liegen lokal unter
  `data/` (CSV + `fotos/` + `anhaenge/` + `mail_log/`, nicht versioniert).
- Der "Synchronisieren"-Menüpunkt (Phase 2) ist noch nicht angebunden.

### Serienmail / Beitragsmahnung einrichten

In der Serienmail- oder Beitragsmahnung-Ansicht über **"SMTP-Einstellungen..."**
Host, Port, Benutzer, Passwort und Absenderadresse eines bestehenden
E-Mail-Kontos hinterlegen (gespeichert lokal in
`%APPDATA%\Mitgliederverwaltung\smtp_config.json`). Für den Button „Kassierer
benachrichtigen“ in der Beitragsmahnung-Ansicht zusätzlich die
Kassierer-E-Mail-Adresse im selben Dialog eintragen.

---

## 🛠️ Build der `.exe` (für Verteilung)

### Schnellweg: `update_und_bauen.bat`

Im Repo-Ordner liegt [`update_und_bauen.bat`](update_und_bauen.bat) — einfach
per Doppelklick starten. Sie holt den neuesten Stand von GitHub
(`git pull`), installiert/aktualisiert die Abhängigkeiten und baut danach die
`.exe` neu, alles in einem Rutsch. Bei einem Fehler (z. B. `git pull`
schlägt wegen lokaler Änderungen fehl) bricht das Skript mit einer
Fehlermeldung ab, statt einfach weiterzumachen.

### Manuell, Schritt für Schritt

PyInstaller ist bereits Teil von `requirements.txt` (Schritt 3 oben) und muss
nicht separat installiert werden. Im Repo-Root ausführen:

```powershell
python -m PyInstaller build/pyinstaller.spec --noconfirm
```

> Der Aufruf über `python -m PyInstaller` (statt direkt `pyinstaller ...`) ist
> bewusst so gewählt: Falls PowerShell mit
> `Die Benennung "pyinstaller" wurde nicht als Name eines Cmdlet ... erkannt`
> abbricht, liegt das daran, dass der `Scripts`-Ordner der Python-Installation
> nicht im `PATH` liegt. `python -m PyInstaller` funktioniert davon
> unabhängig immer, solange `pip install -r requirements.txt` erfolgreich war
> (prüfbar mit `python -m pip show pyinstaller`).

Der Build dauert wegen PyQt5/pandas typischerweise **einige Minuten**. Das
Ergebnis liegt danach unter:

```
dist\Mitgliederverwaltung\Mitgliederverwaltung.exe
```

Der gesamte Ordner `dist\Mitgliederverwaltung\` (nicht nur die `.exe` allein)
wird für die Weitergabe/Verteilung benötigt — `_internal\` enthält die
mitgelieferten Abhängigkeiten (Python-Laufzeit, Qt5, pandas usw.).

**Testen:**

```powershell
.\dist\Mitgliederverwaltung\Mitgliederverwaltung.exe
```

**Hinweise:**

- Der erste Start kann spürbar langsamer sein als spätere Starts – meist weil
  Windows Defender die frisch gebaute, unsignierte `.exe` und die vielen DLLs
  in `_internal\` beim ersten Zugriff scannt. Das ist normales Verhalten bei
  PyInstaller-Builds, kein Fehler.
- `build/pyinstaller.spec` löst alle Pfade relativ zu seinem eigenen
  Speicherort auf (`SPECPATH`) – der Build funktioniert daher unabhängig
  davon, aus welchem Verzeichnis `pyinstaller` aufgerufen wird, solange der
  Pfad zur `.spec`-Datei stimmt.
- Ein Icon ist aktuell nicht eingebunden (`resources/icons/app.ico` existiert
  nicht). Sobald eines vorhanden ist, die entsprechende, auskommentierte
  Zeile in `build/pyinstaller.spec` aktivieren.

---

## 📁 Projektstruktur

```
.
├── src/
│   ├── auth.py                 # Lokale Authentifizierung (users.json in %APPDATA%)
│   ├── mitglieder_adapter.py   # Bindet mitglieder.py/mailer.py ein, eigenes data/-Verzeichnis
│   ├── gui.py                  # PyQt5-Hauptfenster + alle Ansichten/Dialoge
│   ├── main.py                 # Entry-Point (Login → MainWindow)
│   └── sync.py                 # Sync-Engine (Phase 2: Stub/Platzhalter)
├── tests/
│   └── test_mitglieder_adapter.py  # pytest-Suite für die Datenschicht
├── build/
│   └── pyinstaller.spec        # Build-Konfiguration
├── mitglieder.py                # Datenlayer (Übernahme aus der Web-App)
├── mailer.py                    # SMTP-Versand (Übernahme aus der Web-App)
├── data/                        # lokale Daten (nicht versioniert, .gitignore)
├── backups/                     # automatische Sicherheits-Backups (nicht versioniert)
├── requirements.txt
├── PLAN.md                      # Umsetzungsstand & Backlog
└── README.md
```

> **Hinweis:** `mitglieder.py`/`mailer.py` sind eine Kopie aus dem Haupt-Repo
> [Mitgliederverwaltung](https://github.com/dirkheerstrass-lab/Mitgliederverwaltung)
> (Web-App). Änderungen an der Datenschicht dort (z. B. neue Felder, neue
> Validierungsregeln) müssen bei Bedarf manuell hierher übertragen werden, da
> beide Repos bewusst unabhängig voneinander sind. Aktueller Abgleichsstand
> siehe [PLAN.md](PLAN.md).

---

## 🛠️ Entwicklung

### Tests ausführen

```powershell
pip install -r requirements.txt pytest
pytest tests/
```

Die Tests greifen über ein temporäres Datenverzeichnis auf die Datenschicht zu
und berühren nicht das lokale `data/`-Verzeichnis.

---

## 📄 Lizenz

Dieses Projekt basiert auf der Streamlit-Web-App
[Mitgliederverwaltung](https://github.com/dirkheerstrass-lab/Mitgliederverwaltung)
und wurde für die offene Nutzung unter den gleichen Bedingungen entwickelt.
