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
- [x] **Update-Check-Button** (v1.01): vergleicht lokale `VERSION` gegen `src/gui.py` auf `main` im GitHub-Repo (jetzt öffentlich, daher ohne Auth per `raw.githubusercontent.com` abrufbar)
- [x] **Spalten in der Übersichtstabelle ein-/ausblenden** (v1.01): `SpaltenAuswahlDialog`, Auswahl persistiert in `%APPDATA%\Mitgliederverwaltung\spalten_config.json`
- [x] **Suche über mehr Felder** (v1.01): zusätzlich zu Vorname/Nachname jetzt auch Mitgliedsnummer, Stadt, Telefon
- [x] **"by Dirk Heerstraß" unter der Versionsnummer** (v1.02): Label in der Seitenleiste
- [x] **SMTP-Verbindungstest beim Speichern** (v1.02): `SmtpSettingsDialog` testet vor dem Speichern per `smtplib`-Login, ob die Zugangsdaten funktionieren; bei Fehlschlag Rückfrage "Trotzdem speichern?" statt Blockade
- [x] **Excel-Mitgliederimport mit freier Spaltenzuordnung** (v1.03, angepasst v1.04): `ExcelImportDialog`, aus "Neues Mitglied" heraus aufrufbar ("Mitglieder aus Excel importieren..."). Beliebige Excel-Datei auswählen, jede Spalte per Dropdown einem internen Feld zuordnen (automatischer Vorschlag bei exakter Namensübereinstimmung, frei überschreibbar), Live-Vorschau der ersten 5 Zeilen, Datumsnormalisierung wiederverwendet `mitglieder._normalisiere_importiertes_datum()`. **Import ignoriert bewusst `validate_member()`** (seit v1.04) — Pflichtfeld-/Formatfehler (fehlende E-Mail, fehlendes Eintrittsdatum, ungültige IBAN o. ä.) blockieren den Import nicht mehr, da bestehende Vereinslisten oft unvollständig sind; nur IBAN wird bei gültigem Format kosmetisch normalisiert. Nur komplett leere Zeilen (alle zugeordneten Felder leer) werden übersprungen. Unvollständige Datensätze lassen sich später einzeln im Bearbeiten-Dialog vervollständigen. Der einfache, feste Web-App-Import (`import_members_from_excel`) wurde dadurch nicht zusätzlich portiert — die flexible Variante deckt seinen Anwendungsfall mit ab.

## Backlog / noch nicht portiert

- [ ] **Kalender**-Ansicht: Vereinstermine anlegen/löschen, `.ics`-Feed-Export
- [ ] **Terminabfrage**: Doodle-artige Ja/Nein/Vielleicht-Umfragen unter Mitgliedern
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
- [ ] **Statistik/Diagramm zur Mitgliederentwicklung**: neuer kleiner Bereich (z. B. in der Übersicht oder eigene Ansicht), Mitgliederzahl je Jahr basierend auf `Eintrittsdatum`/`Austrittsdatum` auswerten, einfaches Balken-/Liniendiagramm (z. B. `QtCharts` falls verfügbar, sonst `QPainter` oder Zusatzbibliothek wie `matplotlib` — Bibliothekswahl erst bei Umsetzung entscheiden). Praktisch für die Mitgliederversammlung.

## Hinweis zur Repo-Sichtbarkeit

Das Repo wurde am 2026-08-16 von privat auf **öffentlich** umgestellt, damit
der Update-Check-Button `src/gui.py` unauthentifiziert über
`raw.githubusercontent.com` abrufen kann (private Repos liefern dort ohne
Login `404`). Vorher per Git-Historie geprüft: es wurden nie `data/`,
`backups/` oder Konfigurationsdateien mit echten Mitgliederdaten committet —
nur Code und das öffentliche Vereinslogo. Falls sich das je ändert (z. B.
versehentlich sensible Daten committet), Repo-Historie bereinigen, bevor es
wieder privat gestellt wird — ein einfacher Sichtbarkeitswechsel entfernt
bereits geklonte/gecachte Kopien nicht rückwirkend.

## Hinweis zur Datenschicht

`mitglieder.py`/`mailer.py` sind eine Kopie aus dem Haupt-Repo
(Web-App). Sie werden **manuell** synchron gehalten — es gibt keine
automatische Synchronisation. Bei neuen Feldern/Funktionen in der Web-App
prüfen, ob sie auch hier gebraucht werden, und ggf. die Dateien erneut
1:1 kopieren plus die GUI (`src/gui.py`) entsprechend nachziehen.
