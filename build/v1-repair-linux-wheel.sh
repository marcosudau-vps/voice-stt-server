#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo 'usage: v1-repair-linux-wheel.sh PRODUCT_OUTPUT_DIR' >&2
  exit 2
fi

out="$(realpath "$1")"
shopt -s nullglob
raw_wheels=("$out"/*-linux_x86_64.whl)
if [ "${#raw_wheels[@]}" -ne 1 ]; then
  echo "expected exactly one raw Linux product wheel in $out" >&2
  exit 2
fi
raw="${raw_wheels[0]}"
image='voicestt-v1-wheel-repair:manylinux-2-35'
docker build -f build/v1-wheel-repair.Dockerfile -t "$image" .
repair_dir="$out/.auditwheel-repaired"
if [ -e "$repair_dir" ]; then
  echo "refusing to reuse an existing auditwheel output directory: $repair_dir" >&2
  exit 2
fi
mkdir "$repair_dir"
docker run --rm --network none --user "$(id -u):$(id -g)" \
  --volume "$out:/wheels" "$image" repair \
  --plat manylinux_2_35_x86_64 --wheel-dir /wheels/.auditwheel-repaired \
  "/wheels/$(basename "$raw")"

repaired_wheels=("$repair_dir"/*-manylinux_2_35_x86_64.whl)
if [ "${#repaired_wheels[@]}" -ne 1 ]; then
  echo 'auditwheel did not produce exactly one manylinux_2_35_x86_64 wheel' >&2
  exit 2
fi
repaired="${repaired_wheels[0]}"
docker run --rm --network none --volume "$out:/wheels:ro" "$image" show \
  "/wheels/.auditwheel-repaired/$(basename "$repaired")"
python tools/v1_product_wheel.py inspect "$repaired" > "$out/product.json"
python -m twine check "$repaired"
mv "$repaired" "$out/"
rmdir "$repair_dir"
rm -- "$raw"
