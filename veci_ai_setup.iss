; =============================================================================
; Script de Inno Setup para VECI AI - Sistema POS e Inventario Inteligente
; Compila la salida Onedir de PyInstaller (dist\VECI_AI\*) en Veci_AI_Setup.exe
; =============================================================================

#define MyAppName "VECI AI"
#define MyAppVersion "1.0.4"
#define MyAppPublisher "VECI AI Technologies"
#define MyAppURL "https://github.com/veciai"
#define MyAppExeName "VECI_AI.exe"

[Setup]
; Identificador único de la aplicación para registro y desinstalación en Panel de Control
AppId={{8D4F62C1-9A2E-4C11-B83D-7E91C5042A10}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Directorio de instalación por defecto y grupo de Menú de Inicio
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Flujo de Asistente Estándar (Bienvenido > Directorio > Accesos Directos > Listo para Instalar)
WizardStyle=modern
DisableWelcomePage=no
DisableDirPage=no
DisableProgramGroupPage=no
DisableReadyPage=no

; Ícono del Instalador y del Panel de Control (Agregar o quitar programas)
SetupIconFile=build_assets\veci_ai_icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} v{#MyAppVersion}
CreateUninstallRegKey=yes

; Archivo de salida final: installer_output\Veci_AI_Setup_v1.0.1.exe
OutputDir=installer_output
OutputBaseFilename=Veci_AI_Setup_v{#MyAppVersion}
Compression=lzma2/fast
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Empaqueta todo el directorio compilado por PyInstaller (modo Onedir)
Source: "dist\VECI_AI\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\VECI_AI\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Acceso directo en el Menú de Inicio
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\build_assets\veci_ai_icon.ico"; WorkingDir: "{app}"; Comment: "Sistema de Inventario y Facturación POS VECI AI"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
; Acceso directo automático en el Escritorio
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\build_assets\veci_ai_icon.ico"; WorkingDir: "{app}"; Tasks: desktopicon; Comment: "Iniciar VECI AI"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Limpieza completa del directorio de la aplicación al desinstalar desde el Panel de Control
Type: filesandordirs; Name: "{app}"
