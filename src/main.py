# main.py
"""
Einstiegspunkt (Entry-Point) für die Windows-Desktop-App der Mitgliederverwaltung.

Ablauf:
1. Auth-Dialog anzeigen
2. Bei erfolgreichem Login: MainWindow (gui.py) öffnen
"""

import sys
from pathlib import Path

# Relativer Pfad für src-Folder: src wird ausgeführt → src/src.main.py
# Falls direkt gestartet: Pfad anpassen, damit src/ im Suchpfad ist
sys.path.insert(0, str(Path(__file__).resolve().parent))
# Falls dieser Pfad als Paket gestartet wird, src/ bereits im Pfad
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt5.QtWidgets import QApplication
from auth import login_dialog
from gui import MainWindow

def main():
    app = QApplication(sys.argv)

    # Login-Dialog öffnen
    username = login_dialog()
    if not username:
        print("Login fehlgeschlagen – Anwendung wird beendet.")
        return

    # Login erfolgreich → Hauptfenster öffnen
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()