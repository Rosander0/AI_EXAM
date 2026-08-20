"""Device resolution for SANKET.

Universal cross-platform hardware acceleration:
- Apple Silicon Macs (M1/M2/M3/M4): Metal Performance Shaders ('mps')
- NVIDIA GPUs: CUDA ('cuda')
- Universal fallback: CPU ('cpu')
"""

import os
import sys

# Invariant: MPS fallback enabled so unsupported operations fallback to CPU safely on Mac
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"


def resolve_device(pref: str = "auto") -> str:
    """Resolves compute device to 'mps', 'cuda', or 'cpu' with diagnostic output."""
    pref = (pref or "auto").lower()

    if pref in ("cuda", "auto"):
        try:
            import torch
            if torch.cuda.is_available():
                print("[DEVICE] Selected 'cuda' (NVIDIA GPU acceleration available).", file=sys.stderr)
                return "cuda"
        except Exception:
            pass

    if pref in ("mps", "auto"):
        try:
            import torch
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                print("[DEVICE] Selected 'mps' (Apple Silicon GPU acceleration available).", file=sys.stderr)
                return "mps"
        except Exception:
            pass

    try:
        import torch
        if hasattr(torch, "set_num_threads"):
            num_cores = os.cpu_count() or 4
            torch.set_num_threads(min(8, num_cores))
    except Exception:
        pass

    print("[DEVICE] Selected 'cpu' (CPU computation fallback active).", file=sys.stderr)
    return "cpu"
