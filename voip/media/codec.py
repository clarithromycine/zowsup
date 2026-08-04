"""
Audio codec abstraction and Opus wrapper for WhatsApp VoIP.

WhatsApp uses Opus for audio encoding at 16kHz, mono, with ~6kbps bitrate.
960 samples per frame = 60ms @ 16kHz.

This module provides:
- Codec ABC (abstract base class)
- OpusCodec (libopus via ctypes)

Reference: WaCalls internal/voip/media/codec.go, mlow_codec_native.go
"""

import ctypes
import ctypes.util
import struct
import logging
import math
from array import array
from abc import ABC, abstractmethod
from typing import Optional

log = logging.getLogger(__name__)

# WhatsApp audio constants
WHATSAPP_SAMPLE_RATE = 16000
WHATSAPP_FRAME_SIZE = 960  # 60ms @ 16kHz
WHATSAPP_CHANNELS = 1

# Default codec options
DEFAULT_BITRATE = 6000
DEFAULT_COMPLEXITY = 5


class Codec(ABC):
    """Abstract audio codec interface."""

    @abstractmethod
    def encode(self, pcm: list[float]) -> bytes:
        """Encode PCM float samples to compressed bytes."""
        ...

    @abstractmethod
    def decode(self, frame: bytes) -> list[float]:
        """Decode compressed bytes to PCM float samples."""
        ...

    @abstractmethod
    def frame_size(self) -> int:
        """Number of samples per encoded frame."""
        ...

    @abstractmethod
    def sample_rate(self) -> int:
        """Sample rate in Hz."""
        ...

    @abstractmethod
    def close(self):
        """Release codec resources."""
        ...


class OpusCodec(Codec):
    """
    libopus wrapper via ctypes.

    Usage:
        codec = OpusCodec(bitrate=6000, complexity=5)
        encoded = codec.encode(pcm_samples)
        decoded = codec.decode(encoded)
        codec.close()
    """

    # libopus constants
    OPUS_APPLICATION_VOIP = 2048
    OPUS_APPLICATION_RESTRICTED_LOWDELAY = 2051  # forces CELT-only
    OPUS_SET_BITRATE = 4002
    OPUS_SET_COMPLEXITY = 4010
    OPUS_SET_SIGNAL = 4024
    OPUS_SIGNAL_VOICE = 3001
    OPUS_SET_USE_SMPL_REQUEST = 4050  # enable MLow/SMPL (replaces SILK)
    OPUS_SET_DTX = 4016              # enable DTX (comfort noise on silence)

    def __init__(
        self,
        bitrate: int = DEFAULT_BITRATE,
        complexity: int = DEFAULT_COMPLEXITY,
        sample_rate: int = WHATSAPP_SAMPLE_RATE,
        frame_size: int = WHATSAPP_FRAME_SIZE,
        channels: int = WHATSAPP_CHANNELS,
    ):
        self._sample_rate = sample_rate
        self._frame_size = frame_size
        self._channels = channels
        self._bitrate = bitrate
        self._complexity = complexity

        self._lib = None
        self._encoder = None
        self._decoder = None
        self._available = False

        self._load_library()

    @property
    def available(self) -> bool:
        """Whether libopus was loaded successfully."""
        return self._available

    def _load_library(self):
        """Load libopus via ctypes — ALWAYS use raw C API for correct CTL handling.

        opuslib wraps encoder/decoder in Python objects which break raw CTL calls
        like OPUS_SET_USE_SMPL_REQUEST (needs C pointer, gets Python object).
        """
        import os, platform

        # ── ctypes CDLL path first (direct C API, correct CTL) ──
        lib_paths = []
        proj_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        for name in ["libopus_mlow.dll", "libopus.dll", "opus.dll", "libopus-0.dll"]:
            lib_paths.append(os.path.join(proj_dir, name))
            lib_paths.append(os.path.join(proj_dir, "lib", name))
        if platform.system() == "Windows":
            lib_paths += ["libopus_mlow.dll", "opus.dll", "libopus-0.dll", "libopus.dll"]
        elif platform.system() == "Darwin":
            lib_paths += ["libopus.0.dylib", "libopus.dylib"]
        else:
            lib_paths += ["libopus.so.0", "libopus.so"]

        found = ctypes.util.find_library("opus")
        if found:
            lib_paths.insert(0, found)

        for path in lib_paths:
            try:
                self._lib = ctypes.CDLL(path)
                log.info("OpusCodec: loaded %s", path)
                break
            except OSError:
                continue

        if self._lib is None:
            log.warning("libopus not found — OpusCodec unavailable (signaling-only mode)")
            return

        # Configure function signatures
        self._lib.opus_encoder_create.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_int),
        ]
        self._lib.opus_encoder_create.restype = ctypes.c_void_p

        self._lib.opus_decoder_create.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_int),
        ]
        self._lib.opus_decoder_create.restype = ctypes.c_void_p

        self._lib.opus_encode.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_short), ctypes.c_int,
            ctypes.c_char_p, ctypes.c_int,
        ]
        self._lib.opus_encode.restype = ctypes.c_int

        self._lib.opus_decode.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int,
            ctypes.POINTER(ctypes.c_short), ctypes.c_int, ctypes.c_int,
        ]
        self._lib.opus_decode.restype = ctypes.c_int

        self._lib.opus_encoder_destroy.argtypes = [ctypes.c_void_p]
        self._lib.opus_decoder_destroy.argtypes = [ctypes.c_void_p]

        # ── MLow/SMPL global init (required once before any encoder/decoder) ──
        try:
            self._lib.opus_global_create.argtypes = []
            self._lib.opus_global_create.restype = None
            self._lib.opus_global_create()
            log.info("OpusCodec: opus_global_create() called — MLow tables initialized")
        except Exception:
            pass  # not available in standard libopus

        # Configure opus_encoder_ctl (variadic → fixed 3-arg for ctypes)
        self._lib.opus_encoder_ctl.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
        self._lib.opus_encoder_ctl.restype = ctypes.c_int
        try:
            self._lib.opus_decoder_ctl.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
            self._lib.opus_decoder_ctl.restype = ctypes.c_int
        except Exception:
            pass

        # ── Create encoder (VOIP mode — MLow replaces SILK at low bitrates) ──
        err = ctypes.c_int(0)
        self._encoder = self._lib.opus_encoder_create(
            self._sample_rate, self._channels,
            self.OPUS_APPLICATION_VOIP, ctypes.byref(err),
        )
        if err.value != 0 or not self._encoder:
            log.warning("opus_encoder_create failed: error=%d", err.value)
            return

        # ── Create decoder ──
        err = ctypes.c_int(0)
        self._decoder = self._lib.opus_decoder_create(
            self._sample_rate, self._channels, ctypes.byref(err),
        )
        if err.value != 0 or not self._decoder:
            log.warning("opus_decoder_create failed: error=%d", err.value)
            self._lib.opus_encoder_destroy(self._encoder)
            self._encoder = None
            return

        # ── Enable MLow/SMPL on encoder → low-bitrate frames use MLow (9078) ──
        try:
            self._lib.opus_encoder_ctl(self._encoder, self.OPUS_SET_USE_SMPL_REQUEST, 1)
            self._using_mlow = True
            log.info("OpusCodec: SMPL/MLow ENABLED → low-bitrate frames will be 9078")
        except Exception:
            self._using_mlow = False
            log.info("OpusCodec: SMPL/MLow NOT available — using CELT-only fallback")

        # ── Enable DTX → comfort-noise on silence (matches WhatsApp behavior) ──
        try:
            self._lib.opus_encoder_ctl(self._encoder, self.OPUS_SET_DTX, 1)
            log.info("OpusCodec: DTX ENABLED (comfort noise on silence)")
        except Exception:
            pass

        # ── Configure encoder: bitrate, complexity ──
        try:
            self._lib.opus_encoder_ctl(self._encoder, self.OPUS_SET_BITRATE, self._bitrate)
            self._lib.opus_encoder_ctl(self._encoder, self.OPUS_SET_COMPLEXITY, self._complexity)
        except Exception:
            pass

        self._available = True
        log.info("OpusCodec: %dHz %dsamples MLow-ready", self._sample_rate, self._frame_size)

    def encode(self, pcm: list[float]) -> bytes:
        if not self._available:
            raise RuntimeError("OpusCodec not available")
        if len(pcm) != self._frame_size:
            raise ValueError(f"Expected {self._frame_size} samples, got {len(pcm)}")
        # float → int16: pre-alloc array + index loop
        scale = 32767.0
        arr = array('h', [0]) * self._frame_size
        for i in range(self._frame_size):
            v = int(pcm[i] * scale)
            arr[i] = 32767 if v > 32767 else (-32768 if v < -32768 else v)
        # ctypes: zero-copy from array buffer
        PCM16 = ctypes.c_short * self._frame_size
        pcm_i16 = PCM16.from_buffer(arr)
        out_buf = ctypes.create_string_buffer(1500)
        n = self._lib.opus_encode(self._encoder, pcm_i16, self._frame_size, out_buf, 1500)
        if n < 0: raise RuntimeError(f"opus_encode error: {n}")
        return bytes(out_buf[:n])

    def decode(self, frame: bytes) -> list[float]:
        if not self._available:
            raise RuntimeError("OpusCodec not available")
        arr = array('h', [0]) * self._frame_size
        pcm_i16 = (ctypes.c_short * self._frame_size).from_buffer(arr)
        n = self._lib.opus_decode(self._decoder, frame, len(frame), pcm_i16, self._frame_size, 0)
        if n <= 0:
            log.warning("opus_decode FAILED: err=%d len=%d raw=%s", n, len(frame), frame[:8].hex())
            return [0.0] * self._frame_size
        inv = 1.0 / 32768.0
        return [float(arr[i]) * inv for i in range(n)]
        # ctypes path: decode into pre-allocated array('h') for zero-copy
        arr = array('h', [0]) * self._frame_size
        pcm_i16 = (ctypes.c_short * self._frame_size).from_buffer(arr)
        n = self._lib.opus_decode(self._decoder, frame, len(frame), pcm_i16, self._frame_size, 0)
        if n <= 0:
            log.warning("opus_decode FAILED: err=%d len=%d raw=%s (first 8 bytes)",
                       n, len(frame), frame[:8].hex())
            return [0.0] * self._frame_size  # silence on decode failure
        inv = 1.0 / 32768.0
        return [float(arr[i]) * inv for i in range(n)]

    def frame_size(self) -> int:
        return self._frame_size

    def sample_rate(self) -> int:
        return self._sample_rate

    def close(self):
        if self._encoder:
            self._lib.opus_encoder_destroy(self._encoder)
            self._encoder = None
        if self._decoder:
            self._lib.opus_decoder_destroy(self._decoder)
            self._decoder = None
        self._available = False

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


class MLowCodec(Codec):
    """MLow (SMPL) codec backed by the Go mlow library via ctypes.

    Uses the shared library built from wacalls_ref/internal/voip/media/mlow_bridge/.
    WhatsApp primary-device VoIP uses MLow frames (header 0x58) at 16 kHz.
    """

    SAMPLE_RATE = 16000
    FRAME_SIZE = 960  # 60 ms @ 16 kHz

    def __init__(self):
        self._lib = None
        self._dec_handle = 0
        self._enc_handle = 0
        self._available = False
        self._load()

    @property
    def available(self) -> bool:
        return self._available

    def _load(self):
        import os, platform
        # ── Backend toggle: MLOW_BACKEND=c → use C library ──
        backend = os.environ.get("MLOW_BACKEND", "go").lower()
        is_c_backend = backend == "c"

        # Platform-appropriate shared library extension
        system = platform.system()

        if system == "Windows":
            lib_names = ["mlow_decoder_c.dll"]
        elif system == "Darwin":
            lib_names = ["mlow_decoder_c.dylib"]
        else:
            lib_names = ["mlow_decoder_c.so"]
            
        # Search for the library next to this file and in the project root
        here = os.path.dirname(os.path.abspath(__file__))
        proj = os.path.dirname(os.path.dirname(here))
        for base in [here, proj, os.path.join(proj, "lib"), os.getcwd()]:
            for name in lib_names:
                path = os.path.join(base, name)
                if os.path.exists(path):
                    try:
                        self._lib = ctypes.CDLL(path)
                        log.info("MLowCodec: loaded %s (backend=%s)", path, "C" if is_c_backend else "Go")
                        break
                    except OSError as e:
                        log.warning("MLowCodec: failed to load %s: %s", path, e)
            if self._lib is not None:
                break
        if self._lib is None:
            log.warning("MLowCodec: shared library not found (looked for %s)", lib_names)
            return

        # --- decoder/encoder function bindings (guarded) ---
        def _bind(name, argtypes=None, restype=None):
            if hasattr(self._lib, name):
                try:
                    func = getattr(self._lib, name)
                    if argtypes is not None:
                        func.argtypes = argtypes
                    if restype is not None:
                        func.restype = restype
                    return True
                except Exception as e:
                    log.warning("MLowCodec: failed to bind %s: %s", name, e)
                    return False
            else:
                log.warning("MLowCodec: symbol not found: %s", name)
                return False

        # Decoder
        _bind('mlow_decoder_create', argtypes=[], restype=ctypes.c_uint64)
        _bind('mlow_decoder_destroy', argtypes=[ctypes.c_uint64])
        _bind('mlow_decoder_reset', argtypes=[ctypes.c_uint64])
        _bind('mlow_set_redundancy', argtypes=[ctypes.c_uint64, ctypes.c_int])
        _bind('mlow_decode', argtypes=[ctypes.c_uint64, ctypes.c_char_p, ctypes.c_int,
                                       ctypes.POINTER(ctypes.c_float), ctypes.c_int], restype=ctypes.c_int)

        # Encoder
        _bind('mlow_encoder_create', argtypes=[], restype=ctypes.c_uint64)
        _bind('mlow_encoder_destroy', argtypes=[ctypes.c_uint64])
        _bind('mlow_encoder_reset', argtypes=[ctypes.c_uint64])
        _bind('mlow_encode', argtypes=[ctypes.c_uint64, ctypes.POINTER(ctypes.c_float), ctypes.c_int,
                                       ctypes.c_char_p, ctypes.c_int], restype=ctypes.c_int)

        try:
            # Create handles
            self._dec_handle = self._lib.mlow_decoder_create()
            self._enc_handle = self._lib.mlow_encoder_create()
            self._available = self._dec_handle != 0 and self._enc_handle != 0
            log.info("MLowCodec: create handles dec=%s enc=%s available=%s",
                     str(self._dec_handle), str(self._enc_handle), self._available)
            if self._available:
                log.info("MLowCodec: initialized (dec=%d enc=%d)",
                         self._dec_handle, self._enc_handle)
            else:
                # Helpful hint for diagnostics: show available symbols that mention 'mlow'
                try:
                    sym_list = [attr for attr in dir(self._lib) if 'mlow' in attr]
                except Exception:
                    sym_list = []
                log.warning("MLowCodec: initialization FAILED — handles invalid (dec=%s enc=%s). symbols=%s",
                            str(self._dec_handle), str(self._enc_handle), sym_list)
        except Exception as e:
            self._dec_handle = 0
            self._enc_handle = 0
            self._available = False
            log.exception("MLowCodec: exception during initialization: %s", e)

    def encode(self, pcm: list[float]) -> bytes:
        if not self._available:
            raise RuntimeError("MLowCodec not available")
        n = len(pcm)
        # Use array('f') for fast bulk conversion — avoids per-element Python float boxing
        pcm_arr = array('f', pcm)
        pcm_ptr = (ctypes.c_float * n).from_buffer(pcm_arr)
        out_buf = ctypes.create_string_buffer(512)
        r = self._lib.mlow_encode(self._enc_handle, pcm_ptr, n, out_buf, 512)
        if r <= 0:
            log.warning("MLowCodec: encode failed r=%d", r)
            return b""
        return bytes(out_buf[:r])

    def decode(self, frame: bytes) -> list[float]:
        if not self._available:
            raise RuntimeError("MLowCodec not available")
        pcm_arr = array('f', [0.0]) * self.FRAME_SIZE
        pcm_ptr = (ctypes.c_float * self.FRAME_SIZE).from_buffer(pcm_arr)
        n = self._lib.mlow_decode(
            self._dec_handle, frame, len(frame), pcm_ptr, self.FRAME_SIZE,
        )
        if n <= 0:
            return [0.0] * self.FRAME_SIZE
        # Convert only valid samples; array supports fast slicing
        if n >= self.FRAME_SIZE:
            return pcm_arr.tolist()
        result = pcm_arr[:n].tolist()
        result.extend([0.0] * (self.FRAME_SIZE - n))
        return result

    def frame_size(self) -> int:
        return self.FRAME_SIZE

    def sample_rate(self) -> int:
        return self.SAMPLE_RATE

    def reset_decoder(self):
        """Reset decoder cross-frame state (call at stream discontinuity)."""
        if self._lib and self._dec_handle:
            self._lib.mlow_decoder_reset(self._dec_handle)

    def reset_encoder(self):
        """Reset encoder cross-frame state."""
        if self._lib and self._enc_handle:
            self._lib.mlow_encoder_reset(self._enc_handle)

    def set_redundancy(self, n: int):
        """Set negotiated RED redundancy level (0 = bare frames, 1+ = SplitRED).

        When the peer sends 0x86 SplitRED containers, redundancy MUST be >= 1
        so the Go decoder applies Stage 1 (RED depack) before TOC routing.
        Otherwise 0x86 container bytes are misread as TOC → garbage audio.
        """
        if self._lib and self._dec_handle:
            self._lib.mlow_set_redundancy(self._dec_handle, n)

    def close(self):
        if self._lib:
            if self._dec_handle:
                self._lib.mlow_decoder_destroy(self._dec_handle)
            if self._enc_handle:
                self._lib.mlow_encoder_destroy(self._enc_handle)
        self._available = False

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


class NullCodec(Codec):
    """
    Fallback codec for testing / signaling-only mode.

    When opus.dll is not available, this produces a valid Opus silence
    (DTX) frame that real WhatsApp clients can decode, keeping the call
    alive.  Without a valid Opus bitstream the peer would see garbage
    after SRTP decrypt and drop the call after ~20 s.

    The silence frame (0xF8 0xFF 0xFE) is a 3-byte Opus SILK‑only
    20 ms narrowband frame that every Opus decoder recognises.
    """

    # Valid Opus DTX (comfort-noise) frame — recognised by WACRG DTX classifier:
    #   2 bytes, first byte 0x08 → (0x08 & 0xf8) == 0x08  ✓
    #   Triggers 20-byte DTX header with extension word 0x30010000.
    OPUS_SILENCE: bytes = bytes([0x08, 0x00])

    def __init__(self, sample_rate: int = WHATSAPP_SAMPLE_RATE, frame_size: int = WHATSAPP_FRAME_SIZE):
        self._sample_rate = sample_rate
        self._frame_size = frame_size

    def encode(self, pcm: list[float]) -> bytes:
        """Return a valid Opus silence frame (ignores PCM input)."""
        return self.OPUS_SILENCE

    def decode(self, frame: bytes) -> list[float]:
        """Always decode to silence (all zeros)."""
        return [0.0] * self._frame_size

    def frame_size(self) -> int:
        return self._frame_size

    def sample_rate(self) -> int:
        return self._sample_rate

    def close(self):
        pass
