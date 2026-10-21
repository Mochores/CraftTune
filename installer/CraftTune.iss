#define MyAppName "CraftTune-V1.0.0"
#define MyAppVersion "1.0.0"
#define MyAppVerName "CraftTune-V1.0.0 模组参数工坊"
#define MyAppPublisher "CraftTune"
#define MyAppExeName "CraftTune.exe"
#define MyAppId "{{8A2F1D8E-4B5C-4F2A-9C7E-1D3B5A7C9E21}"
#define MyProjectRoot AddBackslash(SourcePath) + ".."

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppVerName}
AppPublisher={#MyAppPublisher}
AppCopyright=CraftTune
DefaultDirName={localappdata}\Programs\CraftTune
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
DisableWelcomePage=no
PrivilegesRequired=lowest
OutputDir={#MyProjectRoot}\installer_output
OutputBaseFilename=CraftTune-V1.0.0-Setup
SetupIconFile={#MyProjectRoot}\assets\app.ico
WizardImageFile=wizard.bmp
WizardSmallImageFile=wizard-small.bmp
WizardStyle=modern
WizardImageStretch=no
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
LZMAUseSeparateProcess=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
UsePreviousAppDir=yes
UsePreviousTasks=yes
AllowNoIcons=yes
VersionInfoVersion=1.0.0.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppVerName} 安装程序
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
VersionInfoCopyright=CraftTune
LanguageDetectionMethod=none
ShowLanguageDialog=no

[Languages]
Name: "chinesesimplified"; MessagesFile: "ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务："; Flags: checkedonce

[Files]
Source: "{#MyProjectRoot}\dist\CraftTune-V1.0.0.exe"; DestDir: "{app}"; DestName: "{#MyAppExeName}"; Flags: ignoreversion
Source: "{#MyProjectRoot}\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#MyProjectRoot}\RELEASE_NOTES-V1.0.0.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#MyProjectRoot}\docs\native_home.png"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "{#MyProjectRoot}\docs\native_mods.png"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "{#MyProjectRoot}\docs\native_editor.png"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "{#MyProjectRoot}\docs\installer.png"; DestDir: "{app}\docs"; Flags: ignoreversion

[Icons]
Name: "{group}\CraftTune-V1.0.0"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载 CraftTune-V1.0.0"; Filename: "{uninstallexe}"
Name: "{autodesktop}\CraftTune-V1.0.0"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动 CraftTune-V1.0.0"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\data\cache"
Type: files; Name: "{app}\data\crafttune.log"
Type: files; Name: "{app}\data\crafttune-error.log"

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;
