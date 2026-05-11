#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef OutputBaseName
  #define OutputBaseName "ScanWatcher_Setup_v" + AppVersion
#endif

[Setup]
AppName=Scan Watcher
AppVersion={#AppVersion}
AppVerName=Scan Watcher {#AppVersion}
AppPublisher=Nova Network
AppPublisherURL=https://www.nova-network.de
AppSupportURL=https://github.com/Abgehnxyz/ScanWatcher
AppCopyright=Copyright (C) 2026 Nova Network
DefaultDirName={autopf}\Nova Network\Scan Watcher
DefaultGroupName=Nova Network\Scan Watcher
OutputBaseFilename={#OutputBaseName}
OutputDir=..\dist\installer
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\ScanWatcher.exe
SetupIconFile=..\assets\icon.ico
WizardSmallImageFile=..\assets\icon.png
DisableWelcomePage=no
DisableProgramGroupPage=yes
ShowLanguageDialog=no
CloseApplications=yes

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Messages]
WelcomeLabel1=Willkommen beim Scan Watcher Setup
WelcomeLabel2=Scan Watcher wird jetzt auf Ihrem Computer installiert.%n%nScan Watcher erkennt automatisch neue Scandokumente, benennt sie per OCR sinnvoll um und legt sie im gewünschten Ordner ab.%n%nScan Watcher ist kostenlos und Open Source. Wenn Ihnen das Tool hilft, freuen wir uns über einen Kaffee auf Ko-fi: ko-fi.com/novanetwork%n%nEin Produkt von Nova Network.

[Tasks]
Name: "desktopicon"; Description: "Desktop-Verknüpfung erstellen"; GroupDescription: "Zusätzliche Symbole:"
Name: "autostart"; Description: "Scan Watcher automatisch mit Windows starten"; GroupDescription: "Autostart:"; Flags: checkedonce

[Files]
Source: "..\dist\ScanWatcher\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\assets\icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Scan Watcher"; Filename: "{app}\ScanWatcher.exe"; IconFilename: "{app}\icon.ico"
Name: "{commondesktop}\Scan Watcher"; Filename: "{app}\ScanWatcher.exe"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon
Name: "{group}\Deinstallieren"; Filename: "{uninstallexe}"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "ScanWatcher"; ValueData: """{app}\ScanWatcher.exe"""; Flags: uninsdeletevalue; Tasks: autostart

[UninstallDelete]
Type: files; Name: "{app}\*.log"

[UninstallRun]
Filename: "powershell.exe"; \
  Parameters: "-NonInteractive -WindowStyle Hidden -Command ""$id = Get-Content -ErrorAction SilentlyContinue -Path ([IO.Path]::Combine($env:APPDATA,'ScanWatcher','install_id')); if ($id) {{ Invoke-RestMethod -Method Post -Uri 'https://ops.abgehn.xyz/api/scanwatcher/event' -ContentType 'application/json' -Body ('{{""install_id"":""' + $id.Trim() + '"",""event"":""uninstall""}}') -ErrorAction SilentlyContinue }}"""; \
  Flags: runhidden

[Run]
Filename: "{app}\ScanWatcher.exe"; Description: "Scan Watcher jetzt starten"; Flags: nowait postinstall skipifsilent
