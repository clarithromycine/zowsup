# ──────────────────────────────────────────────────────────────────────────────
# mlow_c — C/C++ implementation of the MLow (SMPL) audio codec
#
# Produces a shared library named:
#   mlow_decoder.dll  (Windows)
#   mlow_decoder.dylib (macOS)
#   mlow_decoder.so    (Linux)
#
# The Python ctypes loader (voip/media/codec.py) picks up the
# shared library from lib/mlow_decoder_c.{dll,dylib,so}.
# ──────────────────────────────────────────────────────────────────────────────
cmake_minimum_required(VERSION 3.16)
project(mlow_c C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ── Build type ────────────────────────────────────────────────────────────────
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

# ── Output name: always "mlow_decoder" (matches Python loader) ────────────────
set(LIB_OUTPUT_NAME mlow_decoder)

# ── Compiler flags ────────────────────────────────────────────────────────────
# Performance: -O3, native math, no debug overhead in Release
add_compile_options(
    $<$<CONFIG:Release>:-O3>
    $<$<CONFIG:Release>:-ffast-math>
    $<$<CONFIG:Release>:-fno-math-errno>
    $<$<CONFIG:Release>:-funroll-loops>
    $<$<CONFIG:Release>:-fomit-frame-pointer>
)

# Disable miniz ZIP archive APIs — we only need zlib inflate/deflate.
# This avoids errno_t / _wfopen_s portability issues on MinGW.
add_compile_definitions(MINIZ_NO_ARCHIVE_APIS MINIZ_NO_ARCHIVE_WRITING_APIS)

# Warnings as errors for our own code
if(MSVC)
    add_compile_options(/W4 /WX)
else()
    add_compile_options(-Wall -Wextra -Wpedantic -Wno-unused-parameter)
endif()

# ── SIMD detection (used later for platform-specific intrinsics) ─────────────
include(CheckCXXCompilerFlag)
option(MLOW_ENABLE_SIMD "Enable SIMD intrinsics" ON)

if(MLOW_ENABLE_SIMD)
    if(CMAKE_SYSTEM_PROCESSOR MATCHES "x86_64|amd64|AMD64|x86")
        check_cxx_compiler_flag("-msse2" HAVE_SSE2)
        check_cxx_compiler_flag("-mavx2" HAVE_AVX2)
        if(HAVE_AVX2)
            add_compile_options(-mavx2 -mfma)
            add_compile_definitions(MLOW_SSE2 MLOW_AVX2 MLOW_FMA)
        elseif(HAVE_SSE2)
            add_compile_options(-msse2)
            add_compile_definitions(MLOW_SSE2)
        endif()
    elseif(CMAKE_SYSTEM_PROCESSOR MATCHES "aarch64|arm64|ARM64")
        # ARM NEON is always available on aarch64
        add_compile_definitions(MLOW_NEON)
    elseif(CMAKE_SYSTEM_PROCESSOR MATCHES "arm")
        check_cxx_compiler_flag("-mfpu=neon" HAVE_ARM_NEON)
        if(HAVE_ARM_NEON)
            add_compile_options(-mfpu=neon)
            add_compile_definitions(MLOW_NEON)
        endif()
    endif()
endif()

# ── zlib (for seed decompression) ─────────────────────────────────────────────
# We use miniz (single-file) to avoid a hard zlib dependency on every platform.
# miniz is vendored under third_party/miniz/.

# ── Sources ───────────────────────────────────────────────────────────────────
set(MLOW_SOURCES
    src/bridge.c
    src/mlow_decoder.c
    src/mlow_encoder.c
    src/tables_init.c
    src/seed.c
    src/range_coder.c
    src/mem.c
    src/tables/cc_tables.c
    src/tables/lsf_seed.c
    src/tables/pitch_seed.c
    src/decode/decoder.c
    src/decode/synth.c
    src/decode/celp_dec.c
    src/decode/post_filter.c
    src/decode/noise.c
    src/decode/red.c
    src/decode/toc.c
    src/encode/encoder.c
    src/encode/analysis.c
    src/encode/lpc.c
    src/encode/bitrate.c
    src/encode/pitch_enc.c
    src/encode/celp_enc.c
    src/encode/lsf_quant.c
    src/encode/perc.c
    src/encode/vad.c
    src/encode/gains.c
    src/encode/pulse.c
    src/encode/fft.c
    src/encode/pitch.c
    src/encode/lsf.c
    src/encode/logging.c
    third_party/miniz/miniz.c
    third_party/miniz/miniz_tinfl.c
    third_party/miniz/miniz_tdef.c
)

# ── Shared library ───────────────────────────────────────────────────────────
add_library(${LIB_OUTPUT_NAME} SHARED ${MLOW_SOURCES})

# ── Include paths ─────────────────────────────────────────────────────────────
target_include_directories(${LIB_OUTPUT_NAME}
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/include
        ${CMAKE_CURRENT_SOURCE_DIR}/src
        ${CMAKE_CURRENT_SOURCE_DIR}/third_party/miniz
)

# ── Threading library (pthread used by bridge.c handle registry) ─────────────
find_package(Threads REQUIRED)
target_link_libraries(${LIB_OUTPUT_NAME} PRIVATE Threads::Threads)

# ── Platform-specific link flags ──────────────────────────────────────────────
if(WIN32)
    target_compile_definitions(${LIB_OUTPUT_NAME} PRIVATE MLOW_EXPORTS)
    set_target_properties(${LIB_OUTPUT_NAME} PROPERTIES
        WINDOWS_EXPORT_PREFIX "mlow_"
    )
elseif(APPLE)
    set_target_properties(${LIB_OUTPUT_NAME} PROPERTIES
        INSTALL_NAME_DIR "@rpath"
    )
endif()

# ── Install (optional) ────────────────────────────────────────────────────────
include(GNUInstallDirs)
install(TARGETS ${LIB_OUTPUT_NAME}
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)

# ── Cross-compile helper targets ──────────────────────────────────────────────
# Usage examples:
#   cmake -B build-linux-x86  -DCMAKE_C_COMPILER=x86_64-linux-gnu-gcc ...
#   cmake -B build-arm        -DCMAKE_C_COMPILER=aarch64-linux-gnu-gcc ...
#   cmake -B build-win         -DCMAKE_SYSTEM_NAME=Windows \
#                              -DCMAKE_C_COMPILER=x86_64-w64-mingw32-gcc ...
#   cmake -B build-mac-arm     -DCMAKE_SYSTEM_NAME=Darwin \
#                              -DCMAKE_OSX_ARCHITECTURES=arm64 ...
#   cmake -B build-mac-x86     -DCMAKE_SYSTEM_NAME=Darwin \
#                              -DCMAKE_OSX_ARCHITECTURES=x86_64 ...