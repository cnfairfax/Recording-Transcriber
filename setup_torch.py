"""
setup_torch.py
--------------
Detects whether a CUDA-capable NVIDIA GPU is present and installs the
matching PyTorch build into the current Python environment.

Usage:
    python setup_torch.py          # auto-detect GPU
    python setup_torch.py --cpu    # force CPU-only build
    python setup_torch.py --cuda   # force CUDA build (auto-picks version)
    python setup_torch.py --check  # only print what would be installed, don't install
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from typing import Optional


# ---------------------------------------------------------------------------
# CUDA version → PyTorch wheel tag mapping
# Only include versions that PyTorch currently publishes wheels for.
# ---------------------------------------------------------------------------
CUDA_WHEEL_TAGS: list[tuple[tuple[int, int], str]] = [
    # (minimum driver CUDA version, wheel tag)  – checked from newest to oldest
    ((12, 6), "cu126"),
    ((12, 4), "cu124"),
    ((12, 1), "cu121"),
    ((11, 8), "cu118"),
]

PYTORCH_INDEX_BASE = "https://download.pytorch.org/whl"
CPU_INDEX = f"{PYTORCH_INDEX_BASE}/cpu"


# ---------------------------------------------------------------------------
# GPU / CUDA detection
# ---------------------------------------------------------------------------

def _run(cmd: list[str]) -> Optional[str]:
    """Run a command, return combined stdout, or None on failure."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result.stdout if result.returncode == 0 else None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def detect_cuda_version() -> Optional[tuple[int, int]]:
    """Return (major, minor) of the CUDA version supported by the driver, or None."""
    # 1. nvidia-smi is the most reliable probe
    output = _run(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"])
    if output is None:
        output = _run(["nvidia-smi"])

    if output:
        # nvidia-smi header line: "CUDA Version: 12.4"
        match = re.search(r"CUDA\s+Version\s*:\s*(\d+)\.(\d+)", output)
        if match:
            return int(match.group(1)), int(match.group(2))

    # 2. On Linux/macOS try nvcc
    output = _run(["nvcc", "--version"])
    if output:
        match = re.search(r"release\s+(\d+)\.(\d+)", output)
        if match:
            return int(match.group(1)), int(match.group(2))

    return None


def pick_cuda_tag(version: tuple[int, int]) -> Optional[str]:
    """Pick the best supported PyTorch CUDA wheel tag for a driver version."""
    for min_version, tag in CUDA_WHEEL_TAGS:
        if version >= min_version:
            return tag
    return None  # older than cu118 – fall back to CPU


# ---------------------------------------------------------------------------
# Torch installation
# ---------------------------------------------------------------------------

def _current_torch_info() -> Optional[str]:
    """Return installed torch version string, or None if not installed / broken."""
    try:
        result = subprocess.run(
            [sys.executable, "-c", "import torch; print(torch.__version__)"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except Exception:
        return None


def install_torch(index_url: str, force: bool = False) -> bool:
    """Install (or re-install) torch from the given wheel index.  Returns True on success."""
    cmd = [
        sys.executable, "-m", "pip", "install", "torch",
        "--index-url", index_url,
    ]
    if force:
        cmd.append("--force-reinstall")

    print(f"\n→ Running: {' '.join(cmd)}\n")
    try:
        subprocess.check_call(cmd)
        return True
    except subprocess.CalledProcessError:
        return False


def verify_torch() -> bool:
    """Return True if torch imports successfully in a fresh sub-process."""
    output = _current_torch_info()
    return output is not None


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Install the correct PyTorch build.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--cpu",   action="store_true", help="Force CPU-only build")
    group.add_argument("--cuda",  action="store_true", help="Force CUDA build (auto-picks version)")
    parser.add_argument("--check", action="store_true", help="Print what would be installed without installing")
    parser.add_argument("--force", action="store_true", help="Re-install even if torch is already working")
    args = parser.parse_args()

    # --- Probe current state --------------------------------------------------
    print("=== Recording Transcriber – Torch Setup ===\n")

    current = _current_torch_info()
    if current and not args.force:
        print(f"✓ PyTorch already installed and working: {current}")
        if args.check:
            print("  (--check mode: nothing to do)")
            return 0
        # Still let the user force a specific flavour
        if not args.cpu and not args.cuda:
            print("  Run with --force to re-install, or --cpu / --cuda to switch build.\n")
            return 0

    # --- Detect GPU -----------------------------------------------------------
    if args.cpu:
        cuda_ver = None
        print("ℹ GPU detection skipped (--cpu flag)")
    elif args.cuda:
        cuda_ver = detect_cuda_version()
        if cuda_ver is None:
            print("⚠ Could not detect a CUDA-capable GPU. Falling back to CPU build.")
    else:
        print("Detecting GPU …")
        cuda_ver = detect_cuda_version()
        if cuda_ver:
            print(f"  Found NVIDIA GPU with driver CUDA {cuda_ver[0]}.{cuda_ver[1]}")
        else:
            print("  No CUDA-capable GPU detected.")

    # --- Pick wheel index -----------------------------------------------------
    if cuda_ver:
        cuda_tag = pick_cuda_tag(cuda_ver)
        if cuda_tag:
            index_url = f"{PYTORCH_INDEX_BASE}/{cuda_tag}"
            build_label = f"CUDA ({cuda_tag})"
        else:
            print(f"  CUDA {cuda_ver} is older than the minimum supported (11.8). Using CPU build.")
            index_url = CPU_INDEX
            build_label = "CPU"
    else:
        index_url = CPU_INDEX
        build_label = "CPU"

    print(f"\nSelected PyTorch build : {build_label}")
    print(f"Wheel index URL        : {index_url}")

    if args.check:
        print("\n(--check mode: not installing)")
        return 0

    # --- Install --------------------------------------------------------------
    success = install_torch(index_url, force=True)

    if not success:
        print("\n✗ Installation failed. Check pip output above.")
        return 1

    # --- Verify ---------------------------------------------------------------
    print("\nVerifying installation …")
    if verify_torch():
        ver = _current_torch_info()
        print(f"✓ PyTorch installed successfully: {ver}")
        return 0
    else:
        print("✗ PyTorch installed but still fails to import.")
        print("  On Windows, try installing the Visual C++ Redistributable:")
        print("  https://aka.ms/vs/17/release/vc_redist.x64.exe")
        return 1


if __name__ == "__main__":
    sys.exit(main())
