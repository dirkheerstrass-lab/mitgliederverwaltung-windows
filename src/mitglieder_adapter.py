# mitglieder_adapter.py
"""
Bindet mitglieder.py/mailer.py (im Repo-Root dieses eigenständigen
Windows-App-Repos, ursprünglich aus der Streamlit-Web-App übernommen) ein.
Beide Module rufen kein st.* auf und sind daher unverändert wiederverwendbar.

Hinweis: mitglieder.py/mailer.py sind eine Kopie aus dem Haupt-Repo
(Mitgliederverwaltung) und werden bei Änderungen an der Web-App-Datenschicht
manuell synchron gehalten, da dieses Repo bewusst eigenständig ist.
"""

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

# Lokales Datenverzeichnis im App-Ordner (nicht versioniert, siehe .gitignore).
# Alle Verzeichniskonstanten, die mitglieder.py beim eigenen Import einmalig
# aus seinem eigenen BASE_DIR ableitet, werden hier explizit auf denselben
# Root umgebogen - sich nur auf DATA_DIR zu verlassen reicht nicht, da
# BACKUPS_DIR/ZAHLUNGEN_DIR eigenständige Modulkonstanten sind, die nicht
# automatisch mit DATA_DIR "mitwandern".
_DATA_DIR = PROJECT_ROOT / "data"
mitglieder.DATA_DIR = _DATA_DIR
mitglieder.CSV_PATH = _DATA_DIR / "mitglieder.csv"
mitglieder.FOTOS_DIR = _DATA_DIR / "fotos"
mitglieder.ANHAENGE_DIR = _DATA_DIR / "anhaenge"
mitglieder.MAIL_LOG_DIR = _DATA_DIR / "mail_log"
mitglieder.ZAHLUNGEN_DIR = _DATA_DIR / "zahlungen"
mitglieder.BACKUPS_DIR = PROJECT_ROOT / "backups"


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
