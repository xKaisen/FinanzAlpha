; -----------------------------------------------
; Inno Setup Script für FinanzAlpha v0.1.1
; Kopiert das komplette dist\FinanzAlpha_0_1_1-Verzeichnis
; -----------------------------------------------

#define AppName      "FinanzAlpha"
#define AppVersion   "0.1.1"
#define SourceDir    "..\dist\FinanzAlpha_0_1_1"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={pf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=installer_output
OutputBaseFilename={#AppName}_Setup_{#AppVersion}
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Files]
; Recursiv alles aus dem One-Dir-Bundle kopieren:
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
; Desktop-Shortcut
Name: "{autodesktop}\{#AppName} v{#AppVersion}"; Filename: "{app}\{#AppName}_0_1_1.exe"
; Startmenü-Shortcut
Name: "{group}\{#AppName} v{#AppVersion}"; Filename: "{app}\{#AppName}_0_1_1.exe"

[Run]
; Nach der Installation die App starten (WorkingDir stellt sicher, dass CWD stimmt)
Filename: "{app}\{#AppName}_0_1_1.exe"; Description: "{cm:LaunchProgram,{#AppName}}"; \
    WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent
