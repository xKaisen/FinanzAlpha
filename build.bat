@echo off
setlocal

REM === VERSION DEFINIEREN ===
set VERSION=0.1.5
set OUTDIR=dist\FinanzApp_%VERSION%
set ICON=finanz_icon.ico
set SIGNTOOL="C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64\signtool.exe"
set EXE_NAME=FinanzAlpha.exe
set EXE_PATH=%OUTDIR%\%EXE_NAME%

echo ======================================
echo 🚧 Baue FinanzAlpha v%VERSION%...
echo ======================================

REM === Ordner anlegen ===
mkdir %OUTDIR%

REM === PyInstaller Build ===
pyinstaller ^
  --name FinanzAlpha ^
  --onefile ^
  --noconsole ^
  --icon=%ICON% ^
  --add-data "changelog.json;." ^
  --add-data "finanz_app.db;." ^
  --hidden-import bcrypt ^
  --collect-all PySide6 ^
  main.py

IF %ERRORLEVEL% NEQ 0 (
    echo ❌ Build fehlgeschlagen.
    pause
    exit /b %ERRORLEVEL%
)

REM === EXE verschieben ===
move dist\%EXE_NAME% %EXE_PATH%

REM === Signieren, falls signtool vorhanden ===
IF EXIST %SIGNTOOL% (
    echo ======================================
    echo 🔐 Signiere .exe mit signtool
    echo ======================================

    %SIGNTOOL% sign ^
        /fd SHA256 ^
        /a ^
        /td SHA256 ^
        /tr http://timestamp.digicert.com ^
        /v ^
        "%EXE_PATH%"

    IF %ERRORLEVEL% EQU 0 (
        echo ✅ Signierung erfolgreich abgeschlossen.
    ) ELSE (
        echo ⚠️  Signierung fehlgeschlagen – .exe bleibt unsigniert.
    )
) ELSE (
    echo ⚠️  signtool.exe nicht gefunden – überspringe Signierung.
)

echo.
echo ✅ Build abgeschlossen: %EXE_PATH%
pause
