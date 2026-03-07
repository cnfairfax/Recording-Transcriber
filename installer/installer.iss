; ──────────────────────────────────────────────────────────────────────────────
; installer.iss  –  Inno Setup 6 script for Recording Transcriber
;
; Build prerequisites
; -------------------
;   1. Run PyInstaller first:
;        .venv\Scripts\python.exe -m PyInstaller installer\recording_transcriber.spec --noconfirm
;      This produces:  dist\Recording Transcriber\
;
;   2. Install Inno Setup 6: https://jrsoftware.org/isdl.php
;
;   3. Compile this script:
;        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\installer.iss
;      (or run installer\build.ps1 which does both steps)
;
;   Output: dist\installer\RecordingTranscriber-1.0.0-Setup.exe
;
; Model selection
; ---------------
;   The installer presents a custom wizard page where the user picks one of
;   six Whisper model sizes.  After the app files are placed, download_model.exe
;   is launched in a console window so the user can see download progress.
;   If the user unchecks "Download now", the model is fetched automatically
;   on first use by the app instead (internet still required at that point).
;
;   Models are stored in:
;     %APPDATA%\Recording Transcriber\models\
;   and survive app upgrades / reinstalls.
; ──────────────────────────────────────────────────────────────────────────────

#define AppName      "Recording Transcriber"
#define AppVersion   "1.0.0"
#define AppPublisher "cfair"
#define AppExe       "Recording Transcriber.exe"
#define DistDir      "..\dist\Recording Transcriber"

[Setup]
; NOTE: Regenerate AppId with Tools > Generate GUID if you fork this project.
AppId={{3F8A2B1C-D4E5-4F60-9A7B-C8D9E0F12345}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppVerName={#AppName} {#AppVersion}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=..\dist\installer
OutputBaseFilename=RecordingTranscriber-{#AppVersion}-Setup
SetupIconFile=..\assets\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
; Minimum Windows 10
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}";                       Filename: "{app}\{#AppExe}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#AppName}";               Filename: "{app}\{#AppExe}"; Tasks: desktopicon

; ── Post-install: download the selected Whisper model ─────────────────────────
; download_model.exe is a console app that prints tqdm progress to its window,
; so we do NOT pass 'runhidden'.  The window title shows "Downloading…".
; 'Check: ShouldDownloadModel' skips this step when the user unchecked the box.
[Run]
Filename: "{app}\download_model.exe"; \
  Parameters: "--model {code:GetSelectedModel}"; \
  WorkingDir: "{app}"; \
  StatusMsg: "Downloading Whisper model '{code:GetSelectedModel}' — this may take several minutes…"; \
  Description: "Download the selected Whisper model"; \
  Check: ShouldDownloadModel; \
  Flags: waituntilterminated

; Also offer to launch the app after installation
Filename: "{app}\{#AppExe}"; \
  Description: "{cm:LaunchProgram,{#AppName}}"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Remove the install directory (but NOT the user's model cache in %APPDATA%)
Type: filesandordirs; Name: "{app}"

; ──────────────────────────────────────────────────────────────────────────────
; Pascal Script
; ──────────────────────────────────────────────────────────────────────────────
[Code]

{ ── Model catalogue (must mirror src/model_manager.py MODELS list) ─────────── }
const
  MODEL_COUNT = 6;

  MODEL_NAMES: array[0..5] of String = (
    'tiny', 'base', 'small', 'medium', 'large-v2', 'large-v3'
  );

  MODEL_DISPLAY: array[0..5] of String = (
    'Tiny       ~75 MB   — Fastest, very basic accuracy',
    'Base       ~145 MB  — Very fast, basic accuracy',
    'Small      ~466 MB  — Good balance of speed and accuracy',
    'Medium     ~1.5 GB  — High accuracy, moderate speed',
    'Large v2   ~3.1 GB  — Very high accuracy',
    'Large v3   ~3.1 GB  — Best overall accuracy  (recommended)'
  );

  MODEL_DETAIL: array[0..5] of String = (
    'Good for quick tests on modest hardware.  Accuracy is noticeably limited.',
    'Suitable for clear speech and short recordings.',
    'Recommended starting point for most users.  Works well on CPU.',
    'High-quality results.  Needs roughly 4 GB of RAM during inference.  A GPU is helpful.',
    'Near human-level accuracy.  Best run on a dedicated GPU (Intel Arc or NVIDIA).',
    'The most accurate model available.  Same weights as Large v2 with improved training — recommended for Intel Arc A-series and NVIDIA GPUs.'
  );

  DEFAULT_MODEL_IDX = 5;   { large-v3 }

{ ── Page controls ─────────────────────────────────────────────────────────── }
var
  ModelPage:      TWizardPage;
  ModelCombo:     TNewComboBox;
  ModelDetail:    TNewStaticText;
  DownloadNow:    TNewCheckBox;
  SkipNote:       TNewStaticText;

{ ── Utility: fill in the detail label for the currently selected model ─────── }
procedure UpdateModelDetail;
begin
  ModelDetail.Caption := MODEL_DETAIL[ModelCombo.ItemIndex];
end;

{ ── Combo OnChange event ───────────────────────────────────────────────────── }
procedure ModelComboChange(Sender: TObject);
begin
  UpdateModelDetail;
end;

{ ── DownloadNow OnClick event — show/hide the skip note ───────────────────── }
procedure DownloadNowClick(Sender: TObject);
begin
  SkipNote.Visible := not DownloadNow.Checked;
end;

{ ── Create custom wizard page ─────────────────────────────────────────────── }
procedure InitializeWizard;
var
  ComboLabel: TNewStaticText;
  i: Integer;
  SurfW: Integer;
begin
  { Page appears after the install-directory selection page }
  ModelPage := CreateCustomPage(
    wpSelectDir,
    'Whisper Model',
    'Choose the speech recognition model to install.'
  );

  SurfW := ModelPage.SurfaceWidth;

  { Label above the combo }
  ComboLabel := TNewStaticText.Create(ModelPage);
  ComboLabel.Parent  := ModelPage.Surface;
  ComboLabel.Left    := 0;
  ComboLabel.Top     := 0;
  ComboLabel.Width   := SurfW;
  ComboLabel.Caption := 'Model size:';
  ComboLabel.AutoSize := True;

  { Combo box – model selector }
  ModelCombo := TNewComboBox.Create(ModelPage);
  ModelCombo.Parent   := ModelPage.Surface;
  ModelCombo.Style    := csDropDownList;
  ModelCombo.Left     := 0;
  ModelCombo.Top      := 20;
  ModelCombo.Width    := SurfW;
  for i := 0 to MODEL_COUNT - 1 do
    ModelCombo.Items.Add(MODEL_DISPLAY[i]);
  ModelCombo.ItemIndex := DEFAULT_MODEL_IDX;
  ModelCombo.OnChange  := @ModelComboChange;

  { Detail label – updates when selection changes }
  ModelDetail := TNewStaticText.Create(ModelPage);
  ModelDetail.Parent  := ModelPage.Surface;
  ModelDetail.Left    := 0;
  ModelDetail.Top     := 54;
  ModelDetail.Width   := SurfW;
  ModelDetail.WordWrap := True;
  ModelDetail.AutoSize := True;
  UpdateModelDetail;

  { Checkbox: download during install }
  DownloadNow := TNewCheckBox.Create(ModelPage);
  DownloadNow.Parent   := ModelPage.Surface;
  DownloadNow.Left     := 0;
  DownloadNow.Top      := 138;
  DownloadNow.Width    := SurfW;
  DownloadNow.Caption  := 'Download model now  (internet connection required)';
  DownloadNow.Checked  := True;
  DownloadNow.OnClick  := @DownloadNowClick;

  { Note shown when "download now" is unchecked }
  SkipNote := TNewStaticText.Create(ModelPage);
  SkipNote.Parent   := ModelPage.Surface;
  SkipNote.Left     := 16;
  SkipNote.Top      := 162;
  SkipNote.Width    := SurfW - 16;
  SkipNote.WordWrap := True;
  SkipNote.AutoSize := True;
  SkipNote.Caption  :=
    'The model will be downloaded automatically the first time the app transcribes a file. ' +
    'You can also run  download_model.exe --model <name>  from the installation folder at any time.';
  SkipNote.Visible := False;
end;

{ ── Called by [Run] Parameters to supply the chosen model name ─────────────── }
function GetSelectedModel(Param: String): String;
begin
  Result := MODEL_NAMES[ModelCombo.ItemIndex];
end;

{ ── Called by [Run] Check to decide whether to run the downloader ─────────── }
function ShouldDownloadModel(Param: String): Boolean;
begin
  Result := DownloadNow.Checked;
end;
