# V1 preservation release production image.
#
# Runtime behaviour intentionally follows the historical V1 Dockerfile.  The
# release-only difference is build-once semantics: the Python distribution and
# the explicitly selected Kroko Free/Pro wheel are candidate inputs, so the
# production image never recompiles Kroko and never installs VoiceSTT editable
# from the checkout.
FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254

ARG VOICESTT_VERSION=1.0.0
ARG VOICESTT_GIT_COMMIT=unknown
ARG KROKO_VARIANT=free
ARG BUILD_DATE=unknown
ARG IMAGE_TITLE=voice-stt-server

LABEL org.opencontainers.image.title="${IMAGE_TITLE}" \
      org.opencontainers.image.description="VoiceSTT V1 preservation server (CPU, Debian Bookworm)" \
      org.opencontainers.image.version="${VOICESTT_VERSION}" \
      org.opencontainers.image.revision="${VOICESTT_GIT_COMMIT}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.source="https://github.com/marcosudau-vps/voice-stt-server" \
      org.opencontainers.image.licenses="MIT" \
      com.voicestt.kroko-variant="${KROKO_VARIANT}"

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VOICESTT_OFFLINE_MODELS=1 \
    VOICESTT_CPU_ONLY=1 \
    VOICESTT_KROKO_VARIANT=${KROKO_VARIANT} \
    VOICESTT_FASTER_WHISPER_MODEL_ROOT=/models/ctranslate2 \
    VOICESTT_KROKO_MODEL_ROOT=/models/kroko \
    VOICESTT_OPENWAKEWORD_MODEL_ROOT=/models/openwakeword \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential portaudio19-dev libsndfile1 ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY api_fastapi_server/requirements.txt /tmp/api-requirements.txt
COPY release-inputs/python/*.whl /tmp/voicestt/
COPY release-inputs/kroko/*.whl /tmp/kroko/

RUN test "${KROKO_VARIANT}" = "free" -o "${KROKO_VARIANT}" = "pro" && \
    test "$(find /tmp/voicestt -maxdepth 1 -name '*.whl' | wc -l)" -eq 1 && \
    test "$(find /tmp/kroko -maxdepth 1 -name '*.whl' | wc -l)" -eq 1 && \
    python -m pip install --upgrade pip setuptools wheel && \
    python -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu && \
    python -m pip install /tmp/kroko/*.whl && \
    python -m pip install "/tmp/voicestt/$(basename /tmp/voicestt/*.whl)[faster-whisper,silero-onnx-cpu]" \
      -r /tmp/api-requirements.txt python-multipart scikit-learn requests && \
    python -m pip install --no-deps 'openwakeword==0.6.0' && \
    sed -i '/^Requires-Dist: tflite-runtime/d' \
      /usr/local/lib/python3.12/site-packages/openwakeword-*.dist-info/METADATA && \
    python -m pip check && \
    apt-mark manual libportaudio2 libasound2 libjack-jackd2-0 libgomp1 && \
    apt-get purge -y --auto-remove build-essential portaudio19-dev && \
    rm -rf /var/lib/apt/lists/* /tmp/voicestt /tmp/kroko /tmp/api-requirements.txt

EXPOSE 8010
HEALTHCHECK --interval=30s --timeout=10s --start-period=180s --retries=5 \
  CMD python -c "import json, urllib.request; result=json.load(urllib.request.urlopen('http://127.0.0.1:8010/health', timeout=5)); assert result.get('ready') and result.get('ok')" || exit 1

CMD ["python", "-m", "VoiceSTT_server.server", \
     "--host", "0.0.0.0", "--port", "8010", \
     "--device", "cpu", "--compute-type", "int8", \
     "--model", "small", "--realtime-model", "tiny", \
     "--engine-options", "{\"local_files_only\":true}", \
     "--realtime-engine-options", "{\"local_files_only\":true}"]
