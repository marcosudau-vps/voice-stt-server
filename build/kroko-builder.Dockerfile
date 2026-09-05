# AP-SRV-070 W4C: standalone Linux/AMD64 Kroko-ONNX builder.
#
# This is the continuation of the pre-W4C Dockerfile "kroko-builder" stage
# (see build/BUILD.md): a Linux container that has the native toolchain
# Kroko needs (cmake, a C/C++ compiler, git, OpenSSL/zlib headers) and runs
# the existing, unmodified VoiceSTT.install_kroko builder/fingerprint/
# artifact-store authority (VoiceSTT/kroko/*) inside it.
#
# W4C runs this image standalone, driven by tools/build_production.py, on a
# Windows host that cannot itself produce a Linux/AMD64 Kroko wheel. It is
# never referenced by the production Dockerfile and never runs as part of a
# production image build - see build/BUILD.md 7.2 (no Kroko builder stage,
# no native Kroko compilation in the production Docker build).
#
# The persistent Kroko artifact store (VOICESTT_KROKO_ARTIFACT_STORE) is
# bind-mounted into the container at run time so a REUSE hit or a freshly
# built, verified artifact both land back on the host.
FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential cmake git libssl-dev pybind11-dev zlib1g-dev && \
    rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip setuptools wheel && \
    python -m pip install huggingface_hub

WORKDIR /build/voicestt

# Only the Kroko builder/fingerprint/artifact-store authority itself, plus
# the version resolver it transitively imports through VoiceSTT/__init__.py
# and the source-controlled VERSION file it reads - never the rest of the
# project source tree.
COPY VERSION VERSION
COPY VoiceSTT/__init__.py VoiceSTT/__init__.py
COPY VoiceSTT/_version.py VoiceSTT/_version.py
COPY VoiceSTT/install_kroko.py VoiceSTT/install_kroko.py
COPY VoiceSTT/kroko/ VoiceSTT/kroko/

ENTRYPOINT ["python", "-m", "VoiceSTT.install_kroko"]
CMD ["--describe-artifact", "--variant", "free"]
