import os
import re
from pathlib import Path

import setuptools
from setuptools.command.build_py import build_py as _build_py

REPO_ROOT = Path(__file__).resolve().parent
current_version = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()

INSTALL_GUIDE = """
VoiceSTT V1.0.0 preservation release has two alternative published products:

    pip install voice-stt-server
    pip install voice-stt-server-pro

The public CPython 3.12 Linux/Windows product wheels already embed the matching
Kroko native runtime (Free or Pro respectively). A normal wheel consumer does
not compile Kroko and does not install a separate kroko-onnx wheel. Kroko
`.data` model files remain separate from the Python package.

The historical `stt-install-kroko --build --variant free|pro` command remains
available for developers and source builds; it is not the normal PyPI consumer
path.

Optional VoiceSTT backends can still be installed through extras, for example:

    pip install "voice-stt-server[faster-whisper]"
    pip install "voice-stt-server[silero-onnx-cpu]"

See docs/v1-preservation-release.md for the exact V1 release contract and
build/BUILD.md for source/developer build details.

"""

req_path = REPO_ROOT / "requirements.txt"


def parse_requirements(filename):
    parsed = {}
    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            package = re.split(r"\s*(?:===|==|>=|<=|~=|!=|>|<|;)", line, maxsplit=1)[0].strip()
            parsed[package] = line
    return parsed


def requirement(name, fallback=None):
    return requirements.get(name, fallback or name)


def unique_requirements(items):
    seen = set(); unique = []
    for item in items:
        normalized = item.lower()
        if normalized not in seen:
            seen.add(normalized); unique.append(item)
    return unique


def is_local_backup_file(path):
    filename = os.path.basename(path)
    return " - Kopie" in filename or filename.endswith((".bak", ".tmp"))


class build_py(_build_py):
    def find_package_modules(self, package, package_dir):
        modules = super().find_package_modules(package, package_dir)
        return [(pkg, module, path) for pkg, module, path in modules if not is_local_backup_file(path)]


requirements = parse_requirements(req_path)
base_requirements = [
    requirement("PyAudio"), requirement("webrtcvad-wheels"), requirement("halo"),
    requirement("torch"), requirement("torchaudio"), requirement("scipy"),
    requirement("websockets"), requirement("websocket-client"), requirement("soundfile"),
]
faster_whisper_requirements = [requirement("faster-whisper")]
whisper_cpp_requirements = ["pywhispercpp"]
openai_whisper_requirements = ["openai-whisper"]
sherpa_onnx_requirements = ["sherpa-onnx"]
silero_vad_requirements = ["silero-vad>=6.2.1; python_version >= '3.8'"]
silero_onnx_requirements = ["silero-vad[onnx-cpu]>=6.2.1; python_version >= '3.8'"]
transformers_requirements = ["transformers"]
parakeet_requirements = ["nemo_toolkit[asr]"]
omnilingual_asr_marker = "python_version >= '3.10' and python_version < '3.12' and platform_system != 'Windows'"
omnilingual_asr_requirements = [
    "torch==2.8.0; %s" % omnilingual_asr_marker,
    "torchaudio==2.8.0; %s" % omnilingual_asr_marker,
    "omnilingual-asr>=0.2.0; %s" % omnilingual_asr_marker,
]
qwen_requirements = ["qwen-asr"]
qwen_vllm_requirements = ["qwen-asr[vllm]"]
kroko_builder_requirements = ["huggingface_hub"]
porcupine_requirements = [requirement("pvporcupine")]
openwakeword_requirements = [requirement("openwakeword")]
server_requirements = [
    "fastapi>=0.115", "uvicorn[standard]>=0.30", "python-multipart", "sse-starlette",
    "httpx", "PyYAML>=6.0", "tzdata",
]
app_talk_with_llm_requirements = [
    "RealtimeTTS[edge,system]==0.7.3", "PyQt5==5.15.11", "openai==2.41.1",
    "PyYAML>=6.0", "sounddevice==0.5.5", "wavio==0.0.9", "keyboard==0.13.5",
]
all_optional_requirements = unique_requirements(
    faster_whisper_requirements + whisper_cpp_requirements + openai_whisper_requirements +
    sherpa_onnx_requirements + silero_onnx_requirements + transformers_requirements +
    omnilingual_asr_requirements + qwen_requirements + kroko_builder_requirements +
    porcupine_requirements + openwakeword_requirements
)
extras_require = {
    "minimal": [], "faster-whisper": faster_whisper_requirements,
    "whisper-cpp": whisper_cpp_requirements, "whispercpp": whisper_cpp_requirements,
    "openai-whisper": openai_whisper_requirements, "sherpa-onnx": sherpa_onnx_requirements,
    "sherpa": sherpa_onnx_requirements, "silero-vad": silero_vad_requirements,
    "silero": silero_vad_requirements, "silero-onnx": silero_onnx_requirements,
    "silero-onnx-cpu": silero_onnx_requirements, "vad-onnx": silero_onnx_requirements,
    "transformers": transformers_requirements, "moonshine": transformers_requirements,
    "granite": transformers_requirements, "cohere": transformers_requirements,
    "omnilingual-asr": omnilingual_asr_requirements, "omnilingual": omnilingual_asr_requirements,
    "meta-omnilingual-asr": omnilingual_asr_requirements, "qwen": qwen_requirements,
    "qwen3-asr": qwen_requirements, "kroko-builder": kroko_builder_requirements,
    "porcupine": porcupine_requirements, "pvporcupine": porcupine_requirements,
    "pvp": porcupine_requirements, "openwakeword": openwakeword_requirements,
    "oww": openwakeword_requirements,
    "wakewords": unique_requirements(porcupine_requirements + openwakeword_requirements),
    "wake-words": unique_requirements(porcupine_requirements + openwakeword_requirements),
    "server": server_requirements, "example-app": app_talk_with_llm_requirements,
    "recommended": unique_requirements(faster_whisper_requirements + silero_onnx_requirements),
    "default": unique_requirements(faster_whisper_requirements + silero_onnx_requirements),
    "all": unique_requirements(faster_whisper_requirements + silero_onnx_requirements +
        kroko_builder_requirements + porcupine_requirements + openwakeword_requirements +
        server_requirements + app_talk_with_llm_requirements),
}

with open(REPO_ROOT / "README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()
long_description = INSTALL_GUIDE + long_description

setuptools.setup(
    name="voice-stt-server", version=current_version, author="Kolja Beigel",
    author_email="kolja.beigel@web.de",
    description="A fast Voice Activity Detection and Transcription System",
    long_description=long_description, long_description_content_type="text/markdown",
    url="https://github.com/marcosudau-vps/voice-stt-server",
    packages=setuptools.find_packages(include=["VoiceSTT","VoiceSTT.*","VoiceSTT_server","VoiceSTT_server.*","api_fastapi_server","api_fastapi_server.*"]),
    python_requires=">=3.11", license="MIT", install_requires=base_requirements,
    extras_require=extras_require,
    keywords="real-time, audio, transcription, speech-to-text, voice-activity-detection, VAD, real-time-transcription, ambient-noise-detection, microphone-input, faster_whisper, speech-recognition, voice-assistants, audio-processing, buffered-transcription, pyaudio, ambient-noise-level, voice-deactivity",
    package_data={"VoiceSTT":["assets/warmup_audio.wav"],"api_fastapi_server":["static/index.html"]},
    include_package_data=True, cmdclass={"build_py": build_py},
    entry_points={"console_scripts":[
        "stt-server=VoiceSTT_server.server:main",
        "stt-server-legacy=VoiceSTT_server.stt_server:main",
        "stt=VoiceSTT_server.stt_cli_client:main",
        "stt-install-kroko=VoiceSTT.install_kroko:main",
    ]},
)
