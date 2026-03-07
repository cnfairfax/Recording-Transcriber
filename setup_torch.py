"""
setup_torch.py
--------------
Detects the best available GPU (NVIDIA CUDA, Intel Arc XPU, or none) and
installs the matching PyTorch build into the current Python environment.

Priority: NVIDIA CUDA > Intel Arc / Intel GPU (XPU) > CPU

Usage:
    python setup_torch.py           # auto-detect GPU
    python setup_torch.py --cpu     # force CPU-only build
    python setup_torch.py --cuda    # force NVIDIA CUDA build (auto-picks version)
    python setup_torch.py --xpu     # force Intel XPU build (Arc / Data Center GPU)
    python setup_torch.py --check   # print what would be installed without installing
    python setup_torch.py --force   # re-install even if torch already works

Notes:
  • Intel Arc support uses PyTorch native XPU backend (torch.xpu), available
    from PyTorch 2.5+.  Intel Extension for PyTorch (IPEX) reached EOL in
    March 2026 and is not used here.
  • For Intel XPU to work the Intel GPU driver must be installed first:
    https://www.intel.com/content/www/us/en/developer/articles/tool/pytorch-prerequisites-for-intel-gpu.html
"""

from __future__ import annotations

import argparse
import enum
import re
import subprocess
import sys
from typing import Optional


# ---------------------------------------------------------------------------
# GPU backend enum
# ---------------------------------------------------------------------------

class GpuBackend(enum.Enum):
    NVIDIA_CUDA = "nvidia_cuda"
    INTEL_XPU   = "intel_xpu"
    CPU         = "cpu"


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
CPU_INDEX  = f"{PYTORCH_INDEX_BASE}/cpu"
XPU_INDEX  = f"{PYTORCH_INDEX_BASE}/xpu"  # Intel Arc / Data Center GPU (XPU)


# ---------------------------------------------------------------------------
# GPU / hardware detection helpers
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


# ------------------------------------------------------------------
# NVIDIA CUDA
# ------------------------------------------------------------------

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


# ------------------------------------------------------------------
# Intel Arc / Intel GPU (XPU)
# ------------------------------------------------------------------

# Strings we look for in the GPU adapter name to identify Intel discrete GPUs.
_INTEL_GPU_PATTERNS = re.compile(
    r"Intel.*Arc"
    r"|Intel.*Data\s*Center.*GPU"
    r"|Intel.*Ponte\s*Vecchio"
    r"|Intel.*Alchemist"
    r"|Intel.*Battlemage",
    re.IGNORECASE,
)


def _gpu_names() -> list[str]:
    """Return a list of GPU/display adapter names visible to the OS."""
    names: list[str] = []

    # Windows – WMI via PowerShell (no extra tools needed)
    if sys.platform == "win32":
        out = _run([
            "powershell", "-NoProfile", "-Command",
            "Get-WmiObject Win32_VideoController | Select-Object -ExpandProperty Name",
        ])
        if out:
            names.extend(line.strip() for line in out.splitlines() if line.strip())
        if not names:
            # Fallback: wmic
            out = _run(["wmic", "path", "win32_VideoController", "get", "name"])
            if out:
                names.extend(
                    line.strip()
                    for line in out.splitlines()
                    if line.strip() and line.strip().lower() != "name"
                )
    else:
        # Linux – lspci or /sys
        out = _run(["lspci"])
        if out:
            for line in out.splitlines():
                if re.search(r"VGA|3D|Display", line, re.IGNORECASE):
                    names.append(line)
        # macOS – system_profiler
        if not names:
            out = _run(["system_profiler", "SPDisplaysDataType"])
            if out:
                for line in out.splitlines():
                    m = re.search(r"Chipset Model:\s*(.+)", line)
                    if m:
                        names.append(m.group(1).strip())

    return names


def detect_intel_arc() -> Optional[str]:
    """Return the adapter name if an Intel Arc / XPU-capable GPU is found, else None."""
    for name in _gpu_names():
        if _INTEL_GPU_PATTERNS.search(name):
            return name
    return None


# ------------------------------------------------------------------
# Combined GPU detection
# ------------------------------------------------------------------

class DetectionResult:
    def __init__(self, backend: GpuBackend, label: str, index_url: str) -> None:
        self.backend    = backend
        self.label      = label
        self.index_url  = index_url


def detect_best_backend(*, force_cpu: bool, force_cuda: bool, force_xpu: bool) -> DetectionResult:
    """Probe GPUs and return the DetectionResult for the best available backend."""

    if force_cpu:
        print("ℹ  GPU detection skipped (--cpu)")
        return DetectionResult(GpuBackend.CPU, "CPU", CPU_INDEX)

    if force_xpu:
        print("ℹ  Skipping NVIDIA probe, using Intel XPU build (--xpu)")
        return DetectionResult(GpuBackend.INTEL_XPU, "Intel XPU", XPU_INDEX)

    if force_cuda:
        print("ℹ  Skipping Intel probe, using CUDA build (--cuda)")
        cuda_ver = detect_cuda_version()
        if cuda_ver is None:
            print("⚠  Could not detect CUDA driver version. Falling back to CPU.")
            return DetectionResult(GpuBackend.CPU, "CPU", CPU_INDEX)
        tag = pick_cuda_tag(cuda_ver)
        if tag is None:
            print(f"⚠  CUDA {cuda_ver} < minimum supported (11.8). Falling back to CPU.")
            return DetectionResult(GpuBackend.CPU, "CPU", CPU_INDEX)
        return DetectionResult(
            GpuBackend.NVIDIA_CUDA,
            f"NVIDIA CUDA ({tag})",
            f"{PYTORCH_INDEX_BASE}/{tag}",
        )

    # --- Auto-detect: NVIDIA first, then Intel, then CPU ---
    print("Detecting GPU …")

    gpu_names = _gpu_names()
    if gpu_names:
        print("  Found display adapters:")
        for name in gpu_names:
            print(f"    • {name}")

    # NVIDIA
    cuda_ver = detect_cuda_version()
    if cuda_ver:
        print(f"  NVIDIA GPU detected – driver CUDA {cuda_ver[0]}.{cuda_ver[1]}")
        tag = pick_cuda_tag(cuda_ver)
        if tag:
            return DetectionResult(
                GpuBackend.NVIDIA_CUDA,
                f"NVIDIA CUDA ({tag})",
                f"{PYTORCH_INDEX_BASE}/{tag}",
            )
        print(f"  CUDA {cuda_ver} older than minimum (11.8) – checking Intel next.")

    # Intel Arc
    intel_name = detect_intel_arc()
    if intel_name:
        print(f"  Intel GPU detected: {intel_name}")
        return DetectionResult(GpuBackend.INTEL_XPU, f"Intel XPU  ({intel_name})", XPU_INDEX)

    print("  No CUDA or Intel Arc GPU detected – using CPU build.")
    return DetectionResult(GpuBackend.CPU, "CPU", CPU_INDEX)


# ---------------------------------------------------------------------------
# Torch installation helpers
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


def verify_torch(backend: GpuBackend) -> bool:
    """Return True if torch imports and the expected device is available."""
    if backend == GpuBackend.NVIDIA_CUDA:
        check = "import torch; assert torch.cuda.is_available(), 'cuda not available'"
    elif backend == GpuBackend.INTEL_XPU:
        check = "import torch; assert torch.xpu.is_available(), 'xpu not available'"
    else:
        check = "import torch; import whisper"
    try:
        result = subprocess.run(
            [sys.executable, "-c", check],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.returncode == 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Detect GPU and install the correct PyTorch build.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="GPU priority: NVIDIA CUDA > Intel Arc XPU > CPU",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--cpu",  action="store_true", help="Force CPU-only build")
    group.add_argument("--cuda", action="store_true", help="Force NVIDIA CUDA build")
    group.add_argument("--xpu",  action="store_true", help="Force Intel XPU build (Arc / Data Center)")
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
        if not (args.cpu or args.cuda or args.xpu):
            print("  Run with --force to re-install, or --cpu / --cuda / --xpu to switch build.\n")
            return 0

    # --- Detect best backend --------------------------------------------------
    detection = detect_best_backend(
        force_cpu=args.cpu,
        force_cuda=args.cuda,
        force_xpu=args.xpu,
    )

    print(f"\nSelected PyTorch build : {detection.label}")
    print(f"Wheel index URL        : {detection.index_url}")

    if detection.backend == GpuBackend.INTEL_XPU:
        print(
            "\n  Note: Intel XPU requires the Intel GPU driver to be installed.\n"
            "  Driver guide: https://www.intel.com/content/www/us/en/developer/"
            "articles/tool/pytorch-prerequisites-for-intel-gpu.html"
        )

    if args.check:
        print("\n(--check mode: not installing)")
        return 0

    # --- Install --------------------------------------------------------------
    success = install_torch(detection.index_url, force=True)

    if not success:
        print("\n✗ Installation failed. Check pip output above.")
        return 1

    # --- Verify ---------------------------------------------------------------
    print("\nVerifying installation …")
    if verify_torch(detection.backend):
        ver = _current_torch_info()
        print(f"✓ PyTorch installed successfully: {ver}")
        if detection.backend == GpuBackend.INTEL_XPU:
            print("  torch.xpu.is_available() = True")
        elif detection.backend == GpuBackend.NVIDIA_CUDA:
            print("  torch.cuda.is_available() = True")
        return 0
    else:
        print("\n✗ PyTorch installed but device check failed.")
        if detection.backend == GpuBackend.INTEL_XPU:
            print("  torch.xpu.is_available() returned False.")
            print("  Make sure the Intel GPU driver is installed and up to date.")
            print("  Driver guide: https://www.intel.com/content/www/us/en/developer/"
                  "articles/tool/pytorch-prerequisites-for-intel-gpu.html")
        elif detection.backend == GpuBackend.NVIDIA_CUDA:
            print("  torch.cuda.is_available() returned False.")
            print("  On Windows, ensure the Visual C++ Redistributable is installed:")
            print("  https://aka.ms/vs/17/release/vc_redist.x64.exe")
        else:
            print("  On Windows, ensure the Visual C++ Redistributable is installed:")
            print("  https://aka.ms/vs/17/release/vc_redist.x64.exe")
        return 1


if __name__ == "__main__":
    sys.exit(main())
