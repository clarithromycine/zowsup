# mlow_c

C/C++ implementation of the MLow (SMPL) audio codec.

## 目录结构

```
mlow_c/
├── CMakeLists.txt          # 跨平台构建 (Windows/macOS/Linux/ARM)
├── include/
│   └── mlow.h              # 公共 C ABI
├── src/
│   ├── mlow_internal.h     # 内部接口
│   ├── bridge.c            # C ABI 入口
│   ├── mlow_decoder.c      # 解码器生命周期
│   ├── mlow_encoder.c      # 编码器生命周期
│   ├── tables_init.c       # 全局表初始化
│   ├── range_coder.c       # 熵编码器
│   ├── mem.c               # WASM 堆布局模拟
│   ├── tables/
│   │   ├── cc_tables.c     # 能量/增益/pulse 表
│   │   ├── lsf_seed.c       # LSF 种子表展开
│   │   └── pitch_seed.c     # pitch 种子表展开
│   ├── decode/
│   │   ├── decoder.c        # 解码器顶层
│   │   ├── synth.c          # NLSF→LPC 合成
│   │   ├── celp_dec.c       # CELP 解码
│   │   ├── post_filter.c    # 谐波后滤波
│   │   ├── noise.c          # 噪声生成
│   │   ├── red.c            # RED 冗余拆包
│   │   └── toc.c            # TOC 路由
│   └── encode/
│       ├── encoder.c        # 编码器顶层
│       ├── analysis.c       # 分析前端
│       ├── lpc.c            # LPC 前端
│       ├── pitch_enc.c      # pitch 估计
│       ├── celp_enc.c       # CELP 激励编码
│       ├── lsf_quant.c      # LSF 量化
│       ├── perc.c           # 感知模型
│       ├── vad.c            # 语音活动检测
│       ├── gains.c          # 增益表
│       ├── pulse.c          # 脉冲编码
│       ├── fft.c            # FFT
│       ├── pitch.c          # pitch 合成
│       ├── lsf.c            # LSF 操作
│       └── logging.c        # 日志
├── data/
│   ├── cc_seed.bin         # 能量/增益/pulse 种子数据 (2.1 KB)
│   ├── lsf_seed.bin        # LSF 种子数据 (30 KB)
│   └── pitch_seed.bin      # pitch 种子数据 (2.3 KB)
└── third_party/
    └── miniz/              # 单文件 zlib 替代库
        ├── miniz.c
        └── miniz.h
```

## 构建

### macOS / Linux

```bash
cd mlow_c
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel
```

产物: `build/libmlow_decoder.dylib` (macOS) 或 `build/libmlow_decoder.so` (Linux)

### Windows (交叉编译)

```bash
cmake -B build-win -DCMAKE_SYSTEM_NAME=Windows \
  -DCMAKE_C_COMPILER=x86_64-w64-mingw32-gcc \
  -DCMAKE_CXX_COMPILER=x86_64-w64-mingw32-g++
cmake --build build-win --parallel
```

产物: `build-win/mlow_decoder.dll`

### ARM64 (交叉编译)

```bash
cmake -B build-arm -DCMAKE_SYSTEM_NAME=Linux \
  -DCMAKE_C_COMPILER=aarch64-linux-gnu-gcc \
  -DCMAKE_CXX_COMPILER=aarch64-linux-gnu-g++
cmake --build build-arm --parallel
```

## 接口

9 个导出函数：

| 函数 | 签名 |
|------|------|
| `mlow_decoder_create` | `uint64_t ()` → handle |
| `mlow_decoder_destroy` | `void (uint64_t)` |
| `mlow_decoder_reset` | `void (uint64_t)` |
| `mlow_set_redundancy` | `void (uint64_t, int)` |
| `mlow_decode` | `int (uint64_t, const uint8_t*, int, float*, int)` |
| `mlow_encoder_create` | `uint64_t ()` → handle |
| `mlow_encoder_destroy` | `void (uint64_t)` |
| `mlow_encoder_reset` | `void (uint64_t)` |
| `mlow_encode` | `int (uint64_t, const float*, int, uint8_t*, int)` |

Python 侧 (`voip/media/codec.py`) 通过 ctypes 加载共享库，支持多路并发编解码（每路通话创建独立实例，FFT scratch buffer 使用 thread-local 存储）。