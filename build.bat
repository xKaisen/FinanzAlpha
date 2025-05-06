@echo off
setlocal

REM === DEFINIERE SKRIPT-VERZEICHNIS ===
rem Setzt SCRIPT_DIR auf das Verzeichnis, in dem dieses Batch-Skript liegt.
set SCRIPT_DIR=%~dp0

REM === VERSION DEFINIEREN ===
set VERSION=1.0.1
set OUTDIR=dist\FinanzApp_%VERSION%
rem Annahme: icon liegt im Skript-Verzeichnis im selben Ordner wie das Skript selbst
set ICON=%SCRIPT_DIR%finanz_icon.ico

REM Der Name, den PyInstaller erzeugt:
set EXE_NAME=FinanzAlpha.exe
set EXE_PATH=%OUTDIR%\%EXE_NAME%

echo ======================================
echo 🚧 Baue FinanzAlpha v%VERSION%...
echo ======================================

REM === Dist-Ordner anlegen ===
if not exist "%OUTDIR%" (
    echo Erstelle Ausgabeordner: "%OUTDIR%"
    mkdir "%OUTDIR%"
) else (
    echo Ausgabeordner existiert bereits: "%OUTDIR%"
)

rem === PyInstaller Build ===
echo Führe PyInstaller aus...
pyinstaller ^
  --name FinanzAlpha ^
  --onefile ^
  --windowed ^
  --icon="%ICON%" ^
  --add-data "%SCRIPT_DIR%web\templates;web\templates" ^
  --add-data "%SCRIPT_DIR%web\static;web\static" ^
  --add-data "%SCRIPT_DIR%CHANGELOG.md;." ^
  --hidden-import bcrypt ^
  --hidden-import markdown ^
  %SCRIPT_DIR%desktop_app.py


rem Überprüfe, ob PyInstaller erfolgreich war
if %ERRORLEVEL% neq 0 (
    echo ======================================
    echo ❌ BUILD FEHLGESCHLAGEN. Siehe PyInstaller-Ausgabe oben für Details.
    echo ======================================
    pause
    exit /b %ERRORLEVEL%
)

rem === EXE verschieben ===
echo Verschiebe erstellte EXE...
rem ... (Rest des Skripts bleibt gleich) ...

rem Überprüfe, ob PyInstaller erfolgreich war
if %ERRORLEVEL% neq 0 (
    echo ======================================
    echo ❌ BUILD FEHLGESCHLAGEN. Siehe PyInstaller-Ausgabe oben für Details.
    echo ======================================
    pause
    exit /b %ERRORLEVEL%
)

REM === EXE verschieben ===
echo Verschiebe erstellte EXE...
if exist "dist\%EXE_NAME%" (
    rem Stelle sicher, dass der Zielordner existiert, falls er oben nicht erstellt wurde (unwahrscheinlich)
    if not exist "%OUTDIR%" mkdir "%OUTDIR%"
    move /Y "dist\%EXE_NAME%" "%OUTDIR%\"
    echo ✅ EXE erfolgreich verschoben nach "%EXE_PATH%".
) else (
    echo ======================================
    echo ❌ FEHLER: Keine EXE gefunden in "dist\%EXE_NAME%". PyInstaller hat die Datei nicht erstellt.
    echo ======================================
    pause
    exit /b 1
)

rem --- Der Signierungs-Abschnitt wurde hier entfernt ---


echo.
echo ======================================
echo ✅ BUILD V%VERSION% ERFOLGREICH ABGESCHLOSSEN.
echo ======================================
echo Die fertige Anwendung findest du hier:
echo "%EXE_PATH%"
echo.

rem Halte das Fenster offen, damit der Benutzer die Meldungen lesen kann
pause

rem Beende das lokale Environment der Batchdatei
endlocal