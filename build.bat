@echo off
setlocal

REM === VERSION DEFINIEREN ===
set VERSION=1.0.1
set OUTDIR=dist\FinanzApp_%VERSION%
set ICON=finanz_icon.ico
set SIGNTOOL="C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64\signtool.exe"

REM Der Name, den PyInstaller erzeugt:
set EXE_NAME=FinanzAlpha.exe
set EXE_PATH=%OUTDIR%\%EXE_NAME%

echo ======================================
echo 🚧 Baue FinanzAlpha v%VERSION%...
echo ======================================

REM === Dist-Ordner anlegen ===
if not exist "%OUTDIR%" (
    mkdir "%OUTDIR%"
)

REM === PyInstaller Build ===
pyinstaller ^
  --name FinanzAlpha ^
  --onefile ^
  --noconsole ^
  --icon=%ICON% ^
  --hidden-import bcrypt ^
  --collect-all PySide6 ^
  start_offline.py

if %ERRORLEVEL% neq 0 (
    echo ❌ Build fehlgeschlagen.
    pause
    exit /b %ERRORLEVEL%
)

REM === EXE verschieben ===
if exist "dist\%EXE_NAME%" (
    move /Y "dist\%EXE_NAME%" "%EXE_PATH%"
) else (
    echo ❌ Keine EXE gefunden in dist\%EXE_NAME%.
    pause
    exit /b 1
)

REM === Signieren, falls signtool vorhanden ===
if exist %SIGNTOOL% (
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
    if %ERRORLEVEL% equ 0 (
        echo ✅ Signierung erfolgreich abgeschlossen.
    ) else (
        echo ⚠️  Signierung fehlgeschlagen – .exe bleibt unsigniert.
    )
) else (
    echo ⚠️  signtool.exe nicht gefunden – überspringe Signierung.
)

echo.
echo ✅ Build abgeschlossen: %EXE_PATH%
pause
