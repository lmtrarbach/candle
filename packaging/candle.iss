; Inno Setup script: builds the Windows installer from the PyInstaller output.
;   iscc /DAppVersion=0.1.0 packaging\candle.iss
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{8C5E7B1A-3F2D-4C59-9E61-CA4D1E0B7A21}
AppName=Candle
AppVersion={#AppVersion}
AppPublisher=Candle
DefaultDirName={autopf}\Candle
DefaultGroupName=Candle
UninstallDisplayIcon={app}\Candle.exe
SetupIconFile=candle.ico
OutputDir=..\dist
OutputBaseFilename=Candle-{#AppVersion}-windows-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ChangesAssociations=yes
PrivilegesRequiredOverridesAllowed=dialog

[Files]
Source: "..\dist\Candle\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\Candle"; Filename: "{app}\Candle.exe"
Name: "{autodesktop}\Candle"; Filename: "{app}\Candle.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Registry]
Root: HKA; Subkey: "Software\Classes\.candle"; ValueType: string; ValueData: "Candle.Project"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\Candle.Project"; ValueType: string; ValueData: "Candle project"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Candle.Project\DefaultIcon"; ValueType: string; ValueData: "{app}\Candle.exe,0"
Root: HKA; Subkey: "Software\Classes\Candle.Project\shell\open\command"; ValueType: string; ValueData: """{app}\Candle.exe"" ""%1"""

[Run]
Filename: "{app}\Candle.exe"; Description: "Launch Candle"; Flags: nowait postinstall skipifsilent
