#ifndef MLOW_RANGE_CODER_H
#define MLOW_RANGE_CODER_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ── Constants ─────────────────────────────────────────────────────────────── */
#define EC_SYM_BITS    8
#define EC_CODE_BITS   32
#define EC_SYM_MAX     255
#define EC_CODE_TOP    (1u << (EC_CODE_BITS - 1))
#define EC_CODE_BOT    (EC_CODE_TOP >> EC_SYM_BITS)
#define EC_CODE_EXTRA  ((EC_CODE_BITS - 2) % EC_SYM_BITS + 1)
#define EC_WINDOW_SIZE 32
#define EC_UINT_BITS   8
#define EC_CODE_SHIFT  (EC_CODE_BITS - EC_SYM_BITS - 1)

/* ── RangeDecoder (Opus/CELT range entropy decoder) ────────────────────────── */
typedef struct {
    const uint8_t *buf;
    uint32_t storage;
    uint32_t endOffs;
    uint32_t endWindow;
    int32_t  nendBits;
    int32_t  nbitsTotal;
    uint32_t offs;
    uint32_t rng;
    uint32_t val;
    uint32_t ext;
    int32_t  rem;
    int32_t  Err;   /* sticky decode error */
} RangeDecoder;

void range_dec_init(RangeDecoder *d, const uint8_t *buf, int len);

uint32_t range_dec_decode(RangeDecoder *d, uint32_t ft);
int32_t  range_dec_decode_icdf(RangeDecoder *d, const uint8_t *icdf, int icdf_len, uint32_t ftb);
int32_t  range_dec_decode_cdf(RangeDecoder *d, const uint16_t *cdf, int n);
uint32_t range_dec_bits_n(RangeDecoder *d, uint32_t n);
uint32_t range_dec_decode_uint(RangeDecoder *d, uint32_t ft0);
uint32_t range_dec_decode_raw_symbol(RangeDecoder *d, uint32_t nbits);
int32_t  range_dec_bit_logp(RangeDecoder *d, uint32_t logp);
int32_t  range_dec_decode64_fine_sym(RangeDecoder *d);
void     range_dec_update(RangeDecoder *d, uint32_t fl, uint32_t fh, uint32_t ft);
int32_t  range_dec_tell(RangeDecoder *d);

/* ── RangeEncoder (Opus/CELT range entropy encoder) ────────────────────────── */
typedef struct {
    uint8_t *buf;
    uint32_t storage;
    uint32_t endOffs;
    uint32_t endWindow;
    int32_t  nendBits;
    int32_t  nbitsTotal;
    uint32_t offs;
    uint32_t rng;
    uint32_t val;
    uint32_t ext;
    int32_t  rem;
    int32_t  err;
} RangeEncoder;

void range_enc_init(RangeEncoder *e, uint8_t *buf, int size);
void range_enc_encode(RangeEncoder *e, uint32_t fl, uint32_t fh, uint32_t ft);
void range_enc_bit_logp(RangeEncoder *e, int32_t val, uint32_t logp);
void range_enc_encode_icdf(RangeEncoder *e, int32_t s, const uint8_t *icdf, uint32_t ftb);
void range_enc_encode_cdf(RangeEncoder *e, int32_t s, const uint16_t *cdf, int n);
void range_enc_bits_n(RangeEncoder *e, uint32_t fl, uint32_t n);
void range_enc_encode_uint(RangeEncoder *e, uint32_t fl, uint32_t ft0);
void range_enc_encode_raw_symbol(RangeEncoder *e, uint32_t sym, uint32_t nbits);
void range_enc_encode64_fine_sym(RangeEncoder *e, int32_t sym);
void range_enc_done(RangeEncoder *e);
int  range_enc_consumed_len(RangeEncoder *e);

/* ── Utility ──────────────────────────────────────────────────────────────── */
int32_t mlow_ilog(uint32_t x);

#ifdef __cplusplus
}
#endif

#endif /* MLOW_RANGE_CODER_H */