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
echo  2/4: Abhaengigkeiten installieren/aktualisieren
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
echo  3/4: Vorhandene Mitgliederdaten absichern (falls noch im alten Ordner)
echo ============================================
REM Aeltere Versionen dieser App speicherten Mitgliederdaten in
REM dist\Mitgliederverwaltung\data (neben der .exe). Der naechste Build-
REM Schritt loescht diesen kompletten Ordner - falls dort noch echte Daten
REM liegen (weil die App von dort aus benutzt wurde, bevor der Datenordner
REM auf %%APPDATA%% umgestellt wurde), werden sie hier zuerst nach
REM %%APPDATA%%\Mitgliederverwaltung verschoben, damit nichts verloren geht.
if exist "dist\Mitgliederverwaltung\data" (
    if not exist "%APPDATA%\Mitgliederverwaltung\data" (
        echo Verschiebe vorhandene Mitgliederdaten nach %APPDATA%\Mitgliederverwaltung ...
        if not exist "%APPDATA%\Mitgliederverwaltung" mkdir "%APPDATA%\Mitgliederverwaltung"
        move "dist\Mitgliederverwaltung\data" "%APPDATA%\Mitgliederverwaltung\data" >nul
    )
)
if exist "dist\Mitgliederverwaltung\backups" (
    if not exist "%APPDATA%\Mitgliederverwaltung\backups" (
        if not exist "%APPDATA%\Mitgliederverwaltung" mkdir "%APPDATA%\Mitgliederverwaltung"
        move "dist\Mitgliederverwaltung\backups" "%APPDATA%\Mitgliederverwaltung\backups" >nul
    )
)

echo.
echo ============================================
echo  4/4: .exe bauen (PyInstaller)
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
