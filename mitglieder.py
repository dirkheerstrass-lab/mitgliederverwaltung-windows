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
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from fpdf import FPDF

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CSV_PATH = DATA_DIR / "mitglieder.csv"
FOTOS_DIR = DATA_DIR / "fotos"
ANHAENGE_DIR = DATA_DIR / "anhaenge"
MAIL_LOG_DIR = DATA_DIR / "mail_log"

# Erlaubte Dateiendungen und maximale Dateigröße für Mitglieder-Anhänge.
ANHANG_ERLAUBTE_ENDUNGEN = {".pdf", ".jpg", ".jpeg", ".png", ".docx", ".doc", ".txt"}
ANHANG_MAX_GROESSE_BYTES = 10 * 1024 * 1024  # 10 MB

# Vereinsname für vCard (ORG) und Mitgliedsausweis; leer lassen, um das Feld wegzulassen
VEREINSNAME = ""

COLUMNS = [
    "ID", "Mitgliedsnummer", "Anrede", "Vorname", "Nachname", "E-Mail",
    "Telefon", "Straße", "PLZ", "Stadt", "Geburtstag", "Eintrittsdatum",
    "Austrittsdatum", "Gruppen", "Mitgliedsstatus", "DKV-Nummer",
    "NWDV-Nummer", "Game-Shot-Nummer", "Funktion",
    "Einwilligung_Fotos_Daten", "Einwilligung_Datum",
    "Vertreter_Name", "Vertreter_Telefon", "Vertreter_E-Mail", "Notizen",
    "Zahlungsrhythmus", "Beitragsbetrag", "Letzte_Zahlung",
]

ZAHLUNGSRHYTHMUS_OPTIONEN = ["monatlich", "quartalsweise", "halbjährlich", "jährlich"]
_RHYTHMUS_MONATE = {"monatlich": 1, "quartalsweise": 3, "halbjährlich": 6, "jährlich": 12}

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


# --- Hilfsfunktionen ---

def is_valid_email(email: str) -> bool:
    return bool(email) and bool(EMAIL_REGEX.match(email.strip()))


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
    return df[df["ID"] != mitglied_id].reset_index(drop=True)


# --- Kennzahlen / Übersicht ---

def status_anzahl(df: pd.DataFrame) -> dict[str, int]:
    """Anzahl Mitglieder je Status, für die Zahlenkacheln auf der Übersicht."""
    return {status: int((df["Mitgliedsstatus"] == status).sum()) for status in STATUS_OPTIONEN}


def naechste_geburtstage(df: pd.DataFrame, tage: int = 30) -> pd.DataFrame:
    heute = date.today()
    eintraege = []
    for _, zeile in df.iterrows():
        geb = parse_datum(zeile.get("Geburtstag", ""))
        if geb is None:
            continue
        naechster = geb.replace(year=heute.year)
        if naechster < heute:
            naechster = geb.replace(year=heute.year + 1)
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


def save_attachment(mitglied_id: str, uploaded_file) -> Path:
    ordner = _anhang_ordner(mitglied_id)
    ordner.mkdir(parents=True, exist_ok=True)
    ziel = ordner / sichere_dateiname(uploaded_file.name)
    with open(ziel, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return ziel


def delete_attachment(mitglied_id: str, dateiname: str) -> None:
    ziel = _anhang_ordner(mitglied_id) / dateiname
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


def build_mitgliedsausweis(mitglied: pd.Series) -> bytes:
    pdf = FPDF(orientation="P", unit="mm", format=(85, 55))
    pdf.add_page()

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


# --- Serienbrief-PDF (optionaler Anhang zur Serienmail) ---

def fuelle_platzhalter(vorlage: str, mitglied: pd.Series) -> str:
    """Ersetzt Platzhalter wie {Vorname} in einer Serienmail-/Serienbrief-Vorlage
    durch die Werte des jeweiligen Mitglieds. Unbekannte Platzhalter bleiben
    unverändert stehen, statt einen Fehler zu werfen."""
    ergebnis = vorlage
    for spalte in COLUMNS:
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
