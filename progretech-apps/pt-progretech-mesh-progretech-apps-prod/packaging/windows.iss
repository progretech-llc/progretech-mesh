#ifndef AppVersion
  #define AppVersion "0.1.1"
#endif
[Setup]
AppId=ProgreTech.MeshOffline
AppName=Mesh Offline
AppVersion={#AppVersion}
AppPublisher=ProgreTech
DefaultDirName={localappdata}\Programs\ProgreTech\MeshOffline
DefaultGroupName=Mesh Offline
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist\releases
OutputBaseFilename=mesh-offline-{#AppVersion}-windows-setup
Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={app}\MeshOffline.exe
[Files]
Source: "..\dist\MeshOffline\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\Mesh Offline"; Filename: "{app}\MeshOffline.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Mesh Offline"; Filename: "{app}\MeshOffline.exe"; WorkingDir: "{app}"
[Run]
Filename: "{app}\MeshOffline.exe"; Description: "Launch Mesh Offline"; Flags: nowait postinstall skipifsilent
