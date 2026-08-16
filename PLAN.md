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

### Sicherheit

- [ ] **Passwort ändern**: neuer Menüpunkt/Dialog "Passwort ändern" (analog `SmtpSettingsDialog`), nutzt vorhandene `auth.py`-Funktionen (`get_users`, `save_users`, `hash_password`). Aktuelles Passwort zur Bestätigung abfragen. Aktuell gibt es keine Möglichkeit, das Login-Passwort in der App zu ändern — bleibt sonst dauerhaft `admin123`.
- [ ] **Backups verschlüsseln**: Backup-ZIP enthält IBAN/Adressen/Fotos im Klartext. Beim "Backup erstellen" optional ein Passwort abfragen und das ZIP damit verschlüsseln (z. B. `pyzipper` für echte AES-Verschlüsselung, da Python-Standard-`zipfile` das nicht kann). Beim Restore entsprechend Passwort abfragen. Mindestens: deutlicher Warnhinweis im Backup-Dialog, dass die Datei sensible Daten unverschlüsselt enthält, falls Verschlüsselung nicht sofort umgesetzt wird — relevant, da Backups laut Beschluss oben (Server-Synchronisation verworfen) der vorgesehene Weg für gelegentlichen Datenaustausch mit anderen Vorstandsmitgliedern sind (z. B. per Mail).

### Komfort / Alltagstauglichkeit

- [ ] **Mitgliedsnummer-Vergabe: kleinste freie Nummer statt höchste+1**: neue Hilfsfunktion, die vorhandene `Mitgliedsnummer`-Werte aus `df["Mitgliedsnummer"]` einsammelt (nur numerische), als Menge behandelt und die kleinste positive ganze Zahl findet, die **nicht** enthalten ist (löst also zuerst Lücken durch ausgetretene/gelöschte Mitglieder, erst danach die nächsthöhere Zahl). Als Vorschlag im "Neues Mitglied"-Formular anzeigen (Button "Vorschlagen" neben dem Mitgliedsnummer-Feld), nicht automatisch fest eintragen — frei überschreibbar.
- [ ] **Sammelaktionen in der Übersicht**: `UebersichtPage`-Tabelle auf Mehrfachauswahl umstellen (aktuell nur Einzelauswahl fürs Bearbeiten). Sammel-Buttons z. B. "Status setzen für Auswahl", "Ausgewählte löschen" (mit derselben Bestätigungslogik wie Einzel-Löschen).
- [ ] **Spalten in der Übersichtstabelle ein-/ausblenden**: Kontextmenü oder kleines Einstellungs-Icon über der Tabelle, das die Sichtbarkeit einzelner Spalten umschaltet (`QTableWidget.setColumnHidden`), Auswahl ggf. persistent speichern (z. B. in `%APPDATA%` analog `smtp_config.json`). 28 Spalten sind aktuell sehr breit/unübersichtlich.
- [ ] **Suche über mehr Felder**: `suche_edit` in `UebersichtPage` aktuell nur gegen Vorname/Nachname (`str.contains`). Erweitern auf Mitgliedsnummer, Stadt, Telefon (mehrere `str.contains`-Bedingungen mit ODER verknüpft, analog bestehendem Muster).
- [ ] **Statistik/Diagramm zur Mitgliederentwicklung**: neuer kleiner Bereich (z. B. in der Übersicht oder eigene Ansicht), Mitgliederzahl je Jahr basierend auf `Eintrittsdatum`/`Austrittsdatum` auswerten, einfaches Balken-/Liniendiagramm (z. B. `QtCharts` falls verfügbar, sonst `QPainter` oder Zusatzbibliothek wie `matplotlib` — Bibliothekswahl erst bei Umsetzung entscheiden). Praktisch für die Mitgliederversammlung.
- [ ] **Update-Check-Button in der App**: Button/Menüpunkt "Nach Updates suchen", vergleicht lokale `VERSION`-Konstante (`src/gui.py`) mit dem aktuellen `VERSION`-Wert direkt in `src/gui.py` auf `main` im GitHub-Repo (z. B. via GitHub-API `/repos/.../contents/src/gui.py` oder `raw.githubusercontent.com`-Abruf, Wert per Regex extrahieren — kein Release-/Tag-Mechanismus nötig, da `VERSION` laut gelebter Konvention bei jeder Repo-Änderung hochgezählt wird). Zeigt Hinweis, falls die Remote-Version höher ist als die lokale, mit Anleitung "`update_und_bauen.bat` ausführen".

## Hinweis zur Datenschicht

`mitglieder.py`/`mailer.py` sind eine Kopie aus dem Haupt-Repo
(Web-App). Sie werden **manuell** synchron gehalten — es gibt keine
automatische Synchronisation. Bei neuen Feldern/Funktionen in der Web-App
prüfen, ob sie auch hier gebraucht werden, und ggf. die Dateien erneut
1:1 kopieren plus die GUI (`src/gui.py`) entsprechend nachziehen.
