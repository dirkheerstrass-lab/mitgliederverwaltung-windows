# sync.py
"""
Synchronisationsengine für die Windows-Offline-Version der Mitgliederverwaltung.

Verantwortlich:
- Lokale Hasherstellung und Vergleich
- HTTPS-Request-Stub für serverseitige Operationen
- Conflict-Detection mit Dialog

Unvollständig: Echte Server-Integration (sollte in Phase 2 erfolgen)
"""

import hashlib
import requests
from typing import List, Dict, Any
from PyQt5.QtWidgets import QMessageBox
from datetime import datetime

# Definiere öffentlich zugängliche Endpunkte (falls Server FIREWALL schützt)
# In der Praxis wären diese lokal zugänglich oder ein privates Public-Suffix (z.B. .local)
DEV_BASE_URL = "https://192.168.1.223:8501/api/members/"
WEBDAV_BASE_URL = "DAV:https://192.168.1.223:8501/webdav2/members/"


class SyncEngine:
    def __init__(self, base_url: str = DEV_BASE_URL):
        """Initialisiere die Synchronisations-Logik mit Server-URL."""
        self.base_url = base_url
        self.local_hashes = {}
        self._last_synced = None  # Für UI-Feedback

    def _compute_local_hashes(self, members: List[Dict[str, str]]) -> None:
        """Berechne SHA-256 Hash für jedes Mitglied,
        bestehend aus:
1. Mitglied-ID
2. Vorname
3. Nachname
4. Eintrittsdatum
5. Status
        """
        self.local_hashes.clear()
        for member in members:
            data = (  # Konkatenation der Schlüsseldaten
                member.get("ID", "") + "|" +
                member.get("Vorname", "") + "|" +
                member.get("Nachname", "") + "|" +
                member.get("Eintrittsdatum", "") + "|" +
                member.get("Mitgliedsstatus", "")
            ).encode("utf-8")
            hash_val = hashlib.sha256(data).hexdigest()
            self.local_hashes[member["ID"]] = hash_val

    def get_members_diff(self, server_members: List[Dict]) -> tuple:
        """
        Vergleichen der lokalen und server-Hashes zur Erkennung
        von Unterschieden.
        """
        # Create a map of server members by ID
        server_map = {m["ID"]: m for m in server_members}
        # Compute local hashes
        self._compute_local_hashes(server_members)

        to_upload = []
        to_download = []
        conflicts = []

        # Check for members that exist locally but not on server (new local)
        for member_id, local_hash in self.local_hashes.items():
            if member_id not in server_map:
                to_upload.append(member_id)
            elif server_map[member_id].get("hash") != local_hash:
                conflicts.append(member_id)

        # Check for members that exist on server but not locally (new server)
        for member_id in server_map:
            if member_id not in self.local_hashes:
                to_download.append(member_id)

        return to_upload, to_download, conflicts

    def upload_member(self, member: Dict[str, str]) -> bool:
        """POST request to upload a member to the server."""
        try:
            response = requests.post(
                self.base_url,
                json=member,
                timeout=30,
            )
            return response.status_code in (200, 201)
        except Exception as e:
            print(f"Upload fehlgeschlagen: {e}")
            return False

    def download_member(self, member_id: str) -> Dict[str, str] | None:
        """GET request to download a member from the server."""
        try:
            response = requests.get(
                f"{self.base_url}{member_id}",
                timeout=30,
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Download fehlgeschlagen: {e}")
            return None

    def delete_member_remote(self, member_id: str) -> bool:
        """DELETE request to remove a member from the server."""
        try:
            response = requests.delete(
                f"{self.base_url}{member_id}",
                timeout=30,
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Delete fehlgeschlagen: {e}")
            return False

    def sync_now(self, local_members: List[Dict[str, str]], parent=None) -> bool:
        """
        Haupt-Synchronisationsfunktion.
        Liest die lokalen Mitglieder, vergleicht mit dem Server und führt
        Uploads/Downloads/Deletes aus.
        """
        # 1. Lokale Hashes berechnen
        self._compute_local_hashes(local_members)

        # 2. Server-Daten abrufen (falls erreichbar)
        try:
            response = requests.get(self.base_url, timeout=10)
            if response.status_code != 200:
                # Server nicht erreichbar – Offline-Modus
                return False
            server_members = response.json()
        except Exception:
            # Keine Netzwerkverbindung – Offline-Modus
            return False

        # 3. Diff berechnen
        to_upload, to_download, conflicts = self.get_members_diff(server_members)

        # 4. Konflikte auflösen (nur wenn Konflikte existieren)
        if conflicts:
            # Zeige Dialog: "Konflikt bei Mitglied X – wie weiter?"
            msg = QMessageBox(parent)
            msg.setWindowTitle("Synchronisations-Konflikt")
            msg.setText(
                "Folgende Mitglieder wurden gleichzeitig bearbeitet:\n" +
                "\n".join(conflicts)
            )
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            if msg.exec_() == QMessageBox.Yes:
                # User entscheidet: Lokal übernehmen
                pass  # Upload later
            else:
                # User entscheidet: Server übernehmen
                pass  # Download later

        # 5. Uploads durchführen
        for member_id in to_upload:
            member = next((m for m in local_members if m["ID"] == member_id), None)
            if member:
                self.upload_member(member)

        # 6. Downloads durchführen
        for member_id in to_download:
            server_member = self.download_member(member_id)
            if server_member:
                # Füge zur lokalen DB hinzu (wird von der GUI-Caller-Instanz erledigt)
                pass

        self._last_synced = datetime.now().isoformat(timespec="seconds")
        return True