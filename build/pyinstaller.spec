# pyinstaller.spec
# Build-Spezifikation für die Windows-Desktop-Version der Mitgliederverwaltung

# Ingredienzien
import os

block_cipher = None

# SPECPATH ist der Ordner, in dem diese .spec-Datei liegt (build/) - alle Pfade
# werden relativ dazu aufgelöst, unabhängig davon, aus welchem Verzeichnis
# "pyinstaller build/pyinstaller.spec" aufgerufen wird.
PROJECT_ROOT = os.path.join(SPECPATH, "..")

# Absicherung
# mitglieder.py und mailer.py liegen im Repo-Root und werden von
# mitglieder_adapter.py importiert - müssen daher mit eingebunden werden.
A = Analysis(
    [os.path.join(PROJECT_ROOT, "src", "main.py")],
    pathex=[os.path.join(PROJECT_ROOT, "src"), PROJECT_ROOT],
    binaries=[],
    datas=[
        (os.path.join(PROJECT_ROOT, "mitglieder.py"), "."),
        (os.path.join(PROJECT_ROOT, "mailer.py"), "."),
        # Icon nur einbinden, falls vorhanden - andernfalls diese Zeile entfernen
        # (os.path.join(PROJECT_ROOT, "resources", "icons", "app.ico"), "."),
    ],
    hiddenimports=[
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'requests',
        'hashlib',
        'pandas',
        'openpyxl',
        'fpdf',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    A.pure,
    A.zipped_data,
    cipher=block_cipher,
)

# Echtes Onedir: EXE() bekommt bewusst KEINE binaries/datas - die .exe bleibt
# dadurch ein schlanker Launcher, der seine Abhängigkeiten zur Laufzeit aus
# dem von COLLECT() erzeugten _internal/-Ordner lädt. Werden binaries/datas
# zusätzlich hier übergeben (wie zuvor), bündelt PyInstaller sie ein zweites
# Mal direkt in die .exe - das macht sie unnötig groß und den Start langsamer,
# obwohl _internal/ ohnehin schon dieselben Dateien lose bereitstellt.
exe = EXE(
    pyz,
    A.scripts,
    [],
    [],
    [],
    name='Mitgliederverwaltung',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # kein UPX: vermeidet Entpack-Overhead jeder DLL/.pyd beim Start (mehr Speicherplatz statt langsamerem Start)
    console=False,  # Windowed-Modus: kein zusätzliches Konsolenfenster - alle Meldungen laufen über QMessageBox
    # icon='resources/icons/app.ico',  # einkommentieren, sobald ein Icon vorhanden ist
    uac_admin=False,
)

coll = COLLECT(
    exe,
    A.binaries,
    A.datas,
    strip=False,
    upx=False,
    name='Mitgliederverwaltung',
    # Abhängigkeiten einbetten: keine
)

# Hinweise:
# - Die Datenbank-Datei (members.db) wird im Installationsverzeichnis abgelegt und # von der App gelesen.
# - .spec sollte am Ende mit `pyinstaller your_spec.spec` erstellt werden
# - Ergebnis ist bewusst ein "onedir"-Build mit vielen losen Dateien in
#   dist/Mitgliederverwaltung/_internal/ statt einer möglichst kompakten .exe
#   (schnellerer Start). Für die Weitergabe an Endnutzer ist ein richtiger
#   Installer (z. B. Inno Setup/NSIS), der dist/Mitgliederverwaltung/ verpackt,
#   als spätere Aufgabe vorgesehen (siehe PLAN.md).