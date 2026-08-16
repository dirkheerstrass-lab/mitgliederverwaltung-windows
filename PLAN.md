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
- [ ] **Excel-Mitgliederimport**: Massenimport im „Neues Mitglied“-Formular der Web-App (`import_members_from_excel`, `build_import_vorlage`)
- [ ] Weitere PDF-Exporte: Beitrittserklärung, Austrittsbestätigung, Aufnahmeantrag (Letzterer benötigt zusätzlich `vorlagen/aufnahmeantrag_vorlage.pdf` — noch nicht in dieses Repo kopiert)
- [ ] Server-Synchronisation (Phase 2, `src/sync.py` ist bewusst nur ein Platzhalter)
- [ ] Richtiger Installer/Setup.exe (z. B. Inno Setup oder NSIS), der den `dist/Mitgliederverwaltung/`-Ordner für Endnutzer verpackt/installiert. Der Build ist bewusst als "onedir" mit vielen losen Dateien in `_internal/` gehalten (schnellerer Start als eine kompakt gepackte `.exe`) — ein Installer soll das später für Endnutzer unsichtbar machen.
- [ ] SMTP-Einstellungen (`SmtpSettingsDialog`, `src/gui.py`): beim Speichern einmal die Verbindung testen (z. B. `smtplib`-Login mit den eingegebenen Zugangsdaten versuchen), statt Fehler erst beim nächsten Serienmail-/Beitragsmahnung-Versand zu bemerken. Bei Fehlschlag Meldung anzeigen, Speichern aber trotzdem erlauben (falls z. B. gerade kein Internet verfügbar ist).

## Hinweis zur Datenschicht

`mitglieder.py`/`mailer.py` sind eine Kopie aus dem Haupt-Repo
(Web-App). Sie werden **manuell** synchron gehalten — es gibt keine
automatische Synchronisation. Bei neuen Feldern/Funktionen in der Web-App
prüfen, ob sie auch hier gebraucht werden, und ggf. die Dateien erneut
1:1 kopieren plus die GUI (`src/gui.py`) entsprechend nachziehen.
