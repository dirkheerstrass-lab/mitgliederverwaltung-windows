# Umsetzungsstand & Roadmap

Diese Datei hält fest, welcher Funktionsumfang der Streamlit-Web-App
([Mitgliederverwaltung](https://github.com/dirkheerstrass-lab/Mitgliederverwaltung))
bereits in diese native Windows-App portiert wurde und was als Backlog noch
offen ist — damit künftige Arbeitssessions den Stand auf einen Blick sehen,
ohne beide Repos neu abzugleichen.

## Umgesetzt

- [x] Übersicht: Metriken, Geburtstage/Jubiläen, Filter (Status/Gruppe/Suche), Tabelle, Excel-/PDF-Export
- [x] Neues Mitglied / Bearbeiten in **3 Tabs** (analog zur Web-App): „Persönliche Daten“, „Gruppen & Mitgliedschaft“, „Konto & SEPA“
- [x] SEPA-Mandat: IBAN (mit Prüfziffer-Validierung), Kontoinhaber, Mandatsreferenz, Mandatsdatum + PDF-Export
- [x] Beitragsverwaltung: Zahlungsrhythmus, Beitragsbetrag, berechnete nächste Fälligkeit
- [x] Zahlungshistorie: „Zahlung erfassen“ + Zahlungsverlauf im Bearbeiten-Dialog
- [x] Foto & Anhänge pro Mitglied (hinzufügen/anzeigen/löschen)
- [x] Mail-Verlauf pro Mitglied
- [x] vCard- und Mitgliedsausweis-Export
- [x] Mitglied löschen (mit Bestätigung, räumt Foto/Anhänge/Logs auf)
- [x] Serienmail: Mehrfachauswahl, Platzhalter, SMTP-Versand, PDF-Anhang optional
- [x] **Beitragsmahnung**: Liste fälliger Mitglieder, Mahnungsversand (gemeinsamer Versand-Mechanismus mit Serienmail), „Kassierer benachrichtigen“-Sammelmail
- [x] **Backup/Restore**: Backup als ZIP erstellen, Wiederherstellen (mit doppelter Bestätigung inkl. Bestätigungstext-Eingabe), automatische Sicherheits-Backups vor jedem Restore mit Einzel-Download
- [x] Lokale Authentifizierung (users.json in %APPDATA%)
- [x] Windows-.exe-Build via PyInstaller

## Backlog / noch nicht portiert

- [ ] **Kalender**-Ansicht: Vereinstermine anlegen/löschen, `.ics`-Feed-Export
- [ ] **Terminabfrage**: Doodle-artige Ja/Nein/Vielleicht-Umfragen unter Mitgliedern
- [ ] **Excel-Mitgliederimport (einfach, Web-App-Portierung)**: Massenimport wie im „Neues Mitglied“-Formular der Web-App (`import_members_from_excel`, `build_import_vorlage`, `mitglieder.py:609-634`) — erwartet zwingend eine Kopfzeile, die (eine Teilmenge der) internen Spaltennamen aus `COLUMNS` **exakt** trifft; unbekannte Spaltenüberschriften werden ignoriert, keine Zuordnungsmöglichkeit.
- [ ] **Excel-Mitgliederimport (mit freier Spaltenzuordnung)**: eigenständige, umfangreichere Variante — Nutzer wählt eine beliebige Excel-Datei mit **eigener** Spaltenbeschriftung, ordnet in der App selbst jede Spalte einem internen Feld zu (statt feste Kopfzeile vorauszusetzen). Sinnvoll für bestehende Vereinslisten mit gewachsenen, abweichenden Spaltennamen. Design-Skizze:
  - Neuer Dialog/Ansicht "Mitglieder aus Excel importieren": (1) Datei auswählen, erste Zeile als Spaltenüberschriften einlesen (`pandas.read_excel`, wie in `import_members_from_excel()` bereits vorgemacht); (2) Zuordnungs-Formular — für jedes Feld aus `mitglieder.COLUMNS` (außer `ID`) ein Dropdown mit den gefundenen Spaltenüberschriften (+ "— nicht zuordnen —"), Vorschläge bei ähnlichem Namen vorbelegt, frei überschreibbar; (3) Vorschau der ersten Zeilen nach angewandter Zuordnung; (4) Import mit `validate_member()`-Prüfung pro Zeile (kein Alles-oder-Nichts, Ergebnis "N erfolgreich / N Fehler mit Zeilennummer"); (5) Datumsfelder ggf. über eine an `_normalisiere_importiertes_datum()` (`mitglieder.py`) angelehnte Normalisierung.
  - Reine GUI-/Windows-App-Logik (`src/gui.py` oder neues `src/excel_import.py`), kein Eingriff in die geteilte `mitglieder.py` nötig — nur `validate_member()`/`add_member()` werden wiederverwendet.
- [ ] Weitere PDF-Exporte: Beitrittserklärung, Austrittsbestätigung, Aufnahmeantrag (Letzterer benötigt zusätzlich `vorlagen/aufnahmeantrag_vorlage.pdf` — noch nicht in dieses Repo kopiert)
- ~~Server-Synchronisation (Phase 2)~~ — **bewusst verworfen** (2026-08-16):
  Nur eine Person (Dirk) pflegt die Mitgliederdaten, es gibt keinen
  Mehrbenutzer-Bedarf mit gleichzeitigem Zugriff. Eine Online-/Server-
  Architektur (zentrale API auf dem vorhandenen vServer, Windows-App als
  Client) würde dafür unnötige Komplexität bedeuten (API-Bau, Auth pro
  Nutzer, Konfliktbehandlung bei gleichzeitigem Schreiben). Die bereits
  vorhandene **Backup/Restore-Funktion** deckt den eigentlichen Bedarf
  (Sicherung, gelegentlicher Austausch mit anderen Vorstandsmitgliedern per
  ZIP-Datei) bereits vollständig ab. `src/sync.py` bleibt daher dauerhaft nur
  ein unbenutzter Platzhalter — falls sich der Bedarf ändert (z. B. mehrere
  Personen sollen künftig gleichzeitig live arbeiten), diese Entscheidung neu
  bewerten.
- [ ] Richtiger Installer/Setup.exe (z. B. Inno Setup oder NSIS), der den `dist/Mitgliederverwaltung/`-Ordner für Endnutzer verpackt/installiert. Der Build ist bewusst als "onedir" mit vielen losen Dateien in `_internal/` gehalten (schnellerer Start als eine kompakt gepackte `.exe`) — ein Installer soll das später für Endnutzer unsichtbar machen.
- [ ] SMTP-Einstellungen (`SmtpSettingsDialog`, `src/gui.py`): beim Speichern einmal die Verbindung testen (z. B. `smtplib`-Login mit den eingegebenen Zugangsdaten versuchen), statt Fehler erst beim nächsten Serienmail-/Beitragsmahnung-Versand zu bemerken. Bei Fehlschlag Meldung anzeigen, Speichern aber trotzdem erlauben (falls z. B. gerade kein Internet verfügbar ist).
- [ ] Unter der Versionsnummer in der Seitenleiste (`version_label`, `src/gui.py`, `MainWindow.__init__`) zusätzlich „by Dirk Heerstraß“ anzeigen.
- [ ] **Automatisches Start-Backup (zeitgesteuert)**: bisher gibt es nur ein "automatisches" Backup als Sicherheitsnetz unmittelbar vor einem manuellen Restore (`vor_restore_*.zip`) — kein periodisches Backup, das von selbst ohne Zutun entsteht. Gewünscht: bei jedem App-Start automatisch ein Backup anlegen, höchstens einmal pro Kalendertag (verhindert Spam bei mehrfachem Neustart am selben Tag). Design:
  - Auslöser: nach erfolgreichem Login, vor `window.show()` in `src/main.py`. Kein Hintergrund-Scheduler nötig, App läuft nur bei aktiver Nutzung.
  - Speicherort: `mitglieder.BACKUPS_DIR` (wie Restore-Sicherheitsbackups), aber eigenes Dateinamens-Präfix `auto_start_JJJJMMTT_HHMMSS.zip`, damit sich beide Arten nicht gegenseitig bei der Aufräumlogik beeinflussen.
  - Aufräumen: neueste 7 automatische Start-Backups behalten, älter automatisch löschen (eigener Zähler, unabhängig von der bestehenden Restore-Sicherheitsbackup-Aufräumlogik in `mitglieder.py`).
  - Neue Funktion `erstelle_start_backup_falls_noetig() -> Path | None` in `src/mitglieder_adapter.py` (nicht in `mitglieder.py`, da Windows-App-spezifisch und `mitglieder.py`/`mailer.py` nur manuell synchron gehaltene Kopien aus dem Haupt-Repo sind) — nutzt nur die bereits vorhandene `mitglieder.build_backup_zip()`. Fehler beim Backup (z. B. Schreibrechte) dürfen den App-Start nie blockieren, nur loggen/überspringen.
  - `BackupPage` (`src/gui.py`): neue Sektion "Automatische Start-Backups" (eigene Liste, analog zur bestehenden Restore-Sicherheitsbackup-Sektion) mit Einzel-Download.

## Hinweis zur Datenschicht

`mitglieder.py`/`mailer.py` sind eine Kopie aus dem Haupt-Repo
(Web-App). Sie werden **manuell** synchron gehalten — es gibt keine
automatische Synchronisation. Bei neuen Feldern/Funktionen in der Web-App
prüfen, ob sie auch hier gebraucht werden, und ggf. die Dateien erneut
1:1 kopieren plus die GUI (`src/gui.py`) entsprechend nachziehen.
