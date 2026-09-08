# Buildvarianten und Kroko-Lizenzgrenzen: build/BUILD.md
#
# AP-SRV-070 W4C: public production image. This Dockerfile never compiles
# Kroko and never installs VoiceSTT in editable/source mode - both wheels are
# supplied as build context inputs, produced beforehand by
# tools/build_production.py (VoiceSTT: `python -m build --wheel`; Kroko: the
# separate build/kroko-builder.Dockerfile driven through the existing W4A
# fingerprint/artifact-store authority). See build/BUILD.md for the full
# build matrix and Kroko variant contract.
#
# Build inputs expected in the build context:
#   dist/voicestt/*.whl   - the VoiceSTT wheel for this exact commit/version
#   dist/kroko/*.whl      - the resolved Linux/AMD64 Kroko wheel (free/pro)
#
# Runtime target: Ubuntu 24.04, linux/amd64, CPU-only.
#
# AP-SRV-070 W5-R04, section 12: both stages pin the base image by immutable
# manifest-index digest instead of the floating `ubuntu:24.04` tag, so a
# rebuild of the same source on a fresh GitHub-hosted runner starts from
# exactly the same base bytes. The digest is declared once in
# tools/build_production.py (PRODUCTION_BASE_IMAGE_DIGEST) and a guard test
# fails if this file and that declaration drift apart.

FROM ubuntu:24.04@sha256:33ceb71981b602c1a7443a53469e4dba065f7503eab3078a2d7a57a2ab987517 AS builder

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3.12 python3.12-venv python3.12-dev python3-pip \
      build-essential portaudio19-dev libsndfile1-dev ca-certificates && \
    rm -rf /var/lib/apt/lists/*

RUN python3.12 -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

WORKDIR /build
COPY api_fastapi_server/requirements.txt /build/api_fastapi_server/requirements.txt
COPY dist/voicestt/*.whl /build/dist/voicestt/
COPY dist/kroko/*.whl /build/dist/kroko/

# AP-SRV-070 W4C, requirement 7.1/7.2: a pre-built wheel is installed for
# both VoiceSTT and Kroko - no editable install, no source checkout as the
# runtime basis, no native Kroko compilation in this build.
RUN VOICESTT_WHEEL="$(ls /build/dist/voicestt/*.whl)" && \
    python -m pip install --upgrade pip setuptools wheel && \
    python -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu && \
    python -m pip install /build/dist/kroko/*.whl && \
    python -m pip install "${VOICESTT_WHEEL}[faster-whisper,silero-onnx-cpu,server]" \
      -r /build/api_fastapi_server/requirements.txt scikit-learn requests && \
    python -m pip install --no-deps 'openwakeword==0.6.0' && \
    sed -i '/^Requires-Dist: tflite-runtime/d' \
      /opt/venv/lib/python3.12/site-packages/openwakeword-*.dist-info/METADATA && \
    python -m pip check


FROM ubuntu:24.04@sha256:33ceb71981b602c1a7443a53469e4dba065f7503eab3078a2d7a57a2ab987517 AS runtime

ARG VOICESTT_VERSION=unknown
ARG VOICESTT_GIT_COMMIT=unknown
ARG VOICESTT_KROKO_VARIANT=free
ARG BUILD_DATE=unknown

LABEL org.opencontainers.image.title="voice-stt-server" \
      org.opencontainers.image.description="VoiceSTT FastAPI production server (CPU, Ubuntu 24.04)" \
      org.opencontainers.image.version="${VOICESTT_VERSION}" \
      org.opencontainers.image.revision="${VOICESTT_GIT_COMMIT}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.source="https://github.com/marcosudau-vps/voice-stt-server" \
      org.opencontainers.image.licenses="MIT" \
      com.voicestt.kroko-variant="${VOICESTT_KROKO_VARIANT}"

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:${PATH}" \
    VOICESTT_CPU_ONLY=1 \
    VOICESTT_OFFLINE_MODELS=1 \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    VOICESTT_DATA_ROOT=/var/lib/voicestt

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3.12 libportaudio2 libasound2t64 libsndfile1 libgomp1 ca-certificates && \
    rm -rf /var/lib/apt/lists/* && \
    groupadd --system --gid 10001 voicestt && \
    useradd --system --uid 10001 --gid voicestt --home-dir /var/lib/voicestt \
      --shell /usr/sbin/nologin voicestt && \
    mkdir -p /var/lib/voicestt/models/stt/fasterwhisper \
             /var/lib/voicestt/models/stt/kroko_asr && \
    chown -R voicestt:voicestt /var/lib/voicestt

COPY --from=builder /opt/venv /opt/venv

USER voicestt
WORKDIR /var/lib/voicestt
VOLUME ["/var/lib/voicestt"]

EXPOSE 8010

# AP-SRV-070 W4C, section 10: liveness only. The server always answers
# /health with HTTP 200, even with no STT model loaded (ready=false is a
# valid, administrable NOT_READY state - see VoiceSTT_server/stt_model_management.py
# and api_fastapi_server/server.py's /health handler). Docker health must
# only prove the control plane/process is alive and serving requests; it
# must never gate on a model being loaded, or a container with no model
# provisioned yet would be marked unhealthy and restart-looped forever.
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
  CMD python3.12 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8010/health', timeout=5).getcode() == 200 or exit(1)" || exit 1

ENTRYPOINT ["python3.12", "-m", "VoiceSTT_server.server"]
CMD ["--host", "0.0.0.0", "--port", "8010", \
     "--device", "cpu", "--compute-type", "int8", \
     "--engine-options", "{\"local_files_only\":true}", \
     "--realtime-engine-options", "{\"local_files_only\":true}"]
