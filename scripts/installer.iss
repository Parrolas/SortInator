; Payload is replaceable by the updater; uninstall metadata stays in its parent.
#ifndef AppVersion
  #error AppVersion is required
#endif
#ifndef PayloadDir
  #error PayloadDir is required
#endif

[Setup]
AppId=SortInator
AppName=SortInator
AppVersion={#AppVersion}
AppPublisher=José Parrolas
AppPublisherURL=https://github.com/Parrolas/SortInator
DefaultDirName={localappdata}\Programs\SortInator
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.19041
AppMutex=Local\Parrolas.SortInator.Running
CloseApplications=no
RestartApplications=no
UninstallDisplayIcon={app}\app\SortInator.exe
OutputDir={#OutputDir}
OutputBaseFilename=SortInator-{#AppVersion}-Setup
SetupIconFile={#PayloadDir}\_internal\assets\icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
#ifdef SignedBuild
SignTool=organizador
SignedUninstaller=yes
#endif

[Languages]
Name: "portuguese"; MessagesFile: "compiler:Languages\Portuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; Flags: unchecked

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}\app"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\SortInator"; Filename: "{app}\app\SortInator.exe"; AppUserModelID: "Parrolas.SortInator"
Name: "{autodesktop}\SortInator"; Filename: "{app}\app\SortInator.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\app\SortInator.exe"; Parameters: "--register-integration"; Flags: runhidden waituntilterminated
Filename: "{app}\app\SortInator.exe"; Description: "{cm:LaunchProgram,SortInator}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\app\SortInator.exe"; Parameters: "--unregister-integration"; RunOnceId: "UnregisterIntegration"; Flags: runhidden waituntilterminated skipifdoesntexist

[Code]
var
  ManagedFiles: TArrayOfString;

function InitializeSetup(): Boolean;
var
  ExistingVersion: String;
  PreviousNumber, CandidateNumber: Int64;
begin
  Result := True;
  if RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\SortInator_is1', 'DisplayVersion', ExistingVersion) then
    if StrToVersion(ExistingVersion, PreviousNumber) and
       StrToVersion('{#AppVersion}', CandidateNumber) and
       (ComparePackedVersion(PreviousNumber, CandidateNumber) > 0) then
    begin
      MsgBox(CustomMessage('NewerInstalled'), mbError, MB_OK);
      Result := False;
    end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Index: Integer;
  RelativePath, Target, RuntimeRoot, Parent: String;
begin
  RuntimeRoot := AddBackslash(ExpandConstant('{app}\app'));
  if CurUninstallStep = usUninstall then
    LoadStringsFromFile(RuntimeRoot + 'runtime-files.txt', ManagedFiles);
  if CurUninstallStep = usPostUninstall then
  begin
    for Index := 0 to GetArrayLength(ManagedFiles) - 1 do
    begin
      RelativePath := ManagedFiles[Index];
      if (RelativePath <> '') and (Pos('..', RelativePath) = 0) and
         (Pos(':', RelativePath) = 0) and (Copy(RelativePath, 1, 1) <> '\') and
         (Copy(RelativePath, 1, 1) <> '/') then
      begin
        Target := ExpandFileName(RuntimeRoot + RelativePath);
        if CompareText(Copy(Target, 1, Length(RuntimeRoot)), RuntimeRoot) = 0 then
        begin
          DeleteFile(Target);
          Parent := ExtractFileDir(Target);
          while Length(Parent) >= Length(RuntimeRoot) do
          begin
            RemoveDir(Parent);
            Parent := ExtractFileDir(Parent);
          end;
        end;
      end;
    end;
    RemoveDir(RemoveBackslashUnlessRoot(RuntimeRoot));
    RemoveDir(ExpandConstant('{app}'));
  end;
end;

[CustomMessages]
portuguese.NewerInstalled=Já está instalada uma versão mais recente do SortInator.
english.NewerInstalled=A newer version of SortInator is already installed.
spanish.NewerInstalled=Ya hay instalada una versión más reciente de SortInator.
french.NewerInstalled=Une version plus récente de SortInator est déjà installée.
