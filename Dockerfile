FROM python:3.12-slim-bookworm AS kroko-builder

ARG KROKO_VARIANT=free

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential cmake git libssl-dev pybind11-dev zlib1g-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /build
RUN mkdir -p /build/voicestt/VoiceSTT
COPY VoiceSTT/install_kroko.py /build/voicestt/VoiceSTT/install_kroko.py
RUN python -m pip install --upgrade pip setuptools wheel && \
    python -m pip install huggingface_hub && \
    python /build/voicestt/VoiceSTT/install_kroko.py \
      --build --skip-install --work-dir /build/kroko-work \
      --variant "${KROKO_VARIANT}"


FROM python:3.12-slim-bookworm AS cpu

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VOICESTT_OFFLINE_MODELS=1 \
    VOICESTT_CPU_ONLY=1 \
    VOICESTT_FASTER_WHISPER_MODEL_ROOT=/models/ctranslate2 \
    VOICESTT_KROKO_MODEL_ROOT=/models/kroko \
    VOICESTT_OPENWAKEWORD_MODEL_ROOT=/models/openwakeword \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential portaudio19-dev libsndfile1 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app
COPY --from=kroko-builder /build/kroko-work/kroko-onnx/release_artifacts/linux/*.whl /tmp/kroko-wheels/

RUN python -m pip install --upgrade pip setuptools wheel && \
    python -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu && \
    python -m pip install '/tmp/kroko-wheels/'*.whl && \
    python -m pip install -e '.[faster-whisper,silero-onnx-cpu]' \
      -r api_fastapi_server/requirements.txt python-multipart \
      scikit-learn requests && \
    python -m pip install --no-deps 'openwakeword==0.6.0' && \
    sed -i '/^Requires-Dist: tflite-runtime/d' \
      /usr/local/lib/python3.12/site-packages/openwakeword-*.dist-info/METADATA && \
    python -m pip check && \
    apt-mark manual libportaudio2 libasound2 libjack-jackd2-0 libgomp1 && \
    apt-get purge -y --auto-remove build-essential portaudio19-dev && \
    rm -rf /var/lib/apt/lists/* /tmp/kroko-wheels

EXPOSE 8010
HEALTHCHECK --interval=30s --timeout=10s --start-period=180s --retries=5 \
  CMD python -c "import json, urllib.request; result=json.load(urllib.request.urlopen('http://127.0.0.1:8010/health', timeout=5)); assert result.get('ready') and result.get('ok')" || exit 1

CMD ["python", "-m", "VoiceSTT_server.server", \
     "--host", "0.0.0.0", "--port", "8010", \
     "--device", "cpu", "--compute-type", "int8", \
     "--model", "small", "--realtime-model", "tiny", \
     "--engine-options", "{\"local_files_only\":true}", \
     "--realtime-engine-options", "{\"local_files_only\":true}"]
