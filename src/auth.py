# auth.py
"""
Authentifizierung für die Windows-Offline-Version der Mitgliederverwaltung.

Lokale Authentifizierung mit einer JSON-Datei in %APPDATA%.
Unterstützt Anmeldeversuche, Passwortprüfung (einfache SHA‑256-Hash) und
Sitzungstoken (Session-Handling ist optional – wird nur für den Login-Flow verwendet).
"""

import json
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
)

# Pfad zu den Benutzerdaten: %APPDATA%\Mitgliederverwaltung\users.json
USER_FILE = Path.home() / "AppData" / "Roaming" / "Mitgliederverwaltung" / "users.json"


def hash_password(password: str) -> str:
    """Erzeuge einen einfachen SHA‑256-Hash (für die lokale Nutzung ausreichend)."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def ensure_user_file():
    """Erstelle die users.json-Datei, falls sie nicht existiert, mit dem Standard-Administrator-Account."""
    if not USER_FILE.exists():
        USER_FILE.parent.mkdir(parents=True, exist_ok=True)
        # Für die lokale Nutzung genügt ein einfacher SHA-256-Hash (keine bcrypt-Abhängigkeit nötig).
        # Der Hash wird hier beim ersten Start erzeugt, nicht bei der Installation.
        hashed = hash_password("admin123")
        data = {
            "users": [
                {
                    "username": "admin",
                    "password_hash": hashed,
                    "is_default": True,
                }
            ]
        }
        USER_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

def get_users() -> Dict[str, Any]:
    """Lade die Benutzerliste aus der JSON-Datei."""
    if not USER_FILE.exists():
        return {"users": []}
    return json.loads(USER_FILE.read_text(encoding="utf-8"))

def save_users(data: Dict[str, Any]) -> None:
    """Schreibe die Benutzerliste zurück in die JSON-Datei."""
    USER_FILE.parent.mkdir(parents=True, exist_ok=True)
    USER_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

def authenticate(username: str, password: str) -> bool:
    """Prüfe Username/Password gegen die lokale Benutzerdaten."""
    ensure_user_file()
    users = get_users()
    hashed_input = hash_password(password)
    for user in users.get("users", []):
        if user["username"] == username and user["password_hash"] == hashed_input:
            return True
    return False

def login_dialog(parent=None) -> Optional[str]:
    """
    Zeige einen einfachen Login-Dialog an.
    Gibt den eingeloggten Benutzernamen zurück, falls erfolgreich; sonst None.
    """
    dialog = QDialog(parent)
    dialog.setWindowTitle("Login")
    dialog.resize(300, 150)
    layout = QVBoxLayout(dialog)

    layout.addWidget(QLabel("Username:"))
    username_input = QLineEdit()
    layout.addWidget(username_input)

    layout.addWidget(QLabel("Password:"))
    password_input = QLineEdit()
    password_input.setEchoMode(QLineEdit.Password)
    layout.addWidget(password_input)

    button_row = QHBoxLayout()
    login_button = QPushButton("Login")
    cancel_button = QPushButton("Abbrechen")
    # autoDefault deaktivieren: sonst würde Enter im Passwortfeld sowohl
    # returnPressed (unten) als auch einen impliziten Auto-Klick auf diesen
    # Button auslösen - attempt_login() liefe doppelt, wodurch bei falschem
    # Passwort die Fehlermeldung zweimal nacheinander erscheint.
    login_button.setAutoDefault(False)
    cancel_button.setAutoDefault(False)
    button_row.addWidget(login_button)
    button_row.addWidget(cancel_button)
    layout.addLayout(button_row)

    def attempt_login():
        username = username_input.text().strip()
        password = password_input.text().strip()
        if authenticate(username, password):
            dialog.accept()
        else:
            QMessageBox.warning(dialog, "Login-Fehler", "Falscher Benutzername oder falsches Passwort.")

    login_button.clicked.connect(attempt_login)
    cancel_button.clicked.connect(dialog.reject)
    password_input.returnPressed.connect(attempt_login)

    if dialog.exec_() == QDialog.Accepted:
        return username_input.text().strip()
    return None

# --- Beispiel-Hilfsfunktion, um einen neuen Benutzer hinzuzufügen (kann aus CLI/Installer aufgerufen werden) ---

def create_default_user() -> None:
    """
    Erstelle den Standard-Administrator-Account, falls noch nicht vorhanden.
    Dieser Aufruf sollte nur einmal erfolgen (z. B. durch den Installer).
    """
    ensure_user_file()
    data = get_users()
    if not any(u.get("is_default") for u in data.get("users", [])):
        hashed = hash_password("admin123")
        data["users"].append({
            "username": "admin",
            "password_hash": hashed,
            "is_default": True,
        })
        save_users(data)
        print(f"Standard-Benutzer 'admin' erstellt. Passwort: admin123")