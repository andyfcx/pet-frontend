; Inno Setup script for Biometeo Frontend
; Build with: iscc /DAppVersion=x.y.z installer.iss

#ifndef AppVersion
  #define AppVersion "0.1.1"
#endif

[Setup]
AppName=Biometeo Frontend
AppVersion={#AppVersion}
AppPublisher=Biometeo
DefaultDirName={autopf}\Biometeo Frontend
DefaultGroupName=Biometeo Frontend
OutputDir=dist
OutputBaseFilename=Biometeo-Frontend-{#AppVersion}-windows-x64-setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64

[Files]
Source: "dist\Biometeo Frontend.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Biometeo Frontend"; Filename: "{app}\Biometeo Frontend.exe"
Name: "{commondesktop}\Biometeo Frontend"; Filename: "{app}\Biometeo Frontend.exe"

[Run]
Filename: "{app}\Biometeo Frontend.exe"; Description: "Launch Biometeo Frontend"; Flags: nowait postinstall skipifsilent
