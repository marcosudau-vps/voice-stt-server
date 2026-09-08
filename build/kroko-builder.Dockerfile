# AP-SRV-070 W4C/W5-R04: standalone Linux/AMD64 Kroko-ONNX builder.
#
# This is the continuation of the pre-W4C Dockerfile "kroko-builder" stage
# (see build/BUILD.md): a Linux container that has the native toolchain
# Kroko needs (cmake, a C/C++ compiler, git, OpenSSL/pybind11/zlib headers)
# and runs the existing, unmodified VoiceSTT.install_kroko builder/
# fingerprint/artifact-store authority (VoiceSTT/kroko/*) inside it.
#
# It is driven by tools/build_production.py. It is never referenced by the
# production Dockerfile and never runs as part of a production image build -
# see build/BUILD.md 7.2 (no Kroko builder stage, no native Kroko compilation
# in the production Docker build).
#
# W5-R04, prompt section 12: every value below is the source-controlled
# declaration in VoiceSTT/kroko/buildinputs.py (LINUX_BUILDER_BASE_IMAGE*,
# LINUX_BUILDER_APT_PACKAGES, LINUX_BUILDER_PACKAGING_TOOLS). A guard test
# (tests/unit/test_kroko_fingerprint.py) fails if this file and that
# declaration drift apart, or if either changes without bumping
# LINUX_BUILDER_REVISION - which is a fingerprint input, so a builder change
# can never silently reuse an artifact built by the previous builder.
#
# The artifact store (VOICESTT_KROKO_ARTIFACT_STORE) is bind-mounted into the
# container at run time so a REUSE hit or a freshly built, verified artifact
# both land back on the caller's store. On a GitHub-hosted runner that store
# is a workspace directory restored from (and saved to) the Actions cache; no
# operator-local store is ever required.
FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential cmake git libssl-dev pybind11-dev zlib1g-dev && \
    rm -rf /var/lib/apt/lists/*

# Pinned exactly: these decide how the produced Kroko wheel is built and
# tagged. wheel is held below 0.46 deliberately - upstream's
# cmake/cmake_extension.py imports wheel.bdist_wheel, which 0.46 removed.
RUN python -m pip install --upgrade "pip==26.2.1" && \
    python -m pip install "setuptools==75.8.2" "wheel==0.45.1"

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
