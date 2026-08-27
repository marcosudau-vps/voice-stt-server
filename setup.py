import os
import re

import setuptools
from setuptools.command.build_py import build_py as _build_py


current_version = "1.0.2"


INSTALL_GUIDE = """
VoiceSTT lets you choose the transcription and wake-word dependencies you
want to install.

Recommended default local Whisper install:

    pip install "voicestt[recommended]"

Main ASR backend only, without the faster packaged Silero ONNX Runtime VAD:

    pip install "voicestt[faster-whisper]"

Core package only, without a transcription engine or wake-word backend:

    pip install voicestt

Install multiple extras by separating them with commas:

    pip install "voicestt[faster-whisper,porcupine]"
    pip install "voicestt[whisper-cpp,openwakeword]"

Available extras include:

- faster-whisper: default CTranslate2 Whisper backend
- whisper-cpp: whisper.cpp backend through pywhispercpp
- openai-whisper: original OpenAI Whisper Python backend
- sherpa-onnx: sherpa-onnx CPU backends
- silero-vad: packaged Silero model assets and PyTorch wrapper
- silero-onnx/silero-onnx-cpu: fastest Silero VAD CPU ONNX Runtime backend
- omnilingual/omnilingual-asr: Meta Omnilingual ASR backend for Linux/WSL2 with Python 3.11.x only; uses omnilingual-asr>=0.2.0 with matching torch/torchaudio builds
- transformers: shared Transformers dependency for Moonshine, Granite, and Cohere
- moonshine, granite, cohere: aliases for the Transformers dependency set
- qwen: Qwen ASR backend
- kroko-builder: helper command for building/installing Kroko-ONNX plus Hugging Face model downloads
- porcupine: Porcupine wake-word backend
- openwakeword: OpenWakeWord wake-word backend
- wakewords: both wake-word backends
- recommended/default: faster-whisper backend plus fast Silero CPU ONNX VAD
- server: FastAPI, multipart uploads, HTTP and SSE support
- example-app: dependencies for the OpenAI voice-interface example
- all: the complete supported CPU setup (Faster Whisper, Silero ONNX and wake words)

WebRTC VAD is installed with the core package. AudioToTextRecorder also
initializes a Silero VAD path. Install the recommended/default or
silero-onnx-cpu extra for a self-contained local Silero ONNX Runtime backend.

Meta Omnilingual ASR install note: use Linux or WSL2 with Python 3.11.x.
Native Windows cannot run the Omnilingual runtime because fairseq2n has no
Windows wheel, and Python 3.12.x currently cannot resolve omnilingual-asr>=0.2.0
from PyPI because the upstream package metadata excludes normal 3.12 patch
releases.

For live Kroko-ONNX usage, install the builder helper and then build Kroko in
the same Python environment:

    pip install "voicestt[kroko-builder,silero-onnx-cpu]"
    stt-install-kroko --build --variant free

The complete build reference, including the required distinction between
Community and licensed Pro builds, is maintained at:

    https://github.com/marcosudau-vps/voice-stt-server/blob/main/build/BUILD.md

The silero-onnx-cpu extra is not needed to build Kroko-ONNX itself, but
recorder-based Kroko smoke tests and live AudioToTextRecorder use need a local
VAD backend.

On Windows, use Python 3.12 x64 and start Docker Desktop before running the
builder. Check that Docker's Linux engine is available with:

    python --version
    git --version
    docker version

`docker version` must show a Server section. `docker --version` only checks
that the Docker CLI is installed.

If the default builder cache is not writable, use a project-local work
directory:

    stt-install-kroko --build --variant free --work-dir .\\kroko-builder-work

The kroko-builder extra includes huggingface_hub. Download a public Community
model after the builder finishes:

    mkdir test-model-cache\\kroko-onnx
    python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='Banafo/Kroko-ASR', filename='Kroko-EN-Community-64-L-Streaming-001.data', local_dir='test-model-cache/kroko-onnx')"

"""

# Get the absolute path of requirements.txt
req_path = os.path.join(os.path.dirname(__file__), "requirements.txt")

def parse_requirements(filename):
    parsed = {}
    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            package = re.split(
                r"\s*(?:===|==|>=|<=|~=|!=|>|<|;)",
                line,
                maxsplit=1,
            )[0].strip()
            parsed[package] = line
    return parsed


def requirement(name, fallback=None):
    return requirements.get(name, fallback or name)


def unique_requirements(items):
    seen = set()
    unique = []
    for item in items:
        normalized = item.lower()
        if normalized not in seen:
            seen.add(normalized)
            unique.append(item)
    return unique


def is_local_backup_file(path):
    filename = os.path.basename(path)
    return " - Kopie" in filename or filename.endswith((".bak", ".tmp"))


class build_py(_build_py):
    def find_package_modules(self, package, package_dir):
        modules = super().find_package_modules(package, package_dir)
        return [
            (pkg, module, path)
            for pkg, module, path in modules
            if not is_local_backup_file(path)
        ]


requirements = parse_requirements(req_path)

base_requirements = [
    requirement("PyAudio"),
    requirement("webrtcvad-wheels"),
    requirement("halo"),
    requirement("torch"),
    requirement("torchaudio"),
    requirement("scipy"),
    requirement("websockets"),
    requirement("websocket-client"),
    requirement("soundfile"),
]

faster_whisper_requirements = [requirement("faster-whisper")]
whisper_cpp_requirements = ["pywhispercpp"]
openai_whisper_requirements = ["openai-whisper"]
sherpa_onnx_requirements = ["sherpa-onnx"]
silero_vad_requirements = [
    "silero-vad>=6.2.1; python_version >= '3.8'",
]
silero_onnx_requirements = [
    "silero-vad[onnx-cpu]>=6.2.1; python_version >= '3.8'",
]
transformers_requirements = ["transformers"]
parakeet_requirements = ["nemo_toolkit[asr]"]
omnilingual_asr_marker = (
    "python_version >= '3.10' and python_version < '3.12' "
    "and platform_system != 'Windows'"
)
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
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "python-multipart",
    "sse-starlette",
    "httpx",
    "PyYAML>=6.0",
    "tzdata",
]
app_talk_with_llm_requirements = [
    "RealtimeTTS[edge,system]==0.7.3",
    "PyQt5==5.15.11",
    "openai==2.41.1",
    "PyYAML>=6.0",
    "sounddevice==0.5.5",
    "wavio==0.0.9",
    "keyboard==0.13.5",
]

all_optional_requirements = unique_requirements(
    faster_whisper_requirements
    + whisper_cpp_requirements
    + openai_whisper_requirements
    + sherpa_onnx_requirements
    + silero_onnx_requirements
    + transformers_requirements
    + omnilingual_asr_requirements
    + qwen_requirements
    + kroko_builder_requirements
    + porcupine_requirements
    + openwakeword_requirements
)

extras_require = {
    "minimal": [],
    "faster-whisper": faster_whisper_requirements,
    "whisper-cpp": whisper_cpp_requirements,
    "whispercpp": whisper_cpp_requirements,
    "openai-whisper": openai_whisper_requirements,
    "sherpa-onnx": sherpa_onnx_requirements,
    "sherpa": sherpa_onnx_requirements,
    "silero-vad": silero_vad_requirements,
    "silero": silero_vad_requirements,
    "silero-onnx": silero_onnx_requirements,
    "silero-onnx-cpu": silero_onnx_requirements,
    "vad-onnx": silero_onnx_requirements,
    "transformers": transformers_requirements,
    "moonshine": transformers_requirements,
    "granite": transformers_requirements,
    "cohere": transformers_requirements,
    "omnilingual-asr": omnilingual_asr_requirements,
    "omnilingual": omnilingual_asr_requirements,
    "meta-omnilingual-asr": omnilingual_asr_requirements,
    "qwen": qwen_requirements,
    "qwen3-asr": qwen_requirements,
    "kroko-builder": kroko_builder_requirements,
    "porcupine": porcupine_requirements,
    "pvporcupine": porcupine_requirements,
    "pvp": porcupine_requirements,
    "openwakeword": openwakeword_requirements,
    "oww": openwakeword_requirements,
    "wakewords": unique_requirements(
        porcupine_requirements + openwakeword_requirements
    ),
    "wake-words": unique_requirements(
        porcupine_requirements + openwakeword_requirements
    ),
    "server": server_requirements,
    "example-app": app_talk_with_llm_requirements,
    "recommended": unique_requirements(
        faster_whisper_requirements + silero_onnx_requirements
    ),
    "default": unique_requirements(
        faster_whisper_requirements + silero_onnx_requirements
    ),
    "all": unique_requirements(
        faster_whisper_requirements
        + silero_onnx_requirements
        + kroko_builder_requirements
        + porcupine_requirements
        + openwakeword_requirements
        + server_requirements
        + app_talk_with_llm_requirements
    ),
}

# Read README.md
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

long_description = INSTALL_GUIDE + long_description

setuptools.setup(
    name="voicestt",
    version=current_version,
    author="Kolja Beigel",
    author_email="kolja.beigel@web.de",
    description="A fast Voice Activity Detection and Transcription System",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/marcosudau-vps/voice-stt-server",
    packages=setuptools.find_packages(
        include=[
            "VoiceSTT",
            "VoiceSTT.*",
            "VoiceSTT_server",
            "VoiceSTT_server.*",
            "api_fastapi_server",
            "api_fastapi_server.*",
        ]
    ),
    # classifiers=[
    #     "Programming Language :: Python :: 3",
    #     "Operating System :: OS Independent",
    # ],
    python_requires='>=3.11',
    license='MIT',
    install_requires=base_requirements,
    extras_require=extras_require,
    keywords="real-time, audio, transcription, speech-to-text, voice-activity-detection, VAD, real-time-transcription, ambient-noise-detection, microphone-input, faster_whisper, speech-recognition, voice-assistants, audio-processing, buffered-transcription, pyaudio, ambient-noise-level, voice-deactivity",
    package_data={
        "VoiceSTT": [
            "assets/warmup_audio.wav",
            # AP-SRV-060: the wake-word build assets ship with the package, so
            # an installed wheel on Windows and on Ubuntu resolves them without
            # any runtime download.
            "assets/wakeword_models/models.json",
            "assets/wakeword_models/*.onnx",
        ],
        "api_fastapi_server": ["static/index.html"],
    },
    include_package_data=True,
    cmdclass={"build_py": build_py},
    entry_points={
        'console_scripts': [
            'stt-server=VoiceSTT_server.server:main',
            'stt-server-legacy=VoiceSTT_server.stt_server:main',
            'stt=VoiceSTT_server.stt_cli_client:main',
            'stt-install-kroko=VoiceSTT.install_kroko:main',
        ],
    },
)
