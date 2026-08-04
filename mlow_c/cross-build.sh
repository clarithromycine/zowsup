#!/bin/bash
# cross-build.sh — Cross-compile mlow_c for Linux & Windows using zig cc.
# Run from mlow_c/ directory.
set -e

SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
LIB_DIR="$SRC_DIR/../lib"
BUILD_DIR="$SRC_DIR/build_x"
mkdir -p "$BUILD_DIR" "$LIB_DIR"

# Collect all C sources (same as CMakeLists.txt)
SOURCES=(
    src/bridge.c src/mlow_decoder.c src/mlow_encoder.c
    src/tables_init.c src/seed.c src/range_coder.c src/mem.c
    src/tables/cc_tables.c src/tables/lsf_seed.c src/tables/pitch_seed.c
    src/decode/decoder.c src/decode/synth.c src/decode/celp_dec.c
    src/decode/post_filter.c src/decode/noise.c src/decode/red.c src/decode/toc.c
    src/encode/encoder.c src/encode/analysis.c src/encode/lpc.c src/encode/bitrate.c
    src/encode/pitch_enc.c src/encode/celp_enc.c src/encode/lsf_quant.c
    src/encode/perc.c src/encode/vad.c src/encode/gains.c src/encode/pulse.c
    src/encode/fft.c src/encode/pitch.c src/encode/lsf.c src/encode/logging.c
    third_party/miniz/miniz.c third_party/miniz/miniz_tinfl.c third_party/miniz/miniz_tdef.c
)

CFLAGS=(
    -Iinclude -Isrc -Ithird_party/miniz
    -std=c11 -O3 -ffast-math -fno-math-errno
    -Wall -Wextra -Wno-unused-parameter
    -fPIC -shared
)

echo "=== Linux x86_64 ==="
zig cc -target x86_64-linux-gnu "${CFLAGS[@]}" -o "$LIB_DIR/mlow_decoder_c.so" "${SOURCES[@]}"
echo "✅ $LIB_DIR/mlow_decoder_c.so ($(du -sh "$LIB_DIR/mlow_decoder_c.so" | cut -f1))"

echo "=== Linux arm64 ==="
zig cc -target aarch64-linux-gnu "${CFLAGS[@]}" -o "$LIB_DIR/mlow_decoder_c_arm64.so" "${SOURCES[@]}"
echo "✅ $LIB_DIR/mlow_decoder_c_arm64.so ($(du -sh "$LIB_DIR/mlow_decoder_c_arm64.so" | cut -f1))"

echo "=== Windows x86_64 ==="
zig cc -target x86_64-windows-gnu -DMLOW_EXPORTS "${CFLAGS[@]}" -o "$LIB_DIR/mlow_decoder_c.dll" "${SOURCES[@]}"
echo "✅ $LIB_DIR/mlow_decoder_c.dll ($(du -sh "$LIB_DIR/mlow_decoder_c.dll" | cut -f1))"

echo "=== macOS arm64 (native) ==="
cc "${CFLAGS[@]}" -o "$LIB_DIR/mlow_decoder_c.dylib" "${SOURCES[@]}"
echo "✅ $LIB_DIR/mlow_decoder_c.dylib ($(du -sh "$LIB_DIR/mlow_decoder_c.dylib" | cut -f1))"

echo ""
echo "All done:"
ls -lh "$LIB_DIR"/mlow_decoder_c.*
