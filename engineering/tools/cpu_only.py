"""CPU-only dependency contract for Voice-STT-Server V2 (stdlib only).

V2 runs exclusively on the CPU. PyTorch is still required (``silero-vad``
depends on it and the recorder uses ``torch.multiprocessing``), but on Linux a
plain PyPI resolution of ``torch`` installs the CUDA build together with
several GB of ``nvidia-*``/``triton`` runtime wheels. A dependency in
``install_requires`` cannot select a different package index, so every
installation path we control does this instead:

1. ``install-torch``: install ``torch`` from the official CPU index into the
   *current* interpreter and write a pip constraints file that pins exactly
   that build (``torch==X.Y.Z+cpu``).
2. Every later ``pip install`` runs with ``PIP_CONSTRAINT`` pointing at that
   file, so the resolver can neither replace the CPU build nor pull CUDA
   wheels in.
3. ``check``: fail unless ``torch.version.cuda`` and ``torch.version.hip`` are
   ``None``, no CUDA/ROCm runtime distribution is installed, torch's own
   metadata requires none, and a basic CPU tensor operation works.

``torch.cuda.is_available() == False`` is deliberately *not* used as proof:
it is also false for a CUDA build on a machine without a GPU.

Usage::

    python tools/cpu_only.py install-torch --constraint-out cpu-constraints.txt
    python tools/cpu_only.py check
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from importlib import metadata
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

CPU_TORCH_INDEX_URL = "https://download.pytorch.org/whl/cpu"

#: Distribution names that only exist to provide a GPU runtime.
_GPU_DISTRIBUTION_RE = re.compile(
    r"^(nvidia[-_].+|cuda[-_].+|pytorch[-_]triton.*|triton|cupy.*|onnxruntime[-_]gpu|"
    r"torch[-_]rocm.*|rocm[-_].+)$",
    re.IGNORECASE,
)


def gpu_runtime_distributions(names: Iterable[str]) -> List[str]:
    """The subset of ``names`` that are GPU runtime distributions."""
    return sorted({name for name in names if _GPU_DISTRIBUTION_RE.match(name or "")})


def installed_distribution_names() -> List[str]:
    return sorted({(dist.metadata["Name"] or "") for dist in metadata.distributions()})


def _marker_applies(requirement: str) -> bool:
    """Whether the environment marker of ``requirement`` holds *here*.

    torch's CPU wheels can still list GPU runtimes guarded by markers such as
    ``platform_system == "Linux"`` (seen on the Windows CPU build); those are
    never installed on the current platform and must not count. ``packaging``
    is a base dependency of the product (and vendored by pip); without it the
    check stays conservative and counts every entry.
    """
    if ";" not in requirement:
        return True
    try:
        from packaging.requirements import Requirement  # noqa: PLC0415
    except ImportError:  # pragma: no cover - conservative fallback
        return True
    parsed = Requirement(requirement)
    return parsed.marker is None or parsed.marker.evaluate({"extra": ""})


def gpu_requirements_of(distribution: str) -> List[str]:
    """Active ``Requires-Dist`` entries of ``distribution`` naming a GPU runtime."""
    try:
        requirements = metadata.requires(distribution) or []
    except metadata.PackageNotFoundError:
        return []
    offending = []
    for requirement in requirements:
        name = re.split(r"[\s;<>=!~\[(]", requirement.strip(), maxsplit=1)[0]
        if _GPU_DISTRIBUTION_RE.match(name) and _marker_applies(requirement):
            offending.append(requirement)
    return offending


def check_cpu_only(require_torch: bool = True) -> dict:
    """Machine-checkable CPU-only evidence; raises ``SystemExit`` on failure."""
    problems: List[str] = []
    report: dict = {"gpuDistributions": [], "torch": None}
    report["gpuDistributions"] = gpu_runtime_distributions(installed_distribution_names())
    if report["gpuDistributions"]:
        problems.append("GPU runtime distributions installed: " + ", ".join(report["gpuDistributions"]))
    try:
        import torch  # noqa: PLC0415 - optional by design
    except ModuleNotFoundError:
        if require_torch:
            problems.append("torch is not installed")
    else:
        version = getattr(torch, "version", None)
        cuda = getattr(version, "cuda", None)
        hip = getattr(version, "hip", None)
        torch_gpu_requires = gpu_requirements_of("torch")
        tensor_ok = bool((torch.ones(3) + 1).sum().item() == 6)
        report["torch"] = {
            "version": torch.__version__,
            "cuda": cuda,
            "hip": hip,
            "gpuRequiresDist": torch_gpu_requires,
            "cpuTensorOperation": tensor_ok,
        }
        if cuda is not None:
            problems.append(f"torch is a CUDA build (torch.version.cuda={cuda})")
        if hip is not None:
            problems.append(f"torch is a ROCm build (torch.version.hip={hip})")
        if torch_gpu_requires:
            problems.append("torch metadata requires GPU runtimes: " + ", ".join(torch_gpu_requires))
        if not tensor_ok:
            problems.append("basic CPU tensor operation failed")
    report["ok"] = not problems
    report["problems"] = problems
    return report


def install_cpu_torch(constraint_out: Optional[Path], extra: Sequence[str] = ()) -> str:
    """Install CPU-only torch into this interpreter; return the pin written."""
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--index-url", CPU_TORCH_INDEX_URL,
         "torch", *extra],
        check=True,
    )
    version = subprocess.run(
        [sys.executable, "-c", "import torch; print(torch.__version__)"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    pin = f"torch=={version}"
    if constraint_out is not None:
        constraint_out.parent.mkdir(parents=True, exist_ok=True)
        constraint_out.write_text(pin + "\n", encoding="utf-8")
    return pin


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = parser.add_subparsers(dest="command", required=True)
    install = sub.add_parser("install-torch", help="Install CPU-only torch into this interpreter.")
    install.add_argument("--constraint-out", type=Path, default=None,
                         help="Write a pip constraints file pinning the installed CPU build.")
    check = sub.add_parser("check", help="Verify the CPU-only dependency contract.")
    check.add_argument("--allow-missing-torch", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "install-torch":
        print(install_cpu_torch(args.constraint_out))
        return 0
    report = check_cpu_only(require_torch=not args.allow_missing_torch)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
