#ifndef MLOW_INTERNAL_H
#define MLOW_INTERNAL_H

/*
 * mlow_internal.h — Internal interface shared between codec modules.
 * NOT part of the public ABI (mlow.h is the public header).
 */

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ── Constants ─────────────────────────────────────────────────────────────── */
#define MLOW_SAMPLE_RATE     16000
#define MLOW_FRAME_SAMPLES   960    /* 60 ms @ 16 kHz */
#define MLOW_SUBFR_LEN       80     /* 5 ms @ 16 kHz */
#define MLOW_INTF_LEN        320    /* 20 ms internal frame */
#define MLOW_SUBFR_COUNT     4
#define MLOW_LPC_ORDER       16
#define MLOW_LTP_HIST        728
#define MLOW_ENCODE_BUF_BYTES 512

/* ── Forward declarations ───────────────────────────────────────────────────── */
typedef struct MlowDecoder MlowDecoder;
typedef struct MlowEncoder MlowEncoder;

/* ── Decoder lifecycle ─────────────────────────────────────────────────────── */
MlowDecoder *mlow_decoder_new(void);
void         mlow_decoder_free(MlowDecoder *d);
void         mlow_decoder_reset_impl(MlowDecoder *d);
void         mlow_decoder_set_redundancy(MlowDecoder *d, int n);
int          mlow_decoder_decode(MlowDecoder *d,
                                 const uint8_t *payload, int length,
                                 float *pcm_out, int max_samples);

/* ── Encoder lifecycle ─────────────────────────────────────────────────────── */
MlowEncoder *mlow_encoder_new(void);
void         mlow_encoder_free(MlowEncoder *e);
void         mlow_encoder_reset_impl(MlowEncoder *e);
int          mlow_encoder_encode(MlowEncoder *e,
                                 const float *pcm_in, int pcm_len,
                                 uint8_t *enc_out, int max_enc);

/* ── Global table init (called once via pthread_once) ──────────────────────── */
void mlow_tables_init(void);

#ifdef __cplusplus
}
#endif

#endif /* MLOW_INTERNAL_H */