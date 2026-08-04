#ifndef MLOW_H
#define MLOW_H

/*
 * mlow.h — Public C ABI for the MLow (SMPL) audio codec.
 *
 * The Python loader (voip/media/codec.py) calls these functions via
 * ctypes with the signatures below — they MUST NOT change.
 *
 * Shared library output name:  mlow_decoder.{dll,dylib,so}
 */

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ── Visibility macros ─────────────────────────────────────────────────────── */
#if defined(_WIN32) || defined(__CYGWIN__)
#  ifdef MLOW_EXPORTS
#    define MLOW_API __declspec(dllexport)
#  else
#    define MLOW_API __declspec(dllimport)
#  endif
#else
#  define MLOW_API __attribute__((visibility("default")))
#endif

/* ── Decoder ───────────────────────────────────────────────────────────────── */

/* Create a decoder instance.  Returns an opaque non-zero handle, or 0 on error. */
MLOW_API uint64_t mlow_decoder_create(void);

/* Destroy a decoder instance.  Safe to call with handle = 0 (no-op). */
MLOW_API void mlow_decoder_destroy(uint64_t handle);

/* Reset cross-frame decoder state (call at stream discontinuity). */
MLOW_API void mlow_decoder_reset(uint64_t handle);

/* Set negotiated RED redundancy level (0 = bare frames, 1+ = SplitRED). */
MLOW_API void mlow_set_redundancy(uint64_t handle, int n);

/*
 * Decode one RTP MLow payload into PCM float32 samples.
 *
 *   handle    — decoder handle from mlow_decoder_create()
 *   data      — pointer to encoded payload bytes
 *   length    — number of bytes in data
 *   pcm_out   — output buffer for float32 PCM, range [-1, 1]
 *   max_samples — capacity of pcm_out in samples (typically 960 = 60 ms @ 16 kHz)
 *
 * Returns: number of samples written, or -1 on error.
 */
MLOW_API int mlow_decode(uint64_t handle,
                          const uint8_t *data,
                          int length,
                          float *pcm_out,
                          int max_samples);

/* ── Encoder ───────────────────────────────────────────────────────────────── */

/* Create an encoder instance.  Returns an opaque non-zero handle, or 0 on error. */
MLOW_API uint64_t mlow_encoder_create(void);

/* Destroy an encoder instance.  Safe to call with handle = 0 (no-op). */
MLOW_API void mlow_encoder_destroy(uint64_t handle);

/* Reset cross-frame encoder state. */
MLOW_API void mlow_encoder_reset(uint64_t handle);

/*
 * Encode PCM float32 samples into an MLow payload.
 *
 *   handle  — encoder handle from mlow_encoder_create()
 *   pcm_in  — input float32 PCM samples, range [-1, 1]
 *   pcm_len — number of input samples (typically 960 = 60 ms @ 16 kHz)
 *   enc_out — output buffer for encoded bytes
 *   max_enc — capacity of enc_out in bytes (512 is sufficient)
 *
 * Returns: number of bytes written to enc_out, or -1 on error.
 */
MLOW_API int mlow_encode(uint64_t handle,
                          const float *pcm_in,
                          int pcm_len,
                          uint8_t *enc_out,
                          int max_enc);

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* MLOW_H */