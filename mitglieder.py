"""Datenlayer der Mitgliederverwaltung: CSV-Persistenz, CRUD, Validierung, Fotos/Anhänge, Exporte.

Enthält keine Streamlit-Aufrufe (kein `st.*`) — UI-Feedback bleibt vollständig in streamlit_app.py.
"""
from __future__ import annotations

import calendar
import io
import json
import re
import shutil
import uuid
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
from fpdf import FPDF
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas as reportlab_canvas

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CSV_PATH = DATA_DIR / "mitglieder.csv"
FOTOS_DIR = DATA_DIR / "fotos"
ANHAENGE_DIR = DATA_DIR / "anhaenge"
MAIL_LOG_DIR = DATA_DIR / "mail_log"
ZAHLUNGEN_DIR = DATA_DIR / "zahlungen"
VORLAGEN_DIR = BASE_DIR / "vorlagen"
AUFNAHMEANTRAG_VORLAGE = VORLAGEN_DIR / "aufnahmeantrag_vorlage.pdf"
LOGO_PFAD = VORLAGEN_DIR / "logo.jpg"

# Erlaubte Dateiendungen und maximale Dateigröße für Mitglieder-Anhänge.
ANHANG_ERLAUBTE_ENDUNGEN = {".pdf", ".jpg", ".jpeg", ".png", ".docx", ".doc", ".txt"}
ANHANG_MAX_GROESSE_BYTES = 10 * 1024 * 1024  # 10 MB

# Vereinsname für vCard, Mitgliedsausweis und weitere Dokumente; leer lassen, um das Feld wegzulassen
VEREINSNAME = "1. Dart Club 1990 Erkelenz e.V."

# Gläubiger-Identifikationsnummer für SEPA-Mandate (bei der Bundesbank zu
# beantragen, Format z. B. "DE98ZZZ09999999999"); leer lassen, um im
# SEPA-Mandatsformular eine Leerstelle zum handschriftlichen Ausfüllen zu zeigen.
GLAEUBIGER_ID = ""

COLUMNS = [
    "ID", "Mitgliedsnummer", "Anrede", "Vorname", "Nachname", "E-Mail",
    "Telefon", "Straße", "PLZ", "Stadt", "Geburtstag", "Eintrittsdatum",
    "Austrittsdatum", "Gruppen", "Mitgliedsstatus", "DKV-Nummer",
    "NWDV-Nummer", "Game-Shot-Nummer", "Funktion",
    "Einwilligung_Fotos_Daten", "Einwilligung_Datum",
    "Vertreter_Name", "Vertreter_Telefon", "Vertreter_E-Mail", "Notizen",
    "Zahlungsrhythmus", "Beitragsbetrag", "Letzte_Zahlung",
    "IBAN", "Kontoinhaber", "SEPA_Mandatsreferenz", "SEPA_Mandatsdatum",
]

ZAHLUNGSRHYTHMUS_OPTIONEN = ["monatlich", "quartalsweise", "halbjährlich", "jährlich"]
_RHYTHMUS_MONATE = {"monatlich": 1, "quartalsweise": 3, "halbjährlich": 6, "jährlich": 12}

ZAHLUNGSART_OPTIONEN = ["Überweisung", "Lastschrift", "Bar", "Sonstiges"]

GRUPPEN_OPTIONEN = [
    "Aktive Mitglieder", "Fördernde Mitglieder", "Ehrenmitglied", "Jugend",
    "Schlüsselträger", "DKV Team 1", "DKV Team 2", "DKV Team 3",
    "DKV Team 4", "DKV Team 5", "NWDV 1",
]

ANREDE_OPTIONEN = ["", "Herr", "Frau", "Divers"]
STATUS_OPTIONEN = ["aktiv", "passiv", "inaktiv", "gekündigt", "ausgetreten"]

# Streamlits date_input begrenzt den Datumsbereich standardmäßig auf ca. +/-10 Jahre
# um heute - das reicht für Geburtstage/Eintrittsdaten von Vereinsmitgliedern nicht aus.
MIN_DATUM = date(1900, 1, 1)
MAX_DATUM = date(2100, 12, 31)
JUBILAEUMS_MEILENSTEINE = {5, 10, 15, 20, 25, 30, 35, 40, 45, 50}

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
IBAN_REGEX = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z0-9]{10,30}$")

PDF_LISTE_SPALTEN = ["Mitgliedsnummer", "Name", "E-Mail", "Telefon", "Stadt", "Mitgliedsstatus", "Gruppen"]


# --- Laden / Speichern ---

def load_data() -> pd.DataFrame:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not CSV_PATH.exists():
        df = pd.DataFrame(columns=COLUMNS)
        save_data(df)
        return df
    df = pd.read_csv(CSV_PATH, dtype=str, keep_default_na=False)
    for spalte in COLUMNS:
        if spalte not in df.columns:
            df[spalte] = ""
    return df[COLUMNS]


def save_data(df: pd.DataFrame) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(CSV_PATH, index=False)


# --- Backup / Restore ---

BACKUPS_DIR = BASE_DIR / "backups"


def build_backup_zip() -> bytes:
    """Packt den kompletten data/-Ordner (CSV, Fotos, Anhänge, Mail-Log) in
    ein ZIP-Archiv im Speicher, zum Download über die Weboberfläche."""
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w", zipfile.ZIP_DEFLATED) as zf:
        if DATA_DIR.exists():
            for pfad in DATA_DIR.rglob("*"):
                if pfad.is_file():
                    zf.write(pfad, arcname=pfad.relative_to(DATA_DIR.parent))
    return puffer.getvalue()


class UngueltigesBackup(Exception):
    """Wird ausgelöst, wenn eine hochgeladene Backup-Datei kein gültiges,
    von dieser App erzeugtes Backup ist (z. B. falsches Dateiformat oder
    fehlende mitglieder.csv)."""


def restore_from_backup(zip_bytes: bytes) -> None:
    """Ersetzt den kompletten data/-Ordner durch den Inhalt eines zuvor mit
    build_backup_zip() erzeugten Backups. Legt vorher automatisch ein
    Sicherheits-Backup des aktuellen Standes in backups/ an, damit ein
    versehentliches Wiederherstellen nicht endgültig Daten vernichtet.

    Wirft UngueltigesBackup, wenn die Datei kein gültiges ZIP ist oder keine
    mitglieder.csv enthält - der aktuelle Datenbestand bleibt in diesem Fall
    unangetastet.
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as exc:
        raise UngueltigesBackup("Die hochgeladene Datei ist kein gültiges ZIP-Archiv.") from exc

    namen = zf.namelist()
    if not any(name.endswith("data/mitglieder.csv") for name in namen):
        raise UngueltigesBackup(
            "Das Backup enthält keine mitglieder.csv - vermutlich kein gültiges Backup dieser App."
        )

    # Schutz vor "Zip Slip": verhindert, dass ein präpariertes Archiv über
    # Pfade wie "../../etc/irgendwas" Dateien außerhalb von DATA_DIR.parent
    # schreibt. Jeder Eintrag muss nach der Auflösung innerhalb des Zielordners
    # landen, sonst wird das gesamte Backup abgelehnt.
    ziel_basis = DATA_DIR.parent.resolve()
    for name in namen:
        aufgeloest = (ziel_basis / name).resolve()
        if aufgeloest != ziel_basis and ziel_basis not in aufgeloest.parents:
            raise UngueltigesBackup(
                f"Das Backup enthält einen unzulässigen Pfad ({name}) und wird aus Sicherheitsgründen abgelehnt."
            )

    # Sicherheits-Backup des aktuellen Standes, bevor irgendetwas überschrieben wird.
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    zeitstempel = datetime.now().strftime("%Y%m%d_%H%M%S")
    (BACKUPS_DIR / f"vor_restore_{zeitstempel}.zip").write_bytes(build_backup_zip())
    _sicherheitsbackups_aufraeumen()

    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)
    zf.extractall(DATA_DIR.parent)


MAX_SICHERHEITSBACKUPS = 5


def _sicherheitsbackups_aufraeumen() -> None:
    """Behält nur die MAX_SICHERHEITSBACKUPS neuesten automatischen
    Sicherheits-Backups, damit wiederholte Restores nicht unbegrenzt
    Speicherplatz belegen (jedes Backup enthält Fotos/Anhänge aller
    Mitglieder und kann entsprechend groß werden)."""
    alte_backups = list_sicherheits_backups()[MAX_SICHERHEITSBACKUPS:]
    for pfad in alte_backups:
        pfad.unlink()


def list_sicherheits_backups() -> list[Path]:
    """Liefert alle automatisch vor einem Restore angelegten Sicherheits-Backups,
    neueste zuerst."""
    if not BACKUPS_DIR.exists():
        return []
    return sorted(BACKUPS_DIR.glob("vor_restore_*.zip"), reverse=True)


# --- Hilfsfunktionen ---

def is_valid_email(email: str) -> bool:
    return bool(email) and bool(EMAIL_REGEX.match(email.strip()))


def normalize_iban(iban: str) -> str:
    """Entfernt jegliche Whitespace-Zeichen (auch geschuetzte Leerzeichen, wie
    beim Kopieren aus Bank-PDFs/Kontoauszuegen ueblich) und normalisiert auf
    Grossbuchstaben, damit IBANs einheitlich gespeichert werden."""
    return re.sub(r"\s+", "", iban).upper()


def is_valid_iban(iban: str) -> bool:
    """Prüft eine IBAN auf gültiges Format und korrekte Prüfziffer
    (ISO 7064 MOD 97-10, der Standard-IBAN-Prüfalgorithmus)."""
    bereinigt = normalize_iban(iban)
    if not IBAN_REGEX.fullmatch(bereinigt):
        return False
    umgestellt = bereinigt[4:] + bereinigt[:4]
    ziffern = "".join(str(int(z, 36)) for z in umgestellt)
    return int(ziffern) % 97 == 1


def parse_datum(text: str) -> date | None:
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def compute_next_due(letzte_zahlung: str, rhythmus: str) -> str:
    """Berechnet das Fälligkeitsdatum der nächsten Beitragszahlung aus dem
    Datum der letzten Zahlung und dem Zahlungsrhythmus. Gibt "" zurück, wenn
    kein Datum der letzten Zahlung vorliegt."""
    letzte = parse_datum(letzte_zahlung)
    if letzte is None:
        return ""
    monate = _RHYTHMUS_MONATE.get(rhythmus, 1)
    monat_index = letzte.month - 1 + monate
    jahr = letzte.year + monat_index // 12
    monat = monat_index % 12 + 1
    tag = min(letzte.day, calendar.monthrange(jahr, monat)[1])
    return date(jahr, monat, tag).isoformat()


def berechne_alter(geburtstag: str) -> int | None:
    geb = parse_datum(geburtstag)
    if geb is None:
        return None
    heute = date.today()
    return heute.year - geb.year - ((heute.month, heute.day) < (geb.month, geb.day))


def ist_minderjaehrig(geburtstag: str) -> bool:
    alter = berechne_alter(geburtstag)
    return alter is None or alter < 18


# --- Validierung ---

def validate_member(data: dict, df: pd.DataFrame, editing_id: str | None = None) -> list[str]:
    fehler = []
    if not data.get("Vorname", "").strip():
        fehler.append("Vorname darf nicht leer sein.")
    if not data.get("Nachname", "").strip():
        fehler.append("Nachname darf nicht leer sein.")
    email = data.get("E-Mail", "").strip()
    if not email:
        fehler.append("E-Mail darf nicht leer sein.")
    elif not is_valid_email(email):
        fehler.append("Bitte eine gültige E-Mail-Adresse eingeben.")
    if not data.get("Eintrittsdatum", "").strip():
        fehler.append("Eintrittsdatum darf nicht leer sein.")
    if data.get("Mitgliedsstatus") not in STATUS_OPTIONEN:
        fehler.append(f"Mitgliedsstatus muss einer von {', '.join(STATUS_OPTIONEN)} sein.")

    iban = data.get("IBAN", "").strip()
    if iban:
        if not is_valid_iban(iban):
            fehler.append("Bitte eine gültige IBAN eingeben.")
        else:
            # Normalisierte Form speichern (keine Leerzeichen, Großbuchstaben),
            # damit die IBAN einheitlich in der CSV landet statt in der
            # jeweiligen Schreibweise, die das Mitglied eingegeben hat.
            data["IBAN"] = normalize_iban(iban)

    nummer = data.get("Mitgliedsnummer", "").strip()
    if nummer:
        vorhandene = df[df["ID"] != editing_id] if editing_id else df
        if (vorhandene["Mitgliedsnummer"].astype(str).str.strip() == nummer).any():
            fehler.append(f"Diese Mitgliedsnummer ist bereits vergeben: {nummer}")

    return fehler


# --- CRUD ---

def add_member(df: pd.DataFrame, data: dict) -> pd.DataFrame:
    neue_zeile = {spalte: data.get(spalte, "") for spalte in COLUMNS}
    neue_zeile["ID"] = str(uuid.uuid4())
    neuer_df = pd.concat([df, pd.DataFrame([neue_zeile])], ignore_index=True)
    return neuer_df[COLUMNS]


def update_member(df: pd.DataFrame, mitglied_id: str, data: dict) -> pd.DataFrame:
    df = df.copy()
    idx = df.index[df["ID"] == mitglied_id]
    for spalte in COLUMNS:
        if spalte == "ID" or spalte not in data:
            continue
        df.loc[idx, spalte] = data[spalte]
    return df


def delete_member(df: pd.DataFrame, mitglied_id: str) -> pd.DataFrame:
    delete_photo(mitglied_id)
    delete_all_attachments(mitglied_id)
    delete_mail_log(mitglied_id)
    delete_zahlungslog(mitglied_id)
    return df[df["ID"] != mitglied_id].reset_index(drop=True)


# --- Kennzahlen / Übersicht ---

def status_anzahl(df: pd.DataFrame) -> dict[str, int]:
    """Anzahl Mitglieder je Status, für die Zahlenkacheln auf der Übersicht."""
    return {status: int((df["Mitgliedsstatus"] == status).sum()) for status in STATUS_OPTIONEN}


def _naechster_jahrestag(tag_und_monat: date, jahr: int) -> date:
    """Wandelt ein Datum in denselben Tag/Monat in einem bestimmten Jahr um.
    Für den 29. Februar in einem Nicht-Schaltjahr gibt es dieses Datum nicht
    (date.replace() würde einen ValueError werfen) - Konvention: dann auf den
    28. Februar ausweichen, statt abzustürzen."""
    try:
        return tag_und_monat.replace(year=jahr)
    except ValueError:
        return date(jahr, 2, 28)


def naechste_geburtstage(df: pd.DataFrame, tage: int = 30) -> pd.DataFrame:
    heute = date.today()
    eintraege = []
    for _, zeile in df.iterrows():
        geb = parse_datum(zeile.get("Geburtstag", ""))
        if geb is None:
            continue
        naechster = _naechster_jahrestag(geb, heute.year)
        if naechster < heute:
            naechster = _naechster_jahrestag(geb, heute.year + 1)
        differenz = (naechster - heute).days
        if 0 <= differenz <= tage:
            eintraege.append({
                "Name": f"{zeile['Vorname']} {zeile['Nachname']}",
                "Datum": naechster.strftime("%d.%m."),
                "In Tagen": differenz,
            })
    spalten = ["Name", "Datum", "In Tagen"]
    if not eintraege:
        return pd.DataFrame(columns=spalten)
    return pd.DataFrame(eintraege).sort_values("In Tagen").reset_index(drop=True)[spalten]


def mitgliedschaftsjubilaeen(df: pd.DataFrame) -> pd.DataFrame:
    heute = date.today()
    eintraege = []
    for _, zeile in df.iterrows():
        eintritt = parse_datum(zeile.get("Eintrittsdatum", ""))
        if eintritt is None:
            continue
        jahre = heute.year - eintritt.year
        if jahre in JUBILAEUMS_MEILENSTEINE:
            eintraege.append({
                "Name": f"{zeile['Vorname']} {zeile['Nachname']}",
                "Jahre dabei": jahre,
            })
    spalten = ["Name", "Jahre dabei"]
    if not eintraege:
        return pd.DataFrame(columns=spalten)
    return pd.DataFrame(eintraege)[spalten]


# --- Fotos (genau eines pro Mitglied, neuer Upload ersetzt altes) ---

def _foto_pfad_vorhanden(mitglied_id: str) -> Path | None:
    if not FOTOS_DIR.exists():
        return None
    treffer = sorted(FOTOS_DIR.glob(f"{mitglied_id}.*"))
    return treffer[0] if treffer else None


def get_photo_path(mitglied_id: str) -> Path | None:
    return _foto_pfad_vorhanden(mitglied_id)


def save_photo(mitglied_id: str, uploaded_file) -> Path:
    FOTOS_DIR.mkdir(parents=True, exist_ok=True)
    delete_photo(mitglied_id)
    endung = Path(uploaded_file.name).suffix.lower() or ".jpg"
    ziel = FOTOS_DIR / f"{mitglied_id}{endung}"
    with open(ziel, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return ziel


def delete_photo(mitglied_id: str) -> None:
    vorhandenes = _foto_pfad_vorhanden(mitglied_id)
    if vorhandenes:
        vorhandenes.unlink()


# --- Anhänge (beliebig viele pro Mitglied) ---

def _anhang_ordner(mitglied_id: str) -> Path:
    return ANHAENGE_DIR / mitglied_id


def list_attachments(mitglied_id: str) -> list[Path]:
    ordner = _anhang_ordner(mitglied_id)
    if not ordner.exists():
        return []
    return sorted(p for p in ordner.iterdir() if p.is_file())


def sichere_dateiname(dateiname: str) -> str:
    """Reduziert einen (potenziell vom Client manipulierten) Dateinamen auf den
    reinen Basisnamen ohne Pfadanteile, damit kein Schreibzugriff außerhalb des
    vorgesehenen Zielordners möglich ist (Pfad-Traversal)."""
    basis = Path(dateiname).name
    basis = basis.replace("\\", "_")
    if not basis or basis in {".", ".."}:
        basis = "datei"
    return basis


def validate_attachment(uploaded_file) -> str | None:
    """Prüft Dateityp und Größe eines Anhang-Uploads. Gibt bei Verstoß eine
    Fehlermeldung zurück, sonst None."""
    endung = Path(uploaded_file.name).suffix.lower()
    if endung not in ANHANG_ERLAUBTE_ENDUNGEN:
        erlaubt = ", ".join(sorted(ANHANG_ERLAUBTE_ENDUNGEN))
        return f"Dateityp '{endung}' nicht erlaubt. Erlaubt sind: {erlaubt}"
    if uploaded_file.size > ANHANG_MAX_GROESSE_BYTES:
        max_mb = ANHANG_MAX_GROESSE_BYTES // (1024 * 1024)
        return f"Datei ist zu groß (max. {max_mb} MB)."
    return None


def _kollisionsfreier_dateiname(ordner: Path, name: str) -> str:
    """Hängt bei Namenskollision einen Zähler vor die Dateiendung, damit ein
    Upload nicht unbemerkt eine bereits vorhandene, gleichnamige Datei
    überschreibt (z. B. zwei Anhänge namens 'foto.jpg' von unterschiedlichen
    Uploads)."""
    ziel = ordner / name
    if not ziel.exists():
        return name
    stamm, endung = Path(name).stem, Path(name).suffix
    zaehler = 1
    while (ordner / f"{stamm}_{zaehler}{endung}").exists():
        zaehler += 1
    return f"{stamm}_{zaehler}{endung}"


def save_attachment(mitglied_id: str, uploaded_file) -> Path:
    ordner = _anhang_ordner(mitglied_id)
    ordner.mkdir(parents=True, exist_ok=True)
    dateiname = _kollisionsfreier_dateiname(ordner, sichere_dateiname(uploaded_file.name))
    ziel = ordner / dateiname
    with open(ziel, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return ziel


def delete_attachment(mitglied_id: str, dateiname: str) -> None:
    ziel = _anhang_ordner(mitglied_id) / sichere_dateiname(dateiname)
    if ziel.exists():
        ziel.unlink()


def delete_all_attachments(mitglied_id: str) -> None:
    ordner = _anhang_ordner(mitglied_id)
    if ordner.exists():
        shutil.rmtree(ordner)


# --- Mail-Log (Historie versendeter Serienmails pro Mitglied) ---

def _mail_log_ordner(mitglied_id: str) -> Path:
    return MAIL_LOG_DIR / mitglied_id


def log_mail(mitglied_id: str, betreff: str, empfaenger: str, erfolgreich: bool = True, fehler: str = "") -> None:
    """Hält einen Serienmail-Versand an ein Mitglied fest (eine JSON-Datei pro Versand,
    analog zum Anhänge-Muster: ein Ordner pro Mitglieds-ID)."""
    ordner = _mail_log_ordner(mitglied_id)
    ordner.mkdir(parents=True, exist_ok=True)
    eintrag = {
        "zeitstempel": datetime.now().isoformat(timespec="seconds"),
        "betreff": betreff,
        "empfaenger": empfaenger,
        "erfolgreich": erfolgreich,
        "fehler": fehler,
    }
    dateiname = f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
    (ordner / dateiname).write_text(json.dumps(eintrag, ensure_ascii=False, indent=2), encoding="utf-8")


def delete_mail_log(mitglied_id: str) -> None:
    ordner = _mail_log_ordner(mitglied_id)
    if ordner.exists():
        shutil.rmtree(ordner)


def list_mail_log(mitglied_id: str) -> list[dict]:
    """Liefert alle bisherigen Mail-Log-Einträge eines Mitglieds, neueste zuerst."""
    ordner = _mail_log_ordner(mitglied_id)
    if not ordner.exists():
        return []
    eintraege = []
    for pfad in sorted(ordner.glob("*.json")):
        try:
            eintraege.append(json.loads(pfad.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return sorted(eintraege, key=lambda e: e.get("zeitstempel", ""), reverse=True)


# --- Zahlungshistorie/Beitragsjournal (analog zum Mail-Log-Muster) ---

def _zahlungen_ordner(mitglied_id: str) -> Path:
    return ZAHLUNGEN_DIR / mitglied_id


def log_zahlung(mitglied_id: str, betrag: str, datum: str, zahlungsart: str, notiz: str = "") -> None:
    """Hält eine erfasste Beitragszahlung fest (eine JSON-Datei pro Zahlung,
    analog zum Mail-Log-Muster: ein Ordner pro Mitglieds-ID)."""
    ordner = _zahlungen_ordner(mitglied_id)
    ordner.mkdir(parents=True, exist_ok=True)
    eintrag = {
        # Mikrosekunden-Präzision statt Sekunden (wie sonst im Projekt teils
        # üblich): zwei schnell hintereinander erfasste Zahlungen könnten sonst
        # denselben Sekunden-Zeitstempel bekommen, wodurch "neueste zuerst" in
        # list_zahlungen() nicht mehr eindeutig sortierbar wäre.
        "zeitstempel": datetime.now().isoformat(timespec="microseconds"),
        "datum": datum,
        "betrag": betrag,
        "zahlungsart": zahlungsart,
        "notiz": notiz,
    }
    dateiname = f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
    (ordner / dateiname).write_text(json.dumps(eintrag, ensure_ascii=False, indent=2), encoding="utf-8")


def delete_zahlungslog(mitglied_id: str) -> None:
    ordner = _zahlungen_ordner(mitglied_id)
    if ordner.exists():
        shutil.rmtree(ordner)


def list_zahlungen(mitglied_id: str) -> list[dict]:
    """Liefert alle bisherigen Zahlungs-Log-Einträge eines Mitglieds, neueste zuerst."""
    ordner = _zahlungen_ordner(mitglied_id)
    if not ordner.exists():
        return []
    eintraege = []
    for pfad in sorted(ordner.glob("*.json")):
        try:
            eintraege.append(json.loads(pfad.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return sorted(eintraege, key=lambda e: e.get("zeitstempel", ""), reverse=True)


# --- vCard ---

def build_vcard(mitglied: pd.Series) -> str:
    zeilen = ["BEGIN:VCARD", "VERSION:3.0"]
    zeilen.append(f"N:{mitglied['Nachname']};{mitglied['Vorname']};;;")
    zeilen.append(f"FN:{mitglied['Vorname']} {mitglied['Nachname']}")
    if mitglied.get("E-Mail"):
        zeilen.append(f"EMAIL:{mitglied['E-Mail']}")
    if mitglied.get("Telefon"):
        zeilen.append(f"TEL;TYPE=CELL:{mitglied['Telefon']}")
    if mitglied.get("Straße") or mitglied.get("PLZ") or mitglied.get("Stadt"):
        zeilen.append(
            f"ADR;TYPE=HOME:;;{mitglied.get('Straße', '')};{mitglied.get('Stadt', '')};;{mitglied.get('PLZ', '')};"
        )
    if mitglied.get("Geburtstag"):
        zeilen.append(f"BDAY:{mitglied['Geburtstag']}")
    if VEREINSNAME:
        zeilen.append(f"ORG:{VEREINSNAME}")
    zeilen.append("END:VCARD")
    return "\n".join(zeilen)


# --- Exporte ---

FORMEL_STARTZEICHEN = ("=", "+", "-", "@")


def _entschaerfe_formel(wert):
    """Verhindert CSV/Excel-Formula-Injection: Werte, die mit einem
    formelauslösenden Zeichen beginnen, werden mit einem führenden Apostroph
    versehen, damit Excel/LibreOffice sie als Text statt als Formel liest."""
    if isinstance(wert, str) and wert.startswith(FORMEL_STARTZEICHEN):
        return "'" + wert
    return wert


def export_excel(df: pd.DataFrame) -> bytes:
    puffer = io.BytesIO()
    sicher_df = df.drop(columns=["ID"], errors="ignore").apply(lambda spalte: spalte.map(_entschaerfe_formel))
    sicher_df.to_excel(puffer, index=False, engine="openpyxl")
    return puffer.getvalue()


def build_import_vorlage() -> bytes:
    """Erzeugt eine leere Excel-Datei mit den korrekten Spaltenüberschriften
    (ohne ID) als Vorlage für den Mitglieder-Import."""
    leer_df = pd.DataFrame(columns=[spalte for spalte in COLUMNS if spalte != "ID"])
    puffer = io.BytesIO()
    leer_df.to_excel(puffer, index=False, engine="openpyxl")
    return puffer.getvalue()


def import_members_from_excel(datei_bytes: bytes, df: pd.DataFrame) -> tuple[list[dict], list[str]]:
    """Liest eine hochgeladene Excel-Datei mit einer Mitgliederliste ein (z. B.
    zur Migration einer bestehenden Vereinsliste beim Erststart). Erwartet eine
    Kopfzeile mit (einer Teilmenge von) COLUMNS-Namen - unbekannte Spalten
    werden ignoriert, fehlende Spalten leer aufgefüllt.

    Jede Zeile wird einzeln mit validate_member() geprüft (gegen den
    fortlaufend um bereits als gültig erkannte Zeilen ergänzten Bestand, damit
    auch doppelte Mitgliedsnummern innerhalb der Datei selbst erkannt werden -
    nicht nur gegen bereits vorhandene Mitglieder). Gültige Zeilen werden als
    Liste von data-Dicts zurückgegeben (noch nicht gespeichert - der Aufrufer
    entscheidet, ob/wie sie übernommen werden), zu jeder ungültigen Zeile eine
    Fehlermeldung mit Zeilennummer sowie zusätzlich ausgewertete Zusatzfehler.
    Kein Alles-oder-Nichts: die Rückgabe zeigt vorab, was übernommen würde."""
    try:
        eingelesen = pd.read_excel(io.BytesIO(datei_bytes), dtype=str, keep_default_na=False, engine="openpyxl")
    except Exception as exc:
        return [], [f"Datei konnte nicht gelesen werden: {exc}"]

    datumsfelder = {
        "Geburtstag", "Eintrittsdatum", "Austrittsdatum", "Einwilligung_Datum",
        "Letzte_Zahlung", "SEPA_Mandatsdatum",
    }

    gueltige_datensaetze = []
    fehlermeldungen = []
    laufender_df = df.copy()
    for zeilennummer, zeile in eingelesen.iterrows():
        data = {spalte: str(zeile.get(spalte, "") or "").strip() for spalte in COLUMNS if spalte != "ID"}

        for spalte in datumsfelder:
            data[spalte] = _normalisiere_importiertes_datum(data[spalte])

        # Ohne diese Spalte in der Excel-Datei wäre der Wert sonst "" und
        # würde von validate_member() als ungültig abgelehnt (leerer String
        # ist kein gültiger Mitgliedsstatus) - "aktiv" als Standard passt zum
        # Verhalten des "Neues Mitglied"-Formulars, dessen Status-Auswahl ohne
        # explizite Vorbelegung ebenfalls auf "aktiv" (erste Option) steht.
        if not data["Mitgliedsstatus"]:
            data["Mitgliedsstatus"] = "aktiv"

        fehler = validate_member(data, laufender_df)
        if fehler:
            fehlermeldungen.append(f"Zeile {zeilennummer + 2}: " + "; ".join(fehler))
            continue
        gueltige_datensaetze.append(data)
        laufender_df = add_member(laufender_df, data)

    return gueltige_datensaetze, fehlermeldungen


def _normalisiere_importiertes_datum(wert: str) -> str:
    """Normalisiert ein aus Excel eingelesenes Datum auf das intern erwartete
    Format YYYY-MM-DD. Echte Excel-Datumszellen kommen über pandas oft als
    Text wie '2020-01-15 00:00:00' (mit Uhrzeitanteil) an statt im erwarteten
    reinen Datumsformat - ohne diese Normalisierung würde parse_datum() das
    Datum später klanglos verwerfen (gibt None zurück), das Mitglied aber
    trotzdem mit einem kaputten, nicht mehr auswertbaren Datumswert
    gespeichert. Unparsbare Werte werden zu "" (wie überall sonst in der App
    der Sentinel-Wert für "kein Datum"), damit z. B. ein fehlerhaftes
    Eintrittsdatum durch die bestehende Pflichtfeld-Prüfung auffällt, statt
    unbemerkt als Text gespeichert zu werden."""
    wert = wert.strip()
    if not wert or parse_datum(wert) is not None:
        return wert
    try:
        return pd.to_datetime(wert).date().isoformat()
    except (ValueError, TypeError):
        return ""


def export_pdf(df: pd.DataFrame) -> bytes:
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_font("helvetica", "B", size=12)
    pdf.cell(0, 8, "Mitgliederliste", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", size=7)

    anzeige_df = df.copy()
    if anzeige_df.empty:
        anzeige_df = pd.DataFrame(columns=df.columns)
        anzeige_df["Name"] = []
    else:
        anzeige_df["Name"] = anzeige_df["Nachname"] + ", " + anzeige_df["Vorname"]
    daten = anzeige_df[PDF_LISTE_SPALTEN].values.tolist()

    with pdf.table() as table:
        kopf = table.row()
        for spalte in PDF_LISTE_SPALTEN:
            kopf.cell(spalte)
        for zeile in daten:
            reihe = table.row()
            for wert in zeile:
                reihe.cell(str(wert))

    return bytes(pdf.output())


def logo_verfuegbar() -> bool:
    """Prüft, ob das Vereinslogo hinterlegt ist (vorlagen/logo.jpg) - analog zu
    aufnahmeantrag_verfuegbar() optional, damit ein fehlendes Logo (z. B. bei
    einem frischen Klon vor dem ersten Deploy) die PDF-Erzeugung nicht zum
    Absturz bringt."""
    return LOGO_PFAD.exists()


def _logo_einfuegen(pdf: FPDF, x: float, y: float, w: float) -> None:
    """Platziert das Vereinslogo an der angegebenen Stelle auf der aktuellen
    PDF-Seite, falls vorhanden. pdf.image() verändert die Text-Cursorposition
    in fpdf2 nicht, kann also unabhängig vom übrigen Seitenaufbau aufgerufen
    werden."""
    if LOGO_PFAD.exists():
        pdf.image(str(LOGO_PFAD), x=x, y=y, w=w)


def build_mitgliedsausweis(mitglied: pd.Series) -> bytes:
    pdf = FPDF(orientation="P", unit="mm", format=(85, 55))
    pdf.add_page()
    # Unten rechts platziert, da oben rechts mit langem Namen/Gruppentext und
    # Foto/Kopfzeile kollidieren kann (Karte ist mit 85x55mm sehr klein) -
    # der Bereich unterhalb des Namens/der Gruppen und neben dem Vereinsnamen
    # bleibt dagegen frei.
    _logo_einfuegen(pdf, x=74, y=46, w=8)

    foto_pfad = get_photo_path(mitglied["ID"])
    text_x = 5
    if foto_pfad:
        pdf.image(str(foto_pfad), x=5, y=5, w=18, h=18)
        text_x = 26

    pdf.set_xy(text_x, 6)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(85 - text_x - 5, 5, f"{mitglied['Vorname']} {mitglied['Nachname']}", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("helvetica", size=8)
    if mitglied.get("Mitgliedsnummer"):
        pdf.set_x(text_x)
        pdf.cell(0, 5, f"Mitglieds-Nr.: {mitglied['Mitgliedsnummer']}", new_x="LMARGIN", new_y="NEXT")
    if mitglied.get("Gruppen"):
        pdf.set_x(text_x)
        pdf.multi_cell(85 - text_x - 5, 4, mitglied["Gruppen"].replace(";", ", "))

    if VEREINSNAME:
        pdf.set_xy(5, 46)
        pdf.set_font("helvetica", "I", 7)
        pdf.cell(0, 5, VEREINSNAME)

    return bytes(pdf.output())


def _iban_gruppiert(iban: str) -> str:
    """Formatiert eine IBAN in 4er-Gruppen zur besseren Lesbarkeit auf Formularen
    (z. B. "DE89 3704 0044 0532 0130 00" statt am Stück)."""
    return " ".join(iban[i:i + 4] for i in range(0, len(iban), 4))


def build_sepa_mandat_pdf(mitglied: pd.Series) -> bytes:
    """Erzeugt ein ausfüllbares/unterschreibbares SEPA-Lastschriftmandat als PDF,
    vorausgefüllt mit den beim Mitglied hinterlegten Konto-/Beitragsdaten (sofern
    vorhanden). Leere Felder (z. B. IBAN, Mandatsreferenz) bleiben als Leerstelle
    zum handschriftlichen Ausfüllen."""
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_left_margin(20)
    pdf.set_right_margin(20)
    _logo_einfuegen(pdf, x=170, y=10, w=20)

    pdf.set_font("helvetica", "B", 14)
    pdf.cell(0, 8, "SEPA-Lastschriftmandat", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font("helvetica", size=10)
    if VEREINSNAME:
        pdf.cell(0, 6, f"Zahlungsempfänger: {VEREINSNAME}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(
        0, 6, f"Gläubiger-Identifikationsnummer: {GLAEUBIGER_ID or '(noch nicht hinterlegt)'}",
        new_x="LMARGIN", new_y="NEXT",
    )
    mandatsreferenz = mitglied.get("SEPA_Mandatsreferenz") or "(wird vom Verein ergänzt)"
    pdf.cell(0, 6, f"Mandatsreferenz: {mandatsreferenz}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.multi_cell(
        0, 6,
        "Ich ermächtige den oben genannten Zahlungsempfänger, Zahlungen von meinem Konto "
        "mittels Lastschrift einzuziehen. Zugleich weise ich mein Kreditinstitut an, die vom "
        "Zahlungsempfänger auf mein Konto gezogenen Lastschriften einzulösen.\n\n"
        "Hinweis: Ich kann innerhalb von acht Wochen, beginnend mit dem Belastungsdatum, die "
        "Erstattung des belasteten Betrages verlangen. Es gelten dabei die mit meinem "
        "Kreditinstitut vereinbarten Bedingungen.",
    )
    pdf.ln(4)

    pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 6, "Kontoinhaber", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", size=10)
    kontoinhaber = mitglied.get("Kontoinhaber") or f"{mitglied['Vorname']} {mitglied['Nachname']}"
    pdf.cell(0, 6, kontoinhaber, new_x="LMARGIN", new_y="NEXT")
    if mitglied.get("Straße") or mitglied.get("PLZ") or mitglied.get("Stadt"):
        pdf.cell(
            0, 6,
            f"{mitglied.get('Straße', '')}, {mitglied.get('PLZ', '')} {mitglied.get('Stadt', '')}",
            new_x="LMARGIN", new_y="NEXT",
        )
    pdf.ln(2)

    pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 6, "IBAN", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", size=12)
    iban = mitglied.get("IBAN")
    pdf.cell(0, 8, _iban_gruppiert(iban) if iban else "_" * 27, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)

    pdf.set_font("helvetica", size=10)
    pdf.cell(90, 6, "Ort, Datum", border="T")
    pdf.cell(0, 6, "Unterschrift", border="T", new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())


def build_beitrittserklaerung_pdf(mitglied: pd.Series) -> bytes:
    """Erzeugt eine Beitrittserklärung als PDF mit den bereits erfassten
    Mitgliedsdaten, zum Ausdrucken und Unterschreiben (z. B. nachträglich für
    Mitglieder, die vor Einführung der App beigetreten sind)."""
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_left_margin(20)
    pdf.set_right_margin(20)
    _logo_einfuegen(pdf, x=170, y=10, w=20)

    pdf.set_font("helvetica", "B", 14)
    titel = f"Beitrittserklärung{' zum ' + VEREINSNAME if VEREINSNAME else ''}"
    pdf.multi_cell(0, 8, titel)
    pdf.ln(4)

    pdf.set_font("helvetica", size=10)
    angaben = [
        ("Name", f"{mitglied['Vorname']} {mitglied['Nachname']}"),
        ("Geburtstag", parse_datum(mitglied.get("Geburtstag", "")).strftime("%d.%m.%Y")
            if parse_datum(mitglied.get("Geburtstag", "")) else "-"),
        ("Anschrift", f"{mitglied.get('Straße', '')}, {mitglied.get('PLZ', '')} {mitglied.get('Stadt', '')}"),
        ("E-Mail", mitglied.get("E-Mail", "")),
        ("Telefon", mitglied.get("Telefon", "") or "-"),
        ("Eintrittsdatum", parse_datum(mitglied.get("Eintrittsdatum", "")).strftime("%d.%m.%Y")
            if parse_datum(mitglied.get("Eintrittsdatum", "")) else "-"),
        ("Gruppen", mitglied.get("Gruppen", "").replace(";", ", ") or "-"),
    ]
    for label, wert in angaben:
        pdf.set_font("helvetica", "B", 10)
        pdf.cell(45, 7, f"{label}:")
        pdf.set_font("helvetica", size=10)
        pdf.multi_cell(0, 7, wert)
        # multi_cell setzt die X-Position nicht automatisch auf den linken Rand
        # zurück (bleibt am rechten Rand stehen) - für die nächste Zeile nötig.
        pdf.set_x(pdf.l_margin)
    pdf.ln(4)

    pdf.multi_cell(
        0, 6,
        f"Hiermit erkläre ich meinen Beitritt{' zum ' + VEREINSNAME if VEREINSNAME else ' zum Verein'} "
        "und erkenne die Vereinssatzung in ihrer jeweils gültigen Fassung an.",
    )
    if ist_minderjaehrig(mitglied.get("Geburtstag", "")):
        pdf.ln(2)
        pdf.multi_cell(
            0, 6,
            "Da das Mitglied minderjährig ist, ist zusätzlich die Unterschrift eines "
            "gesetzlichen Vertreters erforderlich.",
        )
    pdf.ln(10)

    pdf.set_font("helvetica", size=10)
    pdf.cell(90, 6, "Ort, Datum", border="T")
    pdf.cell(0, 6, "Unterschrift", border="T", new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())


def build_austrittsbestaetigung_pdf(mitglied: pd.Series) -> bytes:
    """Erzeugt eine Austrittsbestätigung als PDF - eine Bestätigung des Vereins
    an das Mitglied, dass der Austritt zum hinterlegten Austrittsdatum erfolgt
    ist. Funktioniert auch, wenn noch kein Austrittsdatum gesetzt ist (zeigt
    dann eine Leerstelle zum handschriftlichen Nachtragen)."""
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_left_margin(20)
    pdf.set_right_margin(20)
    _logo_einfuegen(pdf, x=170, y=10, w=20)

    pdf.set_font("helvetica", "B", 14)
    pdf.cell(0, 8, "Austrittsbestätigung", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    austrittsdatum = parse_datum(mitglied.get("Austrittsdatum", ""))
    austritt_text = austrittsdatum.strftime("%d.%m.%Y") if austrittsdatum else "_" * 12

    pdf.set_font("helvetica", size=11)
    verein_text = f" von {VEREINSNAME}" if VEREINSNAME else ""
    pdf.multi_cell(
        0, 7,
        f"Hiermit bestätigen wir, dass {mitglied['Vorname']} {mitglied['Nachname']} "
        f"(Mitgliedsnummer: {mitglied.get('Mitgliedsnummer', '') or '-'}) "
        f"zum {austritt_text} aus dem Verein{verein_text} ausgetreten ist.",
    )
    pdf.ln(4)
    pdf.multi_cell(
        0, 6,
        "Etwaige noch ausstehende Beitragsforderungen bleiben von dieser Bestätigung unberührt.",
    )
    pdf.ln(14)

    pdf.set_font("helvetica", size=10)
    pdf.cell(90, 6, "Ort, Datum", border="T")
    pdf.cell(0, 6, "Unterschrift Vorstand", border="T", new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())


# --- Aufnahmeantrag (vereinseigene PDF-Vorlage, automatisch ausgefüllt) ---

def aufnahmeantrag_verfuegbar() -> bool:
    """Prüft, ob die vereinseigene Aufnahmeantrag-Vorlage hinterlegt ist
    (data/vorlagen/aufnahmeantrag_vorlage.pdf) - das Formular ist optional,
    da es sich um eine vereinsspezifische Datei handelt."""
    return AUFNAHMEANTRAG_VORLAGE.exists()


def build_aufnahmeantrag_pdf(mitglied: pd.Series) -> bytes:
    """Füllt die vereinseigene Aufnahmeantrag-PDF-Vorlage automatisch mit den
    Daten des Mitglieds aus. Die Vorlage ist ein "flaches" PDF ohne
    ausfüllbare Formularfelder (kein AcroForm) - die Werte werden deshalb als
    Text-Overlay an den passenden Koordinaten über die Vorlage gelegt.

    Wirft FileNotFoundError, wenn keine Vorlage hinterlegt ist (siehe
    aufnahmeantrag_verfuegbar())."""
    if not AUFNAHMEANTRAG_VORLAGE.exists():
        raise FileNotFoundError(
            f"Keine Aufnahmeantrag-Vorlage gefunden unter {AUFNAHMEANTRAG_VORLAGE}."
        )

    vorlage = PdfReader(str(AUFNAHMEANTRAG_VORLAGE))
    erste_seite = vorlage.pages[0]
    breite = float(erste_seite.mediabox.width)
    hoehe = float(erste_seite.mediabox.height)

    overlay_puffer = io.BytesIO()
    c = reportlab_canvas.Canvas(overlay_puffer, pagesize=(breite, hoehe))
    c.setFont("Helvetica", 10)

    def schreibe(x: float, y_von_oben: float, text: str) -> None:
        """y_von_oben ist die Y-Koordinate von der Oberkante der Seite aus
        gemessen (wie bei pdfplumber ermittelt), wird hier auf reportlabs
        Ursprung unten links umgerechnet."""
        if text:
            c.drawString(x, hoehe - y_von_oben, text)

    schreibe(115, 239.3, mitglied.get("Nachname", ""))
    schreibe(350, 239.3, mitglied.get("Vorname", ""))
    schreibe(112, 262.0, mitglied.get("Straße", ""))
    schreibe(105, 284.8, mitglied.get("PLZ", ""))
    schreibe(322, 284.8, mitglied.get("Stadt", ""))
    schreibe(112, 307.5, mitglied.get("E-Mail", ""))
    geburtstag = parse_datum(mitglied.get("Geburtstag", ""))
    schreibe(380, 307.5, geburtstag.strftime("%d.%m.%Y") if geburtstag else "")
    schreibe(112, 330.3, mitglied.get("Telefon", ""))

    # Status-Ankreuzfeld: "aktiv" -> Aktives Mitglied, "passiv" -> Förderndes
    # Mitglied, sonst nicht ankreuzbar (die Vorlage kennt nur diese beiden
    # Optionen aus dem Datenmodell plus "Gastspieler", das kein eigener
    # Mitgliedsstatus in der App ist).
    status = mitglied.get("Mitgliedsstatus")
    if status == "aktiv":
        schreibe(109, 414.2, "X")
    elif status == "passiv":
        schreibe(109, 440.6, "X")

    schreibe(115, 675.8, date.today().strftime("%d.%m.%Y"))

    c.save()
    overlay_puffer.seek(0)
    overlay_seite = PdfReader(overlay_puffer).pages[0]
    erste_seite.merge_page(overlay_seite)

    writer = PdfWriter()
    writer.add_page(erste_seite)
    for weitere_seite in vorlage.pages[1:]:
        writer.add_page(weitere_seite)

    ausgabe = io.BytesIO()
    writer.write(ausgabe)
    return ausgabe.getvalue()


# --- Serienbrief-PDF (optionaler Anhang zur Serienmail) ---

def fuelle_platzhalter(vorlage: str, mitglied: pd.Series) -> str:
    """Ersetzt Platzhalter wie {Vorname} in einer Serienmail-/Serienbrief-Vorlage
    durch die Werte des jeweiligen Mitglieds. Unbekannte Platzhalter bleiben
    unverändert stehen, statt einen Fehler zu werfen.

    Iteriert bewusst über mitglied.index statt der festen COLUMNS-Liste, damit
    auch zusätzliche, nur zur Laufzeit vorhandene Felder ersetzt werden (z. B.
    "Faelligkeitsdatum" aus faellige_mitglieder() bei der Beitragsmahnung, das
    keine reguläre Mitglieder-Spalte ist)."""
    ergebnis = vorlage
    for spalte in mitglied.index:
        ergebnis = ergebnis.replace(f"{{{spalte}}}", str(mitglied.get(spalte, "")))
    return ergebnis


def build_serienbrief_pdf(mitglied: pd.Series, betreff: str, text: str) -> bytes:
    """Erzeugt ein einfaches Brief-PDF (A4) mit personalisiertem Betreff/Text,
    z. B. als Anhang zu einer Serienmail. Platzhalter in Betreff/Text sind bereits
    vorab mit fuelle_platzhalter() aufzulösen."""
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_left_margin(20)
    pdf.set_right_margin(20)
    _logo_einfuegen(pdf, x=170, y=10, w=20)

    if VEREINSNAME:
        pdf.set_font("helvetica", "I", 9)
        pdf.cell(0, 6, VEREINSNAME, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    pdf.set_font("helvetica", "B", 12)
    pdf.multi_cell(0, 7, betreff)
    pdf.ln(4)

    pdf.set_font("helvetica", size=11)
    pdf.multi_cell(0, 6, text)

    return bytes(pdf.output())


# --- Vereinskalender (Termine, .ics-Export) ---

TERMINE_CSV_PATH = DATA_DIR / "termine.csv"
TERMINE_COLUMNS = ["ID", "Titel", "Beschreibung", "Ort", "Start", "Ende"]


def load_termine() -> pd.DataFrame:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not TERMINE_CSV_PATH.exists():
        df = pd.DataFrame(columns=TERMINE_COLUMNS)
        save_termine(df)
        return df
    df = pd.read_csv(TERMINE_CSV_PATH, dtype=str, keep_default_na=False)
    for spalte in TERMINE_COLUMNS:
        if spalte not in df.columns:
            df[spalte] = ""
    return df[TERMINE_COLUMNS]


def save_termine(df: pd.DataFrame) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(TERMINE_CSV_PATH, index=False)


def parse_datetime(text: str) -> datetime | None:
    """Parst einen Termin-Zeitstempel im Format 'YYYY-MM-DD HH:MM' (so wie
    build_ics_feed und die Termine-Ansicht ihn schreiben/erwarten)."""
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def validate_termin(data: dict) -> list[str]:
    fehler = []
    if not data.get("Titel", "").strip():
        fehler.append("Bitte einen Titel angeben.")
    start = parse_datetime(data.get("Start", ""))
    if start is None:
        fehler.append("Bitte einen gültigen Start (Datum + Uhrzeit) angeben.")
    ende = parse_datetime(data.get("Ende", ""))
    if start is not None and ende is not None and ende < start:
        fehler.append("Das Ende darf nicht vor dem Start liegen.")
    return fehler


def add_termin(df: pd.DataFrame, data: dict) -> pd.DataFrame:
    neue_zeile = {spalte: data.get(spalte, "") for spalte in TERMINE_COLUMNS}
    neue_zeile["ID"] = str(uuid.uuid4())
    neuer_df = pd.concat([df, pd.DataFrame([neue_zeile])], ignore_index=True)
    return neuer_df[TERMINE_COLUMNS]


def delete_termin(df: pd.DataFrame, termin_id: str) -> pd.DataFrame:
    return df[df["ID"] != termin_id].reset_index(drop=True)


def kommende_termine(df: pd.DataFrame, anzahl: int = 5) -> pd.DataFrame:
    """Liefert die nächsten anstehenden Termine (Start in der Zukunft oder
    heute), sortiert nach Start, für die 'Bald anstehend'-Sektion der Übersicht."""
    jetzt = datetime.now()
    eintraege = []
    for _, zeile in df.iterrows():
        start = parse_datetime(zeile.get("Start", ""))
        if start is None or start < jetzt:
            continue
        eintraege.append({
            "Titel": zeile["Titel"],
            "Beginn": start.strftime("%d.%m.%Y %H:%M"),
            "Ort": zeile.get("Ort", ""),
            "_start": start,
        })
    spalten = ["Titel", "Beginn", "Ort"]
    if not eintraege:
        return pd.DataFrame(columns=spalten)
    sortiert = pd.DataFrame(eintraege).sort_values("_start").head(anzahl).reset_index(drop=True)
    return sortiert[spalten]


def _ics_escape(text: str) -> str:
    """Escaped Sonderzeichen für iCalendar-Textfelder (RFC 5545, Abschnitt 3.3.11):
    Backslash, Kommas, Semikolons und Zeilenumbrüche müssen mit Backslash
    maskiert werden, sonst wird das Format von Kalender-Programmen falsch
    interpretiert oder abgelehnt."""
    if not text:
        return ""
    return (
        text.replace("\\", "\\\\")
        .replace(",", "\\,")
        .replace(";", "\\;")
        .replace("\n", "\\n")
    )


def build_ics_feed(termine_df: pd.DataFrame) -> bytes:
    """Erzeugt einen iCalendar-Feed (.ics) aus den gepflegten Vereinsterminen,
    zum manuellen Import in Google Calendar/Apple Kalender/Outlook ("Kalender
    importieren" -> Datei wählen). Reines RFC-5545-Text-Building, keine externe
    Abhängigkeit nötig - das Format ist klein und stabil genug dafür."""
    zeilen = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Mitgliederverwaltung//Vereinskalender//DE",
        "CALSCALE:GREGORIAN",
    ]
    jetzt_utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for _, zeile in termine_df.iterrows():
        start = parse_datetime(zeile.get("Start", ""))
        if start is None:
            continue
        ende = parse_datetime(zeile.get("Ende", "")) or start
        zeilen.append("BEGIN:VEVENT")
        zeilen.append(f"UID:{zeile['ID']}@mitgliederverwaltung")
        zeilen.append(f"DTSTAMP:{jetzt_utc}")
        zeilen.append(f"DTSTART:{start.strftime('%Y%m%dT%H%M%S')}")
        zeilen.append(f"DTEND:{ende.strftime('%Y%m%dT%H%M%S')}")
        zeilen.append(f"SUMMARY:{_ics_escape(zeile.get('Titel', ''))}")
        if zeile.get("Beschreibung"):
            zeilen.append(f"DESCRIPTION:{_ics_escape(zeile['Beschreibung'])}")
        if zeile.get("Ort"):
            zeilen.append(f"LOCATION:{_ics_escape(zeile['Ort'])}")
        zeilen.append("END:VEVENT")
    zeilen.append("END:VCALENDAR")
    # RFC 5545 verlangt CRLF-Zeilenumbrüche.
    return ("\r\n".join(zeilen) + "\r\n").encode("utf-8")


# --- Automatische Beitragsmahnung ---

def faellige_mitglieder(df: pd.DataFrame, stichtag: date | None = None) -> pd.DataFrame:
    """Liefert alle Mitglieder, deren nächste Beitragsfälligkeit (berechnet aus
    Letzte_Zahlung + Zahlungsrhythmus) am oder vor dem Stichtag liegt und die
    eine E-Mail-Adresse hinterlegt haben (sonst könnte ohnehin keine Mahnung
    verschickt werden). Ohne hinterlegte Letzte_Zahlung wird das Mitglied nicht
    als fällig behandelt, da dann keine Fälligkeit berechenbar ist."""
    stichtag = stichtag or date.today()
    eintraege = []
    for _, zeile in df.iterrows():
        if not zeile.get("Letzte_Zahlung") or not zeile.get("E-Mail"):
            continue
        faelligkeit = compute_next_due(zeile["Letzte_Zahlung"], zeile.get("Zahlungsrhythmus", ""))
        if not faelligkeit:
            continue
        if parse_datum(faelligkeit) <= stichtag:
            eintraege.append({**zeile.to_dict(), "Faelligkeitsdatum": faelligkeit})
    if not eintraege:
        return pd.DataFrame(columns=list(df.columns) + ["Faelligkeitsdatum"])
    return pd.DataFrame(eintraege)


def build_kassierer_beitragsuebersicht(faellig_df: pd.DataFrame) -> str:
    """Baut den Text der Sammel-Benachrichtigung an den Kassierer mit allen
    aktuell fälligen Mitgliedern (Name, Betrag, Fälligkeitsdatum)."""
    if faellig_df.empty:
        return "Aktuell sind keine Mitgliedsbeiträge fällig."
    zeilen = [f"Aktuell sind {len(faellig_df)} Mitgliedsbeitrag/-beiträge fällig:", ""]
    for _, zeile in faellig_df.iterrows():
        zeilen.append(
            f"- {zeile['Vorname']} {zeile['Nachname']}: {zeile['Beitragsbetrag']} € "
            f"(fällig seit {zeile['Faelligkeitsdatum']})"
        )
    return "\n".join(zeilen)


# --- Terminabfrage/Umfrage (Doodle-artig) ---

UMFRAGEN_DIR = DATA_DIR / "umfragen"
UMFRAGE_ANTWORT_OPTIONEN = ["ja", "nein", "vielleicht"]


def _umfrage_ordner(umfrage_id: str) -> Path:
    return UMFRAGEN_DIR / umfrage_id


def erstelle_umfrage(titel: str, beschreibung: str, terminoptionen: list[str]) -> str:
    """Legt eine neue Terminabfrage an und gibt ihre ID zurück. terminoptionen
    ist eine Liste frei formulierter Optionen (z. B. Datum/Ort-Kombinationen),
    keine strukturierten Zeitangaben - die Auswahl an einem starren Zeitformat
    festzumachen wäre für die Anwendungsfälle (Vereinsausflug, Turniertermin)
    unnötig einschränkend."""
    umfrage_id = str(uuid.uuid4())
    ordner = _umfrage_ordner(umfrage_id)
    ordner.mkdir(parents=True, exist_ok=True)
    meta = {
        "id": umfrage_id,
        "titel": titel,
        "beschreibung": beschreibung,
        "terminoptionen": terminoptionen,
        "erstellt_am": datetime.now().isoformat(timespec="microseconds"),
    }
    (ordner / "umfrage.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    antworten_df = pd.DataFrame(columns=["Mitglied_ID", "Terminoption", "Antwort"])
    antworten_df.to_csv(ordner / "antworten.csv", index=False)
    return umfrage_id


def lade_umfrage(umfrage_id: str) -> dict | None:
    pfad = _umfrage_ordner(umfrage_id) / "umfrage.json"
    if not pfad.exists():
        return None
    return json.loads(pfad.read_text(encoding="utf-8"))


def liste_umfragen() -> list[dict]:
    """Liefert alle Umfragen, neueste zuerst."""
    if not UMFRAGEN_DIR.exists():
        return []
    umfragen = []
    for ordner in UMFRAGEN_DIR.iterdir():
        meta = lade_umfrage(ordner.name)
        if meta is not None:
            umfragen.append(meta)
    return sorted(umfragen, key=lambda m: m["erstellt_am"], reverse=True)


def _lade_antworten(umfrage_id: str) -> pd.DataFrame:
    pfad = _umfrage_ordner(umfrage_id) / "antworten.csv"
    if not pfad.exists():
        return pd.DataFrame(columns=["Mitglied_ID", "Terminoption", "Antwort"])
    return pd.read_csv(pfad, dtype=str, keep_default_na=False)


def setze_antwort(umfrage_id: str, mitglied_id: str, terminoption: str, antwort: str) -> None:
    """Trägt die Antwort eines Mitglieds zu einer Terminoption ein. Eine bereits
    vorhandene Antwort derselben Person zu derselben Option wird ersetzt (kein
    Duplikat), damit man seine Stimme ändern kann."""
    if antwort not in UMFRAGE_ANTWORT_OPTIONEN:
        raise ValueError(f"Ungültige Antwort: {antwort}")
    df = _lade_antworten(umfrage_id)
    maske = (df["Mitglied_ID"] == mitglied_id) & (df["Terminoption"] == terminoption)
    df = df[~maske]
    neue_zeile = pd.DataFrame([{"Mitglied_ID": mitglied_id, "Terminoption": terminoption, "Antwort": antwort}])
    df = pd.concat([df, neue_zeile], ignore_index=True)
    ordner = _umfrage_ordner(umfrage_id)
    ordner.mkdir(parents=True, exist_ok=True)
    df.to_csv(ordner / "antworten.csv", index=False)


def umfrage_ergebnis(umfrage_id: str) -> pd.DataFrame:
    """Kreuztabelle Terminoption x Antwort-Anzahl für die Auswertungsansicht."""
    meta = lade_umfrage(umfrage_id)
    terminoptionen = meta["terminoptionen"] if meta else []
    df = _lade_antworten(umfrage_id)
    ergebnis = pd.DataFrame(0, index=terminoptionen, columns=UMFRAGE_ANTWORT_OPTIONEN)
    for _, zeile in df.iterrows():
        if zeile["Terminoption"] in ergebnis.index and zeile["Antwort"] in ergebnis.columns:
            ergebnis.loc[zeile["Terminoption"], zeile["Antwort"]] += 1
    ergebnis.index.name = "Terminoption"
    return ergebnis.reset_index()


def antwort_von_mitglied(umfrage_id: str, mitglied_id: str) -> dict[str, str]:
    """Liefert die bisherigen Antworten eines Mitglieds als {Terminoption: Antwort},
    damit die Abstimm-UI vorbelegt werden kann."""
    df = _lade_antworten(umfrage_id)
    eigene = df[df["Mitglied_ID"] == mitglied_id]
    return dict(zip(eigene["Terminoption"], eigene["Antwort"]))
