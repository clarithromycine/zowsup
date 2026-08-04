/*
 * range_coder.c — Opus/CELT range entropy decoder + encoder.
 *
 * Bit-exact with the reference.  The decoder reads range-coded symbols from
 * the front of the buffer and raw bits from the back; the encoder writes them
 * the same way and Done() merges the two streams.
 */

#include "range_coder.h"
#include <string.h>

/* ── Utility ────────────────────────────────────────────────────────────────── */

/* ilog: floor(log2(x))+1 for x>0, 0 for x==0.  Matches bits.Len32. */
int32_t mlow_ilog(uint32_t x) {
    if (x == 0) return 0;
    return (int32_t)(32 - __builtin_clz(x));
}

static uint32_t ec_mini(uint32_t a, uint32_t b) {
    return a < b ? a : b;
}

/* ── Decoder ────────────────────────────────────────────────────────────────── */

static uint32_t dec_read_byte(RangeDecoder *d) {
    if (d->offs < d->storage) {
        return d->buf[d->offs++];
    }
    /* readByte returns 0 at end-of-buffer without setting error.
     * Setting Err here would break the decode loop prematurely. */
    return 0;
}

static uint32_t dec_read_byte_from_end(RangeDecoder *d) {
    if (d->endOffs < d->storage) {
        d->endOffs++;
        return d->buf[d->storage - d->endOffs];
    }
    /* Same as above: returns 0 at end-of-buffer */
    return 0;
}

static void dec_normalize(RangeDecoder *d) {
    while (d->rng <= EC_CODE_BOT) {
        d->nbitsTotal += EC_SYM_BITS;
        d->rng <<= EC_SYM_BITS;
        int32_t sym0 = d->rem;
        d->rem = (int32_t)dec_read_byte(d);
        uint32_t sym = (uint32_t)((sym0 << EC_SYM_BITS | d->rem) >> (EC_SYM_BITS - EC_CODE_EXTRA));
        d->val = ((d->val << EC_SYM_BITS) + (EC_SYM_MAX & ~sym)) & (EC_CODE_TOP - 1);
    }
}

void range_dec_init(RangeDecoder *d, const uint8_t *buf, int len) {
    memset(d, 0, sizeof(*d));
    d->buf = buf;
    d->storage = (uint32_t)len;
    d->nbitsTotal = EC_CODE_BITS + 1 - ((EC_CODE_BITS - EC_CODE_EXTRA) / EC_SYM_BITS) * EC_SYM_BITS;
    d->rng = 1u << EC_CODE_EXTRA;
    d->rem = (int32_t)dec_read_byte(d);
    d->val = d->rng - 1 - ((uint32_t)d->rem >> (EC_SYM_BITS - EC_CODE_EXTRA));
    dec_normalize(d);
}

uint32_t range_dec_decode(RangeDecoder *d, uint32_t ft) {
    if (ft == 0) { d->Err = 1; d->ext = 1; return 0; }
    d->ext = d->rng / ft;
    if (d->ext == 0) { d->Err = 1; d->ext = 1; return 0; }
    uint32_t s = d->val / d->ext;
    return ft - ec_mini(s + 1, ft);
}

static uint32_t dec_decode_bin(RangeDecoder *d, uint32_t bitsN) {
    d->ext = d->rng >> bitsN;
    if (d->ext == 0) { d->Err = 1; d->ext = 1; return 0; }
    uint32_t s = d->val / d->ext;
    uint32_t ft = 1u << bitsN;
    return ft - ec_mini(s + 1, ft);
}

uint32_t range_dec_decode_raw_symbol(RangeDecoder *d, uint32_t nbits) {
    uint32_t sym = dec_decode_bin(d, nbits);
    range_dec_update(d, sym, sym + 1, 1u << nbits);
    return sym;
}

void range_dec_update(RangeDecoder *d, uint32_t fl, uint32_t fh, uint32_t ft) {
    uint32_t s = d->ext * (ft - fh);
    d->val -= s;
    if (fl > 0) {
        d->rng = d->ext * (fh - fl);
    } else {
        d->rng -= s;
    }
    dec_normalize(d);
}

int32_t range_dec_bit_logp(RangeDecoder *d, uint32_t logp) {
    uint32_t r = d->rng;
    uint32_t dv = d->val;
    uint32_t s = r >> logp;
    int32_t ret = (dv < s) ? 1 : 0;
    if (ret == 0) {
        d->val = dv - s;
        d->rng = r - s;
    } else {
        d->rng = s;
    }
    dec_normalize(d);
    return ret;
}

int32_t range_dec_decode_icdf(RangeDecoder *d, const uint8_t *icdf, int icdf_len, uint32_t ftb) {
    if (icdf_len == 0) { d->Err = 1; return 0; }
    uint32_t s0 = d->rng;
    uint32_t dv = d->val;
    uint32_t r = s0 >> ftb;
    int32_t ret = -1;
    uint32_t t, s = s0;
    for (;;) {
        t = s;
        ret++;
        s = r * (uint32_t)icdf[ret];
        if (dv >= s || ret >= icdf_len - 1) break;
    }
    d->val = dv - s;
    d->rng = t - s;
    dec_normalize(d);
    return ret;
}

int32_t range_dec_decode_cdf(RangeDecoder *d, const uint16_t *cdf, int n) {
    if (n < 2) { d->Err = 1; return 0; }
    uint32_t base = (uint32_t)cdf[0];
    if ((uint32_t)cdf[n - 1] <= base) { d->Err = 1; return 0; }
    uint32_t ft = (uint32_t)cdf[n - 1] - base;
    uint32_t fs = range_dec_decode(d, ft);
    uint32_t target = base + fs;
    int k = 0;
    while (k < n - 1) {
        if ((uint32_t)cdf[k + 1] > target) break;
        k++;
    }
    range_dec_update(d, (uint32_t)cdf[k] - base, (uint32_t)cdf[k + 1] - base, ft);
    return (int32_t)k;
}

uint32_t range_dec_bits_n(RangeDecoder *d, uint32_t n) {
    uint32_t window = d->endWindow;
    int32_t available = d->nendBits;
    if ((uint32_t)available < n) {
        for (;;) {
            window |= dec_read_byte_from_end(d) << (uint32_t)available;
            available += EC_SYM_BITS;
            if ((uint32_t)available > EC_WINDOW_SIZE - EC_SYM_BITS) break;
        }
    }
    uint32_t ret = window & ((1u << n) - 1);
    window >>= n;
    available -= (int32_t)n;
    d->endWindow = window;
    d->nendBits = available;
    d->nbitsTotal += (int32_t)n;
    return ret;
}

uint32_t range_dec_decode_uint(RangeDecoder *d, uint32_t ft0) {
    uint32_t ft = ft0 - 1;
    int32_t ftb = mlow_ilog(ft);
    if (ftb > EC_UINT_BITS) {
        ftb -= EC_UINT_BITS;
        uint32_t t = (ft >> (uint32_t)ftb) + 1;
        uint32_t s = range_dec_decode(d, t);
        range_dec_update(d, s, s + 1, t);
        uint32_t v = (s << (uint32_t)ftb) | range_dec_bits_n(d, (uint32_t)ftb);
        if (v <= ft) return v;
        d->Err = 1;
        return ft;
    }
    ft++;
    uint32_t s = range_dec_decode(d, ft);
    range_dec_update(d, s, s + 1, ft);
    return s;
}

int32_t range_dec_decode64_fine_sym(RangeDecoder *d) {
    d->ext = d->rng >> 6;
    if (d->ext == 0) { d->Err = 1; d->ext = 1; return 0; }
    uint32_t s = d->val / d->ext;
    int64_t sym = 63 - (int64_t)s;
    if (sym < 0) sym = 0;
    else if (sym > 64) sym = 64;
    range_dec_update(d, (uint32_t)sym, (uint32_t)sym + 1, 64);
    return (int32_t)sym;
}

int32_t range_dec_tell(RangeDecoder *d) {
    return d->nbitsTotal - mlow_ilog(d->rng);
}

/* ── Encoder ────────────────────────────────────────────────────────────────── */

static void enc_write_byte(RangeEncoder *e, uint32_t b) {
    if (e->offs + e->endOffs < e->storage) {
        e->buf[e->offs++] = (uint8_t)b;
    } else {
        e->err = -1;
    }
}

static void enc_write_byte_at_end(RangeEncoder *e, uint32_t b) {
    if (e->offs + e->endOffs < e->storage) {
        e->endOffs++;
        e->buf[e->storage - e->endOffs] = (uint8_t)b;
    } else {
        e->err = -1;
    }
}

static void enc_carry_out(RangeEncoder *e, int32_t c) {
    if ((uint32_t)c != EC_SYM_MAX) {
        int32_t carry = c >> EC_SYM_BITS;
        if (e->rem >= 0) {
            enc_write_byte(e, (uint32_t)(e->rem + carry));
        }
        if (e->ext > 0) {
            uint32_t sym = (EC_SYM_MAX + (uint32_t)carry) & EC_SYM_MAX;
            while (e->ext > 0) {
                enc_write_byte(e, sym);
                e->ext--;
            }
        }
        e->rem = c & EC_SYM_MAX;
    } else {
        e->ext++;
    }
}

static void enc_normalize(RangeEncoder *e) {
    while (e->rng <= EC_CODE_BOT) {
        enc_carry_out(e, (int32_t)(e->val >> EC_CODE_SHIFT));
        e->val = (e->val << EC_SYM_BITS) & (EC_CODE_TOP - 1);
        e->rng <<= EC_SYM_BITS;
        e->nbitsTotal += EC_SYM_BITS;
    }
}

void range_enc_init(RangeEncoder *e, uint8_t *buf, int size) {
    memset(e, 0, sizeof(*e));
    e->buf = buf;
    e->storage = (uint32_t)size;
    e->nbitsTotal = EC_CODE_BITS + 1;
    e->rng = EC_CODE_TOP;
    e->rem = -1;
}

void range_enc_encode(RangeEncoder *e, uint32_t fl, uint32_t fh, uint32_t ft) {
    if (ft == 0) { e->err = -1; return; }
    uint32_t r = e->rng / ft;
    if (fl > 0) {
        e->val += e->rng - r * (ft - fl);
        e->rng = r * (fh - fl);
    } else {
        e->rng -= r * (ft - fh);
    }
    enc_normalize(e);
}

void range_enc_bit_logp(RangeEncoder *e, int32_t val, uint32_t logp) {
    uint32_t r = e->rng;
    uint32_t l = e->val;
    uint32_t s = r >> logp;
    uint32_t r2 = r - s;
    if (val != 0) {
        e->val = l + r2;
        e->rng = s;
    } else {
        e->rng = r2;
    }
    enc_normalize(e);
}

void range_enc_encode_icdf(RangeEncoder *e, int32_t s, const uint8_t *icdf, uint32_t ftb) {
    uint32_t r = e->rng >> ftb;
    if (s > 0) {
        e->val += e->rng - r * (uint32_t)icdf[s - 1];
        e->rng = r * (uint32_t)(icdf[s - 1] - icdf[s]);
    } else {
        e->rng -= r * (uint32_t)icdf[s];
    }
    enc_normalize(e);
}

void range_enc_encode_cdf(RangeEncoder *e, int32_t s, const uint16_t *cdf, int n) {
    if (n < 2 || s < 0 || s + 1 >= n) { e->err = -1; return; }
    uint32_t base = (uint32_t)cdf[0];
    if ((uint32_t)cdf[n - 1] <= base) { e->err = -1; return; }
    uint32_t ft = (uint32_t)cdf[n - 1] - base;
    range_enc_encode(e, (uint32_t)cdf[s] - base, (uint32_t)cdf[s + 1] - base, ft);
}

void range_enc_bits_n(RangeEncoder *e, uint32_t fl, uint32_t n) {
    uint32_t window = e->endWindow;
    int32_t used = e->nendBits;
    if (used + (int32_t)n > EC_WINDOW_SIZE) {
        while (used >= EC_SYM_BITS) {
            enc_write_byte_at_end(e, window & EC_SYM_MAX);
            window >>= EC_SYM_BITS;
            used -= EC_SYM_BITS;
        }
    }
    window |= fl << (uint32_t)used;
    used += (int32_t)n;
    e->endWindow = window;
    e->nendBits = used;
    e->nbitsTotal += (int32_t)n;
}

void range_enc_encode_uint(RangeEncoder *e, uint32_t fl, uint32_t ft0) {
    uint32_t ft = ft0 - 1;
    int32_t ftb = mlow_ilog(ft);
    if (ftb > EC_UINT_BITS) {
        uint32_t shift = (uint32_t)ftb - EC_UINT_BITS;
        uint32_t t = (ft >> shift) + 1;
        range_enc_encode(e, fl >> shift, (fl >> shift) + 1, t);
        range_enc_bits_n(e, fl & ((1u << shift) - 1), shift);
    } else {
        range_enc_encode(e, fl, fl + 1, ft + 1);
    }
}

void range_enc_encode_raw_symbol(RangeEncoder *e, uint32_t sym, uint32_t nbits) {
    range_enc_encode(e, sym, sym + 1, 1u << nbits);
}

void range_enc_encode64_fine_sym(RangeEncoder *e, int32_t sym) {
    range_enc_encode(e, (uint32_t)sym, (uint32_t)sym + 1, 64);
}

void range_enc_done(RangeEncoder *e) {
    int32_t l = (int32_t)EC_CODE_BITS - mlow_ilog(e->rng);
    uint32_t msk = (EC_CODE_TOP - 1) >> (uint32_t)l;
    uint32_t end = (e->val + msk) & ~msk;
    if ((end | msk) >= e->val + e->rng) {
        l++;
        msk >>= 1;
        end = (e->val + msk) & ~msk;
    }
    while (l > 0) {
        enc_carry_out(e, (int32_t)(end >> EC_CODE_SHIFT));
        end = (end << EC_SYM_BITS) & (EC_CODE_TOP - 1);
        l -= EC_SYM_BITS;
    }
    if (e->rem >= 0 || e->ext > 0) {
        enc_carry_out(e, 0);
    }
    uint32_t window = e->endWindow;
    int32_t used = e->nendBits;
    while (used >= EC_SYM_BITS) {
        enc_write_byte_at_end(e, window & EC_SYM_MAX);
        window >>= EC_SYM_BITS;
        used -= EC_SYM_BITS;
    }
    if (e->err == 0) {
        for (uint32_t i = e->offs; i < e->storage - e->endOffs; i++) {
            e->buf[i] = 0;
        }
        if (used > 0) {
            if (e->endOffs >= e->storage - e->offs) {
                e->err = -1;
            } else {
                e->buf[e->storage - e->endOffs - 1] |= (uint8_t)window;
            }
        }
    }
}

int range_enc_consumed_len(RangeEncoder *e) {
    return (int)(e->offs + e->endOffs);
}