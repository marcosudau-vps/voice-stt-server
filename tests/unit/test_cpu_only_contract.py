"""CPU-only dependency contract (V2): the checker logic and its wiring.

The real installation proof runs in CI (``tools/cpu_only.py check`` in both
the wheel-smoke and the dev environment) and in the release-candidate
qualification (``tools/qualify_build_identity.qualify_installed_wheel``).
These tests pin the decision logic and that every path is wired to it.
"""

from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from engineering.tools import cpu_only  # noqa: E402


def _fake_torch(cuda=None, hip=None):
    module = types.ModuleType("torch")

    class _Tensor:
        def __init__(self, total):
            self.total = total

        def __add__(self, other):
            return _Tensor(self.total + 3 * other)

        def sum(self):
            return self

        def item(self):
            return self.total

    module.ones = lambda n: _Tensor(n)
    module.version = types.SimpleNamespace(cuda=cuda, hip=hip)
    module.__version__ = "9.9.9+cpu" if cuda is None and hip is None else "9.9.9+cu999"
    return module


class GpuDistributionPatternTests(unittest.TestCase):
    def test_gpu_runtime_names_are_recognised(self):
        names = ["nvidia-cublas-cu12", "nvidia_cudnn_cu13", "cuda-bindings", "triton",
                 "pytorch-triton-rocm", "onnxruntime-gpu", "numpy", "torch", "onnxruntime"]
        self.assertEqual(
            cpu_only.gpu_runtime_distributions(names),
            sorted(["nvidia-cublas-cu12", "nvidia_cudnn_cu13", "cuda-bindings", "triton",
                    "pytorch-triton-rocm", "onnxruntime-gpu"]),
        )


class CheckTests(unittest.TestCase):
    def _check(self, torch_module, installed=("numpy", "torch"), requires=()):
        with mock.patch.dict(sys.modules, {"torch": torch_module}), \
                mock.patch.object(cpu_only, "installed_distribution_names", return_value=list(installed)), \
                mock.patch.object(cpu_only.metadata, "requires", return_value=list(requires)):
            return cpu_only.check_cpu_only()

    def test_cpu_build_passes(self):
        report = self._check(_fake_torch())
        self.assertTrue(report["ok"], report)
        self.assertIsNone(report["torch"]["cuda"])

    def test_cuda_build_fails_even_without_a_gpu(self):
        report = self._check(_fake_torch(cuda="13.2"))
        self.assertFalse(report["ok"])
        self.assertIn("CUDA build", " ".join(report["problems"]))

    def test_rocm_build_fails(self):
        report = self._check(_fake_torch(hip="6.2"))
        self.assertFalse(report["ok"])

    def test_installed_nvidia_runtime_fails(self):
        report = self._check(_fake_torch(), installed=("torch", "nvidia-cublas-cu12"))
        self.assertFalse(report["ok"])
        self.assertEqual(report["gpuDistributions"], ["nvidia-cublas-cu12"])

    def test_torch_metadata_requiring_gpu_runtimes_fails(self):
        report = self._check(_fake_torch(), requires=("nvidia-cudnn-cu13==9.1; platform_system == 'Linux'",))
        self.assertFalse(report["ok"])


class WiringTests(unittest.TestCase):
    def test_ci_installs_cpu_torch_and_checks_both_environments(self):
        ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertEqual(ci.count("engineering/tools/cpu_only.py install-torch"), 2)
        self.assertIn("$PY engineering/tools/cpu_only.py check", ci)
        self.assertIn("python engineering/tools/cpu_only.py check", ci)
        self.assertIn('PIP_CONSTRAINT="$SMOKE_CONSTRAINTS"', ci)
        self.assertIn('PIP_CONSTRAINT="$DEV_CONSTRAINTS" python -m pip install -e', ci)

    def test_release_candidate_qualification_uses_the_cpu_contract(self):
        text = (REPO_ROOT / "engineering" / "tools" / "qualify_build_identity.py").read_text(encoding="utf-8")
        self.assertIn('"install-torch"', text)
        self.assertIn('[str(CPU_ONLY_TOOL), "check"]', text)
        self.assertIn('env["PIP_CONSTRAINT"]', text)

    def test_container_and_windows_installers_use_the_cpu_index(self):
        dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("pip install torch --index-url https://download.pytorch.org/whl/cpu", dockerfile)
        self.assertIn("PIP_CONSTRAINT=/build/cpu-constraints.txt", dockerfile)
        self.assertIn("torch.version.cuda is None", dockerfile)
        windows = (REPO_ROOT / "install_windows_cpu.ps1").read_text(encoding="utf-8")
        self.assertIn("--index-url https://download.pytorch.org/whl/cpu", windows)
        for text in (dockerfile, windows):
            self.assertNotIn("torchaudio", text)


if __name__ == "__main__":
    unittest.main()
