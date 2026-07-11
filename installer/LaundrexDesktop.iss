#define MyAppName "Laundrex Desktop"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Deedarian Software Solutions"
#define MyAppExeName "LaundrexDesktop.exe"
#define MyAppFolder "LaundrexDesktop"

[Setup]
AppId={{6B6D0C90-6A9D-4D10-9C14-3AEE7D66E2B4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\LaundrexDesktop
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=Output2
OutputBaseFilename=LaundrexDesktopSetup_v{#MyAppVersion}_r2
SetupIconFile=..\static\assets\favicon.ico
Compression=zip
SolidCompression=no
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Installer
VersionInfoCopyright=Developed by {#MyAppPublisher}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "..\dist\{#MyAppFolder}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__\*,*.pyc,*.pyo,*.log,*.tmp,.pytest_cache\*,.mypy_cache\*"
Source: "..\manage.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\.env"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\apps\*"; DestDir: "{app}\apps"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__\*,*.pyc,*.pyo,*.log,*.tmp,.pytest_cache\*,.mypy_cache\*"
Source: "..\laundrex\*"; DestDir: "{app}\laundrex"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__\*,*.pyc,*.pyo,*.log,*.tmp,.pytest_cache\*,.mypy_cache\*"
Source: "..\desktop_app\*"; DestDir: "{app}\desktop_app"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__\*,*.pyc,*.pyo,*.log,*.tmp,.pytest_cache\*,.mypy_cache\*"
Source: "..\templates\*"; DestDir: "{app}\templates"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__\*,*.pyc,*.pyo,*.log,*.tmp,.pytest_cache\*,.mypy_cache\*"
Source: "..\static\*"; DestDir: "{app}\static"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__\*,*.pyc,*.pyo,*.log,*.tmp,.pytest_cache\*,.mypy_cache\*"
Source: "..\locale\*"; DestDir: "{app}\locale"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__\*,*.pyc,*.pyo,*.log,*.tmp,.pytest_cache\*,.mypy_cache\*"
Source: "..\media\*"; DestDir: "{app}\media"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist; Excludes: "__pycache__\*,*.pyc,*.pyo,*.log,*.tmp,.pytest_cache\*,.mypy_cache\*"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
