# V1 preservation release: standalone Kroko Linux/AMD64 builder.
#
# This intentionally preserves the V1 build semantics in
# VoiceSTT/install_kroko.py.  It does not import the later V2 Kroko runtime or
# model-management architecture.  The release wrapper only pins the upstream
# source revision and records/validates the produced wheel identity.
FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential cmake git libssl-dev pybind11-dev zlib1g-dev && \
    rm -rf /var/lib/apt/lists/*

# Kroko's current cmake extension still needs wheel.bdist_wheel, which is
# present in wheel 0.45.x.  Pin the Python-side packaging toolchain used by the
# candidate builder rather than following latest on every runner.
RUN python -m pip install --upgrade "pip==26.2.1" && \
    python -m pip install "setuptools==75.8.2" "wheel==0.45.1"

WORKDIR /src
COPY VoiceSTT/install_kroko.py VoiceSTT/install_kroko.py
COPY tools/v1_kroko_release.py tools/v1_kroko_release.py
COPY build/v1-kroko-builder.Dockerfile build/v1-kroko-builder.Dockerfile

ENTRYPOINT ["python", "tools/v1_kroko_release.py"]
