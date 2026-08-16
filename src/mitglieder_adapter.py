# mitglieder_adapter.py
"""
Bindet mitglieder.py/mailer.py (im Repo-Root dieses eigenständigen
Windows-App-Repos, ursprünglich aus der Streamlit-Web-App übernommen) ein.
Beide Module rufen kein st.* auf und sind daher unverändert wiederverwendbar.

Hinweis: mitglieder.py/mailer.py sind eine Kopie aus dem Haupt-Repo
(Mitgliederverwaltung) und werden bei Änderungen an der Web-App-Datenschicht
manuell synchron gehalten, da dieses Repo bewusst eigenständig ist.
"""

import shutil
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # Im PyInstaller-Onedir-Build liegt mitglieder_adapter.py (als Teil des
    # Programmarchivs) NICHT neben der .exe, sondern in _internal/ -
    # Path(__file__) darauf zu basieren würde Datenverzeichnisse fälschlich
    # dorthin verlegen. sys.executable zeigt stattdessen zuverlässig auf die
    # .exe selbst, deren übergeordneter Ordner der tatsächliche App-Ordner ist.
    PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import mitglieder  # noqa: E402
import mailer  # noqa: E402

# WICHTIG: Nutzerdaten liegen bewusst NICHT im App-/Repo-Ordner (wie früher),
# sondern in %APPDATA%\Mitgliederverwaltung\ - genau wie schon users.json,
# smtp_config.json und spalten_config.json. Grund: PyInstaller löscht beim
# Bauen (COLLECT-Schritt) den kompletten dist/Mitgliederverwaltung/-Ordner
# und legt ihn neu an, bevor die neuen Dateien hineinkopiert werden - lag
# data/ dort (weil PROJECT_ROOT im gebauten Build = Ordner neben der .exe),
# wurden die echten Mitgliederdaten bei jedem Neubau der .exe mitgelöscht.
# %APPDATA% liegt komplett außerhalb dieses Build-Ordners und ist davon nie
# betroffen - unabhängig davon, wie oft die App neu gebaut wird.
APPDATA_ROOT = Path.home() / "AppData" / "Roaming" / "Mitgliederverwaltung"
_DATA_DIR = APPDATA_ROOT / "data"
_BACKUPS_DIR = APPDATA_ROOT / "backups"

# Alle Verzeichniskonstanten, die mitglieder.py beim eigenen Import einmalig
# aus seinem eigenen BASE_DIR ableitet, werden hier explizit auf denselben
# Root umgebogen - sich nur auf DATA_DIR zu verlassen reicht nicht, da
# BACKUPS_DIR/ZAHLUNGEN_DIR eigenständige Modulkonstanten sind, die nicht
# automatisch mit DATA_DIR "mitwandern".
mitglieder.DATA_DIR = _DATA_DIR
mitglieder.CSV_PATH = _DATA_DIR / "mitglieder.csv"
mitglieder.FOTOS_DIR = _DATA_DIR / "fotos"
mitglieder.ANHAENGE_DIR = _DATA_DIR / "anhaenge"
mitglieder.MAIL_LOG_DIR = _DATA_DIR / "mail_log"
mitglieder.ZAHLUNGEN_DIR = _DATA_DIR / "zahlungen"
mitglieder.BACKUPS_DIR = _BACKUPS_DIR


def _einmalige_datenmigration() -> str | None:
    """Verschiebt data/ bzw. backups/ von ihrem alten, unsicheren Ort (neben
    der .exe bzw. im Repo-Root) nach %APPDATA%, falls dort noch Daten aus
    einer älteren Version dieser App liegen und in %APPDATA% noch nichts
    existiert. Gibt eine Nutzer-Meldung zurück, falls migriert wurde, sonst
    None. Läuft nur einmal, danach existiert der neue Ordner bereits."""
    alte_data_dir = PROJECT_ROOT / "data"
    alte_backups_dir = PROJECT_ROOT / "backups"
    migriert = []

    if alte_data_dir.exists() and not _DATA_DIR.exists():
        _DATA_DIR.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(alte_data_dir), str(_DATA_DIR))
        migriert.append("Mitgliederdaten")

    if alte_backups_dir.exists() and not _BACKUPS_DIR.exists():
        _BACKUPS_DIR.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(alte_backups_dir), str(_BACKUPS_DIR))
        migriert.append("Sicherheits-Backups")

    if not migriert:
        return None
    return (
        f"{' und '.join(migriert)} wurden einmalig von {PROJECT_ROOT} nach "
        f"{APPDATA_ROOT} verschoben, damit sie bei zukünftigen .exe-Neubauten "
        f"nicht mehr versehentlich gelöscht werden können."
    )


MIGRATION_MELDUNG = _einmalige_datenmigration()


class LocalUploadedFile:
    """Adapter, der eine lokale Datei so kapselt, wie mitglieder.py es von einem
    Streamlit-UploadedFile erwartet (.name, .size, .getbuffer())."""

    def __init__(self, path):
        self._path = Path(path)
        self.name = self._path.name
        self.size = self._path.stat().st_size

    def getbuffer(self) -> bytes:
        return self._path.read_bytes()


# --- SMTP-Konfiguration (lokale JSON-Datei statt .streamlit/secrets.toml) ---

SMTP_CONFIG_FILE = Path.home() / "AppData" / "Roaming" / "Mitgliederverwaltung" / "smtp_config.json"

SMTP_FELDER = ["host", "port", "user", "passwort", "absender"]


def load_smtp_config() -> dict:
    """Lädt die lokal gespeicherte SMTP-Konfiguration. Gibt ein leeres Dict
    zurück, falls noch keine Konfiguration existiert."""
    if not SMTP_CONFIG_FILE.exists():
        return {}
    import json

    try:
        return json.loads(SMTP_CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_smtp_config(config: dict) -> None:
    import json

    SMTP_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    SMTP_CONFIG_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")


def smtp_secrets_wrapper() -> dict:
    """Baut ein Objekt, das mailer.smtp_konfiguration() genau wie st.secrets
    konsumieren kann: {"smtp": {...}}. Ein einfaches dict genügt, da
    smtp_konfiguration() nur "in", "[...]" und .get() auf dem smtp-Teil nutzt."""
    smtp = load_smtp_config()
    return {"smtp": smtp} if smtp else {}


def mitgliederzahl_je_jahr(df) -> list:
    """Liefert eine Liste von (Jahr, Anzahl aktiver Mitglieder am Jahresende)
    für jedes Jahr von der frühesten Eintrittsdatum-Jahreszahl bis zum
    aktuellen Jahr - Basis für das Mitgliederentwicklungs-Diagramm. Aktiv am
    Jahresende bedeutet: Eintrittsjahr <= Jahr und (kein Austrittsdatum oder
    Austrittsjahr > Jahr)."""
    from datetime import date

    zeitraeume = []
    for _, zeile in df.iterrows():
        eintritt = mitglieder.parse_datum(zeile.get("Eintrittsdatum", ""))
        if eintritt is None:
            continue
        austritt = mitglieder.parse_datum(zeile.get("Austrittsdatum", ""))
        zeitraeume.append((eintritt.year, austritt.year if austritt else None))

    if not zeitraeume:
        return []

    start_jahr = min(jahr for jahr, _ in zeitraeume)
    end_jahr = date.today().year
    ergebnis = []
    for jahr in range(start_jahr, end_jahr + 1):
        anzahl = sum(
            1 for eintritt_jahr, austritt_jahr in zeitraeume
            if eintritt_jahr <= jahr and (austritt_jahr is None or austritt_jahr > jahr)
        )
        ergebnis.append((jahr, anzahl))
    return ergebnis


def naechste_faellige_zahlungen(df, tage: int = 30) -> list:
    """Liefert eine nach Fälligkeit aufsteigend sortierte Liste anstehender
    und bereits überfälliger Beitragszahlungen - Basis für die
    "Nächste Zahlung fällig"-Liste in der Übersicht. Anders als
    mitglieder.faellige_mitglieder() (nur bereits überfällige Mitglieder mit
    E-Mail, für den Mahnungsversand) werden hier auch demnächst fällige
    Mitglieder sowie Mitglieder ohne E-Mail berücksichtigt, da es nur um die
    Anzeige geht. Mitglieder ohne Letzte_Zahlung (keine Fälligkeit berechenbar)
    werden übersprungen. Jeder Eintrag enthält "name", "faelligkeitsdatum"
    (ISO) und "tage" (negativ = überfällig, 0 = heute, positiv = demnächst)."""
    from datetime import date

    heute = date.today()
    eintraege = []
    for _, zeile in df.iterrows():
        if not zeile.get("Letzte_Zahlung"):
            continue
        faelligkeit = mitglieder.compute_next_due(zeile["Letzte_Zahlung"], zeile.get("Zahlungsrhythmus", ""))
        if not faelligkeit:
            continue
        faelligkeit_datum = mitglieder.parse_datum(faelligkeit)
        differenz = (faelligkeit_datum - heute).days
        if differenz > tage:
            continue
        eintraege.append({
            "name": f"{zeile['Vorname']} {zeile['Nachname']}",
            "faelligkeitsdatum": faelligkeit,
            "tage": differenz,
        })
    eintraege.sort(key=lambda e: e["tage"])
    return eintraege


def naechste_freie_mitgliedsnummer(df) -> str:
    """Ermittelt die kleinste positive ganze Zahl, die noch nicht als
    Mitgliedsnummer vergeben ist - löst also zuerst Lücken durch
    ausgetretene/gelöschte Mitglieder, bevor eine neue Höchstzahl vorgeschlagen
    wird. Nicht-numerische/leere Mitgliedsnummern werden ignoriert."""
    vergeben = set()
    for wert in df["Mitgliedsnummer"]:
        wert = str(wert).strip()
        if wert.isdigit():
            vergeben.add(int(wert))
    kandidat = 1
    while kandidat in vergeben:
        kandidat += 1
    return str(kandidat)


# --- Backup-Verschlüsselung (Windows-App-spezifisch, mitglieder.py bleibt roh) ---
#
# mitglieder.build_backup_zip()/restore_from_backup() erzeugen/lesen bewusst
# unverschlüsselte ZIPs (identisch zur Web-App). Die Backup-Datei enthält aber
# IBAN, Adressen und Fotos im Klartext - für den Fall, dass sie z. B. per
# Mail an ein anderes Vorstandsmitglied weitergegeben wird, bietet die
# Windows-App hier eine optionale AES-Verschlüsselung on top an. Python-
# Standard-zipfile kann keine echte Verschlüsselung, daher pyzipper (AES-256).


def verschluessele_zip(zip_bytes: bytes, passwort: str) -> bytes:
    """Nimmt ein von mitglieder.build_backup_zip() erzeugtes Klartext-ZIP und
    verschlüsselt jeden Eintrag AES-256 mit dem übergebenen Passwort."""
    import io
    import zipfile
    import pyzipper

    quelle = zipfile.ZipFile(io.BytesIO(zip_bytes))
    puffer = io.BytesIO()
    with pyzipper.AESZipFile(
        puffer, "w", compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES
    ) as zf:
        zf.setpassword(passwort.encode("utf-8"))
        for name in quelle.namelist():
            zf.writestr(name, quelle.read(name))
    return puffer.getvalue()


def entschluessele_zip(zip_bytes: bytes, passwort: str) -> bytes:
    """Kehrt verschluessele_zip() um - liefert wieder ein normales
    Klartext-ZIP, das mitglieder.restore_from_backup() verarbeiten kann.
    Wirft ValueError bei falschem Passwort oder beschädigter Datei."""
    import io
    import zipfile
    import pyzipper

    puffer = io.BytesIO()
    try:
        quelle = pyzipper.AESZipFile(io.BytesIO(zip_bytes))
        quelle.setpassword(passwort.encode("utf-8"))
        namen = quelle.namelist()
        with zipfile.ZipFile(puffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for name in namen:
                zf.writestr(name, quelle.read(name))
    except (RuntimeError, pyzipper.BadZipFile) as exc:
        raise ValueError("Falsches Passwort oder beschädigte Backup-Datei.") from exc
    return puffer.getvalue()


def ist_verschluesseltes_backup(zip_bytes: bytes) -> bool:
    """Erkennt, ob ein Backup-ZIP mit verschluessele_zip() erzeugt wurde -
    Backup-Dialoge nutzen das, um beim Wiederherstellen automatisch zu
    entscheiden, ob vorher ein Passwort abgefragt werden muss."""
    import io
    import pyzipper

    try:
        zf = pyzipper.AESZipFile(io.BytesIO(zip_bytes))
        return any(info.flag_bits & 0x1 for info in zf.infolist())
    except Exception:
        return False


# --- Spalten-Sichtbarkeit in der Übersichtstabelle (lokal gespeichert) ---

SPALTEN_CONFIG_FILE = Path.home() / "AppData" / "Roaming" / "Mitgliederverwaltung" / "spalten_config.json"


def load_ausgeblendete_spalten() -> list:
    """Lädt die Liste der vom Nutzer ausgeblendeten Spaltennamen der
    Übersichtstabelle. Gibt eine leere Liste zurück, falls noch keine
    Auswahl gespeichert wurde (Standard: alle Spalten sichtbar)."""
    if not SPALTEN_CONFIG_FILE.exists():
        return []
    import json

    try:
        daten = json.loads(SPALTEN_CONFIG_FILE.read_text(encoding="utf-8"))
        return daten.get("ausgeblendet", [])
    except (json.JSONDecodeError, OSError):
        return []


def save_ausgeblendete_spalten(spalten: list) -> None:
    import json

    SPALTEN_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    SPALTEN_CONFIG_FILE.write_text(json.dumps({"ausgeblendet": spalten}, indent=2), encoding="utf-8")
