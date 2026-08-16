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
- [x] **"Mitglied anzeigen"-Karte bei Einzelklick** (v1.05): `MemberViewDialog`, schreibgeschützte Profilkarte im Karten-Stil (Foto rechts mit "Profilbild hochladen"-Link, Basisdaten links: Mitgliedsnummer, Adresse, Telefon, Geburtstag inkl. berechnetem Alter, E-Mail, Mitgliedsstatus, Gruppen, Funktion). Öffnet sich bei **Einzelklick** auf eine Zeile in der Übersicht; Doppelklick öffnet weiterhin direkt den bestehenden `MemberEditDialog` (3-Tab-Formular). Einzel-/Doppelklick werden über einen `QTimer` mit dem Qt-Standard-Doppelklick-Intervall sauber getrennt (Einzelklick-Aktion wird verworfen, falls ein zweiter Klick rechtzeitig folgt). "Bearbeiten..."-Button in der Karte öffnet `MemberEditDialog` direkt aus der Anzeige heraus.
- [x] **🔴 Kritischer Bugfix: Datenverlust beim .exe-Neubau behoben** (v1.06): `DATA_DIR`/`BACKUPS_DIR` lagen bisher neben der `.exe` (`dist\Mitgliederverwaltung\data`/`backups`) — PyInstaller löscht diesen kompletten Ordner aber bei jedem Build (`COLLECT`-Schritt räumt das Zielverzeichnis komplett auf, bevor es neu befüllt wird), wodurch echte Mitgliederdaten bei jedem `.exe`-Neubau verloren gingen. Fix: Datenordner liegt jetzt fest unter `%APPDATA%\Mitgliederverwaltung\data`/`backups`, komplett außerhalb des Build-Ausgabeordners (analog zu `users.json`/`smtp_config.json`/`spalten_config.json`). Automatische einmalige Migration (`mitglieder_adapter._einmalige_datenmigration()`) verschiebt beim ersten Start alte Daten aus dem Programmordner nach `%APPDATA%`, mit Hinweis-Meldung. Zusätzlich sichert `update_und_bauen.bat` (neuer Schritt 3/4) vor dem Build vorsorglich noch vorhandene alte Daten aus `dist\Mitgliederverwaltung\` nach `%APPDATA%`, damit auch der allererste Build nach diesem Fix nichts verliert. End-to-End per Smoke-Test verifiziert: Daten bleiben auch nach komplettem Löschen des alten Programmordners (simulierter Rebuild) erhalten.
- [x] **Mitgliedsnummer-Vorschlag: kleinste freie Nummer** (v1.07): `adapter.naechste_freie_mitgliedsnummer()` findet die kleinste noch nicht vergebene positive Zahl (Lücken durch Austritte zuerst), Button "Vorschlagen" neben dem Mitgliedsnummer-Feld im "Neues Mitglied"-Formular füllt das Feld, bleibt aber frei überschreibbar.
- [x] **Sammelaktionen in der Übersicht** (v1.07): Tabelle unterstützte bereits Mehrfachauswahl (Qt-Standard `ExtendedSelection`, Strg-/Umschalt-Klick); neue Sammelaktions-Leiste unter der Tabelle mit "Status setzen für Auswahl" (Dropdown + Bestätigung) und "Ausgewählte löschen" (mit Anzahl-Bestätigung, räumt Foto/Anhänge wie beim Einzel-Löschen mit auf).
- [x] **Statistik/Diagramm zur Mitgliederentwicklung** (v1.07): `MitgliederEntwicklungWidget`, einfaches selbstgezeichnetes Balkendiagramm (`QPainter`, keine externe Chart-Bibliothek nötig) in der Übersicht, zeigt aktive Mitgliederzahl je Jahresende basierend auf Eintritts-/Austrittsdatum (`adapter.mitgliederzahl_je_jahr()`).

## Backlog / noch nicht portiert

- [ ] **Mitgliederentwicklung-Diagramm als eigener Punkt in der Seitenleiste statt in der Übersicht eingebettet**: aktuell sitzt `MitgliederEntwicklungWidget` (samt `entwicklung_box`) direkt in `UebersichtPage` (`src/gui.py`, `__init__` ca. Zeile 975-979, befüllt in `refresh_table()` über `adapter.mitgliederzahl_je_jahr()`). Gewünscht: als eigene Navigationsseite (analog zu `BeitragsmahnungPage`/`BackupPage`) mit eigenem Eintrag in `MainWindow.nav_list` (`src/gui.py`, aktuell `["Übersicht", "Neues Mitglied", "Serienmail", "Beitragsmahnung", "Backup"]`) — Übersicht wird dadurch etwas kompakter. Umsetzung: neue Klasse `MitgliederEntwicklungPage(QWidget)`, die das bestehende `MitgliederEntwicklungWidget` einbindet, in `MainWindow.__init__`/`_navigiere()`/`self.stack` wie die anderen Seiten verdrahten. Datenberechnung (`adapter.mitgliederzahl_je_jahr()`) bleibt unverändert, nur der Anzeigeort wechselt.
- [ ] **"Mitgliedschaftsjubiläen"-Box in der Übersicht durch "Nächste Zahlung fällig" ersetzen**: der Nutzer findet die Jubiläen-Liste (`jub_box`/`jubilaeen_list`, `src/gui.py:968-972` + `refresh_table()`, Zeile ~1104-1110, nutzt `mitglieder.mitgliedschaftsjubilaeen()`) nicht interessant — stattdessen soll dort eine Liste "Nächste Zahlung fällig" stehen. Design-Idee:
  - Für jedes Mitglied mit gesetztem `Letzte_Zahlung` das Fälligkeitsdatum über `mitglieder.compute_next_due()` berechnen (bereits vorhanden, genutzt u. a. in `MemberFormWidget._update_naechste_faellig()`), nach Fälligkeitsdatum aufsteigend sortieren, die nächsten N (analog zur Geburtstage-Liste, dort 30-Tage-Fenster) anzeigen — z. B. "Name — Fälligkeitsdatum (in X Tagen)" bzw. "überfällig seit X Tagen" für bereits fällige.
  - Für schon überfällige Mitglieder kann `mitglieder.faellige_mitglieder()` (bereits vorhanden, in `BeitragsmahnungPage` genutzt) als Grundlage dienen; für "als nächstes fällig, aber noch nicht überfällig" fehlt aktuell eine passende Funktion — ggf. neue kleine Hilfsfunktion in `mitglieder_adapter.py` (Windows-App-spezifisch, analog zu `mitgliederzahl_je_jahr()`), die beide Fälle (überfällig + demnächst fällig) in einer sortierten Liste zusammenführt.
  - Reine UI-Umbenennung/-Austausch in `UebersichtPage.__init__`/`refresh_table()`, kein Eingriff in die geteilte `mitglieder.py` nötig, da alle benötigten Bausteine (`compute_next_due`, `faellige_mitglieder`) dort schon existieren.
- [ ] **Mitgliedsstatus automatisch auf "gekündigt" setzen, sobald ein Austrittsdatum eingetragen wird**: aktuell passiert das in der Windows-App gar nicht (kein automatisches Setzen). Die Web-App hat bereits ein ähnliches, aber nicht identisches Muster (`streamlit_app.py:485-495`, `_status_bei_austritt_vorschlagen()`): schlägt bei **frisch gesetztem** Austrittsdatum (vorher leer, jetzt ausgefüllt) automatisch den Status **"ausgetreten"** vor — aber nur, wenn der Status nicht in derselben Aktion bewusst bereits abweichend gewählt wurde (`neuer_status == alter_status`-Prüfung, damit ein gleichzeitig manuell gesetzter Status nicht überschrieben wird). **Unterschied zum aktuellen Wunsch:** hier soll es der Status **"gekündigt"** sein, nicht "ausgetreten" (beide sind gültige, unterschiedliche Werte in `STATUS_OPTIONEN`, `mitglieder.py:68`) — bei der Umsetzung mit dem Nutzer klären, ob "gekündigt" wirklich gewünscht ist oder ob es (wie in der Web-App) "ausgetreten" sein soll, da beide im Verein unterschiedliche Bedeutung haben könnten. Umsetzungsort: `MemberFormWidget`/`MemberEditDialog._speichern()` bzw. `NeuesMitgliedPage._hinzufuegen()` (`src/gui.py`) — Logik analog zum Web-App-Muster übernehmen, nur den Zielstatus anpassen. Vorschlag bleibt änderbar (kein Zwang), damit ein bewusst anders gewählter Status nicht überschrieben wird.
- [ ] **Datumsformat überall auf dd.mm.jjjj (deutsch) statt ISO umstellen**: Die Eingabefelder (`QDateEdit` in `MemberFormWidget`/`MemberEditDialog`, Zeile ~88/209/604) zeigen bereits `dd.MM.yyyy` — intern bleibt alles wie gehabt als ISO-String (`YYYY-MM-DD`) gespeichert (`mitglieder.py`-Konvention, nicht ändern). Aber **alle Tabellen/Listen, die Datumsspalten roh aus dem DataFrame anzeigen, zeigen noch das interne ISO-Format**, da sie `QTableWidgetItem(str(wert))` direkt aus den Rohdaten befüllen, ohne Formatierung:
  - `UebersichtPage.table`, `SerienmailPage.table`, `BeitragsmahnungPage.table` (`src/gui.py`): Spalten `Geburtstag`, `Eintrittsdatum`, `Austrittsdatum`, `Einwilligung_Datum`, `Letzte_Zahlung`, `SEPA_Mandatsdatum` sowie bei Beitragsmahnung zusätzlich `Faelligkeitsdatum`.
  - `MemberEditDialog._zahlungsverlauf_aktualisieren()`: `eintrag.get('datum', '')` wird roh angezeigt.
  - Mail-Verlauf (`MemberEditDialog._mail_log_aktualisieren()`): `zeitstempel` ist ein volles Datum+Uhrzeit (ISO), müsste ebenfalls auf `dd.mm.jjjj HH:MM` umgestellt werden.
  - Bereits korrekt: `MemberViewDialog` (Geburtstag), Geburtstage-/Jubiläen-Listen in der Übersicht (`naechste_geburtstage()`/`mitgliedschaftsjubilaeen()` liefern schon `%d.%m.`-formatiert), alle `QDateEdit`-Eingabefelder, das Versionslabel/Zeitstempel in Dateinamen (keine Nutzer-Datumsanzeige, bleibt technisch/ISO).
  - Umsetzungsidee: eine gemeinsame kleine Hilfsfunktion (z. B. `_iso_zu_anzeige(wert: str) -> str`, wiederverwendet aus dem bereits vorhandenen `_iso_to_qdate()`-Muster) beim Befüllen jeder Tabellenzelle/Listenzeile für alle Datumsspalten anwenden, statt `str(wert)` direkt zu nehmen. Nicht-Datumsspalten unverändert lassen. Bei den Tabellen mit dynamischer Spaltenliste (`anzeige_spalten`) anhand des Spaltennamens erkennen, ob es eine Datumsspalte ist (gleiche `DATUMSFELDER`-Menge wie in `ExcelImportDialog`, Zeile ~1245, zentral wiederverwenden statt zu duplizieren).
  - Sortierung beachten: `QTableWidget` mit `setSortingEnabled(True)` sortiert Spalten aktuell alphabetisch nach dem angezeigten Text — ISO-Strings sortieren dabei zufällig korrekt chronologisch (YYYY-MM-DD sortiert lexikografisch = chronologisch), `dd.mm.jjjj`-Strings **nicht** (würden alphabetisch nach Tag sortieren, nicht nach Datum)! Für korrekte Sortierung nach der Umstellung entweder `QTableWidgetItem` mit einem numerischen/ISO-Sortierschlüssel via `setData(Qt.UserRole, ...)` + `Qt.DisplayRole` getrennt von Sortierrolle versehen, oder eine eigene sortierbare Subklasse verwenden — sonst brechen Tabellen mit sortierbaren Datumsspalten nach der Formatumstellung.

- [ ] **E-Mail beim Bearbeiten optional**: `mitglieder.validate_member()` (`mitglieder.py:259-263`) verlangt aktuell immer eine ausgefüllte, gültige E-Mail-Adresse — auch beim Bearbeiten eines bereits bestehenden Mitglieds. Gewünscht: beim Bearbeiten (`MemberEditDialog._speichern()`, `src/gui.py`) darf das Feld leer bleiben (z. B. ältere Mitglieder ohne hinterlegte E-Mail, oder bewusstes Entfernen). Nur bei "Neues Mitglied" bleibt sie Pflicht (aktuelles Verhalten unverändert). Da `validate_member()` in der geteilten `mitglieder.py` liegt (manuell synchron gehaltene Kopie aus dem Haupt-Repo, siehe Hinweis unten) und dort für die Web-App weiterhin verpflichtend bleiben soll, am ehesten ohne Änderung an `mitglieder.py` lösen: in `MemberEditDialog._speichern()` die von `validate_member()` zurückgegebene "E-Mail darf nicht leer sein."-Fehlermeldung gezielt herausfiltern, wenn das E-Mail-Feld leer ist (die "ungültige E-Mail-Adresse"-Prüfung bei tatsächlich eingetragenem, aber falsch formatiertem Text bleibt bestehen). Auswirkung auf Serienmail/Beitragsmahnung beachten: Mitglieder ohne E-Mail werden dort schon jetzt korrekt übersprungen (`if not empfaenger: raise ValueError(...)`, vorhandene Fehlerbehandlung greift bereits).
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

Alle drei geplanten Komfort-Punkte wurden in v1.07 umgesetzt (siehe "Umgesetzt" oben) — dieser Abschnitt ist aktuell leer.

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
