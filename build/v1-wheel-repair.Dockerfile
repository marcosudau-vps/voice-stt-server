# Repair public Linux product wheels in the same pinned Bookworm ABI family as
# the native Kroko builder and the V1 runtime image. The hosted runner's glibc
# must not determine the wheel's manylinux floor.
FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254

RUN python -m pip install --no-cache-dir --disable-pip-version-check \
    auditwheel==6.8.2 patchelf==0.19.1

ENTRYPOINT ["auditwheel"]
