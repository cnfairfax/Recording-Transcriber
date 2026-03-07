"""
setup_env.py
------------
Verifies and installs the correct runtime dependencies for Recording Transcriber.

Backend: faster-whisper (CTranslate2)
GPU support priority: NVIDIA CUDA > Intel Arc (OpenVINO) > CPU

Usage:
    python setup_env.py            # verify and fix if needed
    python setup_env.py --check    # report only, do not install
    python setup_env.py --cuda     # also install CUDA-enabled ctranslate2
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from typing import Optional


FASTER_WHISPER_INDEX = "https://pypi.org/simple"
OPENVINO_PACKAGE     = "openvino"
BASE_PACKAGES        = ["faster-whisper", "openvino"]


def _run(cmd: list[str]) -> Optional[str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return r.stdout if r.returncode == 0 else None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


# ---------------------------------------------------------------------------
# Hardware detection
# ---------------------------------------------------------------------------

def detect_nvidia() -> bool:
    out = _run(["nvidia-smi"])
    return bool(out and re.search(r"CUDA\s+Version\s*:\s*\d+", out))


def detect_intel_arc() -> Optional[str]:
    """Return the Intel Arc adapter name if found, else None."""
    _ARC = re.compile(
        r"Intel.*Arc|Intel.*Data\s*Center.*GPU|Intel.*Alchemist|Intel.*Battlemage",
        re.IGNORECASE,
    )
    names: list[str] = []
    if sys.platform == "win32":
        out = _run([
            "powershell", "-NoProfile", "-Command",
            "Get-WmiObject Win32_VideoController | Select-Object -ExpandProperty Name",
        ])
        if out:
            names = [l.strip() for l in out.splitlines() if l.strip()]
    else:
        out = _run(["lspci"])
        if out:
            names = [l for l in out.splitlines() if re.search(r"VGA|3D|Display", l, re.I)]
    for name in names:
        if _ARC.search(name):
            return name
    return None


# ---------------------------------------------------------------------------
# Package checks
# ---------------------------------------------------------------------------

def _importable(pkg: str) -> bool:
    r = subprocess.run(
        [sys.executable, "-c", f"import {pkg}"],
        capture_output=True, timeout=30,
    )
    return r.returncode == 0


def _pip_install(packages: list[str], extra_index: Optional[str] = None) -> bool:
    cmd = [sys.executable, "-m", "pip", "install"] + packages
    if extra_index:
        cmd += ["--extra-index-url", extra_index]
    print(f"\n-> {' '.join(cmd)}\n")
    try:
        subprocess.check_call(cmd)
        return True
    except subprocess.CalledProcessError:
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Set up Recording Transcriber environment.")
    parser.add_argument("--check", action="store_true", help="Report status only, no installs")
    parser.add_argument("--cuda",  action="store_true", help="Install CUDA-enabled ctranslate2")
    args = parser.parse_args()

    print("=== Recording Transcriber  Environment Setup ===\n")

    #  Hardware detection 
    print("Detecting hardware ...")
    has_nvidia = detect_nvidia()
    intel_name = detect_intel_arc()

    if has_nvidia:
        print(f"  NVIDIA GPU detected (CUDA)")
    if intel_name:
        print(f"  Intel GPU detected: {intel_name}")
    if not has_nvidia and not intel_name:
        print("  No discrete GPU detected  will use CPU")

    print()

    #  Check faster-whisper 
    print("Checking faster-whisper ...", end=" ")
    fw_ok = _importable("faster_whisper")
    print("OK" if fw_ok else "NOT FOUND")

    #  Check OpenVINO (Intel Arc support) 
    print("Checking openvino ...", end=" ")
    ov_ok = _importable("openvino")
    print("OK" if ov_ok else "NOT FOUND")

    if args.check:
        print("\n(--check mode: no changes made)")
        return 0 if (fw_ok and ov_ok) else 1

    #  Install missing packages 
    to_install = []
    if not fw_ok:
        to_install.append("faster-whisper")
    if not ov_ok:
        to_install.append("openvino")

    if to_install:
        print(f"\nInstalling: {', '.join(to_install)} ...")
        if not _pip_install(to_install):
            print("\nInstallation failed. Check the output above.")
            return 1

    #  Verify 
    print("\nVerifying installation ...")
    fw_ok = _importable("faster_whisper")
    ov_ok = _importable("openvino")

    if fw_ok:
        print("  OK  faster-whisper")
    else:
        print("  FAIL  faster-whisper  try:  pip install --force-reinstall faster-whisper")

    if ov_ok:
        print("  OK  openvino (Intel Arc support)")
    else:
        print("  FAIL  openvino  try:  pip install openvino")

    if not fw_ok:
        return 1

    #  Summary 
    print()
    if has_nvidia:
        print("GPU: NVIDIA CUDA will be used automatically by faster-whisper.")
        print("     (CTranslate2 uses cuBLAS if CUDA drivers are installed.)")
    elif intel_name:
        print("GPU: Intel Arc detected.")
        print("     OpenVINO is installed  Arc acceleration will be used.")
        print("     If you see 'openvino device not available', install the Intel GPU driver:")
        print("     https://www.intel.com/content/www/us/en/developer/articles/tool/")
        print("     pytorch-prerequisites-for-intel-gpu.html")
    else:
        print("GPU: CPU-only mode. Transcription will work but may be slow.")
        print("     Tip: the 'small' or 'medium' model runs faster on CPU than 'large'.")

    print("\nSetup complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())