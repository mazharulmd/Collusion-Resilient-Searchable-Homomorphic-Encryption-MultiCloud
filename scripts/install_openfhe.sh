#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#
# Build and install OpenFHE, which supplies the BFV layer.  Without it the
# build still succeeds but only the plaintext stand-in backend is available,
# and every benchmark refuses to emit HE numbers from it.
#
#   scripts/install_openfhe.sh [install-prefix] [version-tag]
#
# Then configure the project with:
#   cmake -S . -B build -DCMAKE_PREFIX_PATH=<install-prefix>
set -euo pipefail

PREFIX="${1:-$HOME/.local/openfhe}"
TAG="${2:-v1.2.3}"
SRC="${TMPDIR:-/tmp}/openfhe-src-$TAG"
BUILD="${TMPDIR:-/tmp}/openfhe-build-$TAG"
JOBS="$(nproc)"

echo "== OpenFHE $TAG -> $PREFIX (using $JOBS jobs) =="

if [ ! -d "$SRC" ]; then
    git clone --depth 1 --branch "$TAG" \
        https://github.com/openfheorg/openfhe-development.git "$SRC"
fi

cmake -S "$SRC" -B "$BUILD" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="$PREFIX" \
    -DBUILD_UNITTESTS=OFF \
    -DBUILD_EXAMPLES=OFF \
    -DBUILD_BENCHMARKS=OFF \
    -DBUILD_STATIC=OFF \
    -DWITH_OPENMP=ON

cmake --build "$BUILD" -j "$JOBS"
cmake --install "$BUILD"

cat <<EOF

OpenFHE installed to $PREFIX

Add the runtime library path to your shell profile:

  export LD_LIBRARY_PATH="$PREFIX/lib:\$LD_LIBRARY_PATH"

Then build CR-SHE:

  cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="$PREFIX"
  cmake --build build -j $JOBS

and confirm the BFV backend is live:

  ./build/test_he
EOF
