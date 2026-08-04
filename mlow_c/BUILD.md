# mlow_c — Build Guide

C implementation of the MLow (SMPL) audio codec.

## Quick Start (macOS)

```bash
cd mlow_c
cmake -B build -G "Unix Makefiles" -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel

# Output: build/libmlow_decoder.dylib
```

## Cross-Compile All Platforms

Uses `zig cc` for Linux and `mingw-w64` for Windows:

```bash
cd mlow_c
./cross-build.sh

# Outputs to ../lib/:
#   mlow_decoder_c.dylib   macOS arm64
#   mlow_decoder_c.so      Linux x86_64
#   mlow_decoder_c.dll     Windows x86_64
```

### Prerequisites

| Platform | Tool |
|----------|------|
| macOS | Xcode CLT / Homebrew clang |
| Linux cross | `brew install zig` |
| Windows cross | `brew install mingw-w64` |

## Directory Structure

```
mlow_c/
├── src/
│   ├── bridge.c          # C ABI exports (mlow_decode, mlow_encode, ...)
│   ├── mlow_decoder.c    # Decoder lifecycle
│   ├── mlow_encoder.c    # Encoder lifecycle
│   ├── decode/           # Decoder internals (CELP, post filter, noise, RED)
│   ├── encode/           # Encoder internals (analysis, CELP enc, LPC, FFT, ...)
│   └── tables/           # Pre-computed codebook tables
├── include/              # Public headers
├── third_party/miniz/    # zlib replacement (no external deps)
├── cmake/                # CMake toolchain files (cross-compile)
├── tools/                # Seed header generator
├── tests/                # Comparison & validation tests
├── cross-build.sh        # All-platform build script
├── CMakeLists.txt        # CMake build (macOS native)
└── README.md
```

## Running Tests

```bash
# Range decoder test
python3 tests/rd_test.py
```

## Using in Python (voip/media/codec.py)

```bash
python script/main.py <number>
```

The C library must be placed in `lib/mlow_decoder_c.{dylib,so,dll}`.

## Performance

### Current Benchmark (macOS arm64, Release)

| Operation | Latency | Real-time budget (60ms) | CPU usage |
|-----------|--------|-------------------------|-----------|
| Encode | 0.70ms/frame | 16.7ms | ~4% |
| Decode | 0.05ms/frame | 16.7ms | ~0.3% |

### Optimization History

| Phase | Change | Encode speedup | CPU on weak CPU |
|-------|--------|---------------|-----------------|
| Baseline | Recursive FFT + per-frame calloc | — | 17-20% |
| Phase 1 | Pre-allocate scratch buffers | 1× (no measurable gain) | 17-23% |
| Phase 2 | FFT twiddle lookup table + scratch pre-alloc | 3× (2.12→0.70ms) | 14-17% |

### Future Optimization Directions

#### P1: Gain lookup table precomputation
- **Location**: `src/encode/analysis.c` `smpl_rate_control_gains`
- **Issue**: 84×98 = 8232 calls to `smpl_gain_lin` per frame, each doing `memcpy` for bit reinterpretation
- **Fix**: Precompute the full 84×98 gain table at init time
- **Est. impact**: Eliminates ~8000 function calls/frame

#### P2: Compiler optimization flags
- **Issue**: Missing `-flto` (Link-Time Optimization) and `-march=native`
- **Fix**: Add to CMakeLists.txt Release flags:
  ```cmake
  add_compile_options($<$<CONFIG:Release>:-flto>)
  add_compile_options($<$<CONFIG:Release>:-march=native>)
  ```
- **Est. impact**: Cross-function inlining of `celp_dot_prod`, `cpx_mul`, etc. + auto-vectorization of FIR/dot-product loops

#### P3: Double → float in decode path
- **Location**: `src/decode/synth.c` `smpl_lpc_synthesis` (uses `double` accumulator), `smpl_nlsf2a` (uses `cos()` not `cosf()`)
- **Issue**: `double` prevents SIMD vectorization of 16-tap IIR filter
- **Fix**: Switch to `float` accumulator + `cosf()`
- **Est. impact**: Enables auto-vectorization of LPC synthesis loop

#### P4: `smpl_mem` region lookup optimization
- **Location**: `src/mem.c` `region_for()` — linear scan of up to 16 regions
- **Fix**: Binary search or direct hash
- **Est. impact**: Small (reduces pitch decode overhead)

#### P5: `registry_get` optimization
- **Location**: `src/bridge.c` — linear scan + global mutex per `mlow_decode`/`mlow_encode` call
- **Fix**: Direct pointer storage instead of handle lookup
- **Est. impact**: Small (only matters with many concurrent decoders)

#### P6: Iterative FFT (retry)
- **Issue**: Phase 2 v1 (iterative radix-2/3) had audio quality bug — 9-point DFT twiddle indexing error
- **Fix**: Debug the Cooley-Tukey cross-twiddle for 576=64×9 decomposition, or use Bluestein for the 9 factor
- **Est. impact**: Additional 2× on top of Phase 2 v2 (0.70ms → ~0.35ms)
