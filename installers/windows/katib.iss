; Inno Setup script. Run installers/build.py instead of calling iscc by hand.
[Setup]
AppName=Katib
AppVersion={#Version}
DefaultDirName={autopf}\Katib
DefaultGroupName=Katib
OutputDir=..\..\dist\installers
OutputBaseFilename=Katib-{#Version}-windows-setup
SetupIconFile=..\desktop\icon.ico
Compression=lzma2
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\Katib.exe

[Files]
Source: "..\..\dist\Katib\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\Katib"; Filename: "{app}\Katib.exe"
Name: "{autodesktop}\Katib"; Filename: "{app}\Katib.exe"

[Run]
Filename: "{app}\Katib.exe"; Description: "Start Katib"; Flags: nowait postinstall skipifsilent
