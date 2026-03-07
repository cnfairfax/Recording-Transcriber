# recording_transcriber.spec
# ───────────────────────────────────────────────────────────────────────────────
# PyInstaller spec for Recording Transcriber
#
# Produces TWO executables inside a single dist/ folder:
#   dist/Recording Transcriber/
#     Recording Transcriber.exe   – main windowed application
#     download_model.exe          – console helper; used by Inno Setup to pull
#                                   the user-selected Whisper model at install time
#
# Usage
# -----
#   From the repo root:
#     .venv\Scripts\python.exe -m PyInstaller installer\recording_transcriber.spec --noconfirm
#
# Troubleshooting
# ---------------
#   OpenVINO plugin discovery  If Intel Arc inference fails in the bundled app,
#     check that openvino's plugins.xml and the GPU plugin DLL are collected.
#     Run the app from a terminal (set console=True temporarily) and look for
#     messages like "Failed to create plugin" in the openvino logs.
#
#   ctranslate2 CUDA support  Requires the CUDA-enabled ctranslate2 wheel.
#     The CPU/OpenVINO wheels ship without CUDA runtime DLLs.
#
#   Model cache  Models are stored in %APPDATA%\Recording Transcriber\models\
#     and are NOT bundled inside the installer – download_model.exe fetches
#     them on first install (or you can ship a pre-downloaded model beside the
#     installer and copy it there in installer.iss).
# ───────────────────────────────────────────────────────────────────────────────

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

# ── Path helpers ────────────────────────────────────────────────────────────────
# SPECPATH is the directory that contains this spec file (i.e. installer/).
ROOT = str(Path(SPECPATH).parent)          # repo root
ICON = os.path.join(ROOT, "assets", "icon.ico")
icon_arg = ICON if os.path.isfile(ICON) else None

# ── Collect runtime packages ────────────────────────────────────────────────────
# collect_all gathers Python source, data files *and* binary extensions for a
# package.  We run it for each large package and merge the results.
_shared_datas     = []
_shared_binaries  = []
_shared_hidden    = []

# onnxruntime: collect data + binaries ONLY (no hidden imports).
# collect_all('onnxruntime') emits hundreds of 'onnxruntime.transformers.*'
# hidden-import entries that don't exist in the installed wheel, which causes
# PyInstaller to exit with code 1.  Additionally, importing onnxruntime in
# PyInstaller's isolated analysis subprocess triggers a Windows access violation
# on Python 3.13.  So we bypass both problems: grab its files manually and add
# 'onnxruntime' to excludes in every Analysis block.
try:
    _ort_datas    = collect_data_files("onnxruntime", include_py_files=False)
    _ort_binaries = []
    import glob, os as _os
    _ort_root = None
    try:
        import importlib.util as _ilu
        _spec = _ilu.find_spec("onnxruntime")
        if _spec and _spec.submodule_search_locations:
            _ort_root = list(_spec.submodule_search_locations)[0]
    except Exception:
        pass
    if _ort_root:
        for _pat in ("*.dll", "*.so", "*.pyd", "capi/*.dll", "capi/*.pyd"):
            for _f in glob.glob(_os.path.join(_ort_root, _pat)):
                _ort_binaries.append((_f, _os.path.join("onnxruntime", _os.path.dirname(_os.path.relpath(_f, _ort_root)))))
    _shared_datas    += _ort_datas
    _shared_binaries += _ort_binaries
except Exception as _e:
    print(f"WARNING: could not collect onnxruntime files: {_e}")

for pkg in (
    "faster_whisper",
    "ctranslate2",
    "openvino",
    "huggingface_hub",
    "tokenizers",
):
    d, b, h = collect_all(pkg)
    _shared_datas    += d
    _shared_binaries += b
    _shared_hidden   += h

# huggingface_hub needs a few extra submodules to function at runtime
_shared_hidden += collect_submodules("huggingface_hub")
_shared_hidden += collect_submodules("filelock")

# av / soundfile may be pulled in transitively by faster-whisper
for pkg in ("av", "soundfile"):
    try:
        d, b, h = collect_all(pkg)
        _shared_datas    += d
        _shared_binaries += b
        _shared_hidden   += h
    except Exception:
        pass  # optional; skip if not installed


# ── Analysis: main application ──────────────────────────────────────────────────
main_a = Analysis(
    [os.path.join(ROOT, "app.py")],
    pathex=[ROOT],
    binaries=_shared_binaries,
    datas=_shared_datas,
    hiddenimports=_shared_hidden + [
        "src.main_window",
        "src.worker",
        "src.model_manager",
        "PyQt6.QtCore",
        "PyQt6.QtWidgets",
        "PyQt6.QtGui",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Strip packages definitely not needed:
        "torch", "torchvision", "torchaudio",
        "tensorflow", "keras",
        "matplotlib", "notebook", "IPython",
        "numpy.distutils",
        # Prevent analysis-time import crash (files still bundled via datas/binaries above):
        "onnxruntime",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)

# ── Analysis: download_model helper ─────────────────────────────────────────────
dl_a = Analysis(
    [os.path.join(ROOT, "installer", "download_model.py")],
    pathex=[ROOT],
    binaries=_shared_binaries,
    datas=_shared_datas,
    hiddenimports=_shared_hidden + [
        "src.model_manager",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "torch", "torchvision",
        "tensorflow", "keras",
        "matplotlib", "PyQt6",
        # Prevent analysis-time import crash (files still bundled via datas/binaries above):
        "onnxruntime",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)

# ── PYZ archives ────────────────────────────────────────────────────────────────
main_pyz = PYZ(main_a.pure)
dl_pyz   = PYZ(dl_a.pure)

# ── EXE: Recording Transcriber ──────────────────────────────────────────────────
main_exe = EXE(
    main_pyz,
    main_a.scripts,
    [],
    exclude_binaries=True,     # binaries go into COLLECT (shared with downloader)
    name="Recording Transcriber",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                 # UPX can cause false AV positives; keep off
    console=False,             # windowed — no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=icon_arg,
    version=os.path.join(ROOT, "installer", "version_info.txt") if
        os.path.isfile(os.path.join(ROOT, "installer", "version_info.txt")) else None,
)

# ── EXE: download_model helper ──────────────────────────────────────────────────
dl_exe = EXE(
    dl_pyz,
    dl_a.scripts,
    [],
    exclude_binaries=True,
    name="download_model",
    debug=False,
    strip=False,
    upx=False,
    console=True,              # console window shows tqdm download progress
    icon=None,
)

# ── COLLECT: merge both EXEs into one dist folder ───────────────────────────────
# PyInstaller deduplicates binaries/datas across the two analyses automatically.
coll = COLLECT(
    main_exe,
    main_a.binaries,
    main_a.zipfiles,
    main_a.datas,
    dl_exe,
    dl_a.binaries,
    dl_a.zipfiles,
    dl_a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Recording Transcriber",   # → dist/Recording Transcriber/
)
