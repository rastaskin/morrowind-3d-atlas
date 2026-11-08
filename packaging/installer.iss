#ifndef AppVersion
  #define AppVersion "1.3.1"
#endif
[Setup]
AppId={{62BF4218-A898-47E5-9A36-B60E56A98A1F}
AppName=Morrowind 3D Atlas
AppVersion={#AppVersion}
AppPublisher=Morrowind Atlas Contributors
AppPublisherURL=https://github.com/rastaskin/morrowind-3d-atlas
DefaultDirName={localappdata}\Programs\Morrowind3DAtlas
DefaultGroupName=Morrowind 3D Atlas
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\release
OutputBaseFilename=Morrowind-3D-Atlas-Setup-{#AppVersion}-win-x64
SetupIconFile=atlas.ico
UninstallDisplayIcon={app}\MorrowindAtlas.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
LicenseFile=..\LICENSE
CloseApplications=yes
AppMutex=Morrowind3DAtlasDesktop
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
[Files]
Source: "..\dist\MorrowindAtlas\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\Morrowind 3D Atlas"; Filename: "{app}\MorrowindAtlas.exe"
Name: "{autodesktop}\Morrowind 3D Atlas"; Filename: "{app}\MorrowindAtlas.exe"; Tasks: desktopicon
[Run]
Filename: "{app}\MorrowindAtlas.exe"; Description: "{cm:LaunchProgram,Morrowind 3D Atlas}"; Flags: nowait postinstall skipifsilent
