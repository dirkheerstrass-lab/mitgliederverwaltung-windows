@echo off
REM Holt den neuesten Stand aus GitHub und baut die Mitgliederverwaltung.exe neu.
REM Einfach per Doppelklick starten (im Repo-Ordner liegend).

setlocal
cd /d "%~dp0"

echo ============================================
echo  1/3: Neuesten Stand von GitHub holen (git pull)
echo ============================================
git pull
if errorlevel 1 (
    echo.
    echo FEHLER: git pull ist fehlgeschlagen. Abbruch.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  2/3: Abhaengigkeiten installieren/aktualisieren
echo ============================================
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo FEHLER: Installation der Abhaengigkeiten ist fehlgeschlagen. Abbruch.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  3/3: .exe bauen (PyInstaller)
echo ============================================
python -m PyInstaller build\pyinstaller.spec --noconfirm
if errorlevel 1 (
    echo.
    echo FEHLER: Der Build ist fehlgeschlagen. Siehe Meldungen oben.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Fertig! Die neue .exe liegt unter:
echo  dist\Mitgliederverwaltung\Mitgliederverwaltung.exe
echo ============================================
pause
