; Inno Setup script. Run installers/build.py instead of calling iscc by hand.
[Setup]
AppName=Katib
AppVersion={#Version}
AppPublisher=M. Abdullah K. Mughal
AppPublisherURL=https://github.com/MergenEnBilge/Katib
DefaultDirName={autopf}\Katib
DefaultGroupName=Katib
OutputDir=..\..\dist\installers
OutputBaseFilename=Katib-{#Version}-windows-setup
SetupIconFile=..\desktop\icon.ico
Compression=lzma2
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\Katib.exe
; A server left running from an earlier version holds its files open; ask before replacing them.
CloseApplications=yes

[Files]
Source: "..\..\dist\Katib\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\Katib"; Filename: "{app}\Katib.exe"
Name: "{group}\Katib Server"; Filename: "{app}\KatibServer.exe"; Comment: "Keep Katib running for your other devices, with an icon in the tray"
Name: "{autodesktop}\Katib"; Filename: "{app}\Katib.exe"

[Registry]
; "Start when I sign in", if it was ever turned on, goes with the program.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "Katib Server"; Flags: dontcreatekey uninsdeletevalue

[Run]
Filename: "{app}\Katib.exe"; Description: "Start Katib"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Stop the background server before its files are removed.
Filename: "{app}\KatibServer.exe"; Parameters: "--stop"; Flags: runhidden waituntilterminated; RunOnceId: "StopServer"
