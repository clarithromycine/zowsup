/*
 * seed.c — Shared seed-loading utilities (protobuf parse, zlib inflate, dcmf→cmf).
 */

#include "seed.h"
#include "range_coder.h"
#include <math.h>
#include <string.h>
#include <stdlib.h>

#include "miniz.h"

/* ── Protobuf parsing ────────────────────────────────────────────────────────── */

/* readVarint: read a base-128 varint from b[*ip].  Returns 1 on success, 0 on EOF. */
static int read_varint(const uint8_t *b, int blen, int *ip, uint64_t *out) {
    uint64_t v = 0;
    uint32_t shift = 0;
    while (*ip < blen) {
        uint8_t c = b[(*ip)++];
        v |= (uint64_t)(c & 0x7f) << shift;
        if ((c & 0x80) == 0) {
            *out = v;
            return 1;
        }
        shift += 7;
    }
    return 0;
}

int parse_proto(const uint8_t *b, int blen, proto_field_t *fields, int max_fields) {
    int count = 0;
    int i = 0;
    while (i < blen && count < max_fields) {
        uint64_t key;
        if (!read_varint(b, blen, &i, &key)) break;
        int field = (int)(key >> 3);
        int wire = (int)(key & 7);
        if (wire == 0) {
            uint64_t v;
            if (!read_varint(b, blen, &i, &v)) break;
            fields[count].field = field;
            fields[count].wire = 0;
            fields[count].varint = v;
            fields[count].bytes = NULL;
            fields[count].len = 0;
            count++;
        } else if (wire == 2) {
            uint64_t ln;
            if (!read_varint(b, blen, &i, &ln)) break;
            if (i + (int)ln > blen) break;
            fields[count].field = field;
            fields[count].wire = 2;
            fields[count].varint = 0;
            fields[count].bytes = b + i;
            fields[count].len = (int)ln;
            i += (int)ln;
            count++;
        } else {
            break;
        }
    }
    return count;
}

/* Helper: find a field by number, returns NULL if not found. */
static const proto_field_t *find_field(const proto_field_t *fields, int n, int field_num) {
    for (int i = 0; i < n; i++) {
        if (fields[i].field == field_num) return &fields[i];
    }
    return NULL;
}

/* ── Varint decoders ────────────────────────────────────────────────────────── */

int decode_varints_u32(const uint8_t *b, int blen, uint32_t *out, int max_out) {
    int count = 0;
    int i = 0;
    while (i < blen && count < max_out) {
        uint64_t v = 0;
        uint32_t shift = 0;
        while (i < blen) {
            uint8_t c = b[i++];
            v |= (uint64_t)(c & 0x7f) << shift;
            if ((c & 0x80) == 0) break;
            shift += 7;
        }
        out[count++] = (uint32_t)v;
    }
    return count;
}

int decode_zigzag_varints(const uint8_t *b, int blen, int32_t *out, int max_out) {
    int count = 0;
    int i = 0;
    while (i < blen && count < max_out) {
        uint64_t v = 0;
        uint32_t shift = 0;
        while (i < blen) {
            uint8_t c = b[i++];
            v |= (uint64_t)(c & 0x7f) << shift;
            if ((c & 0x80) == 0) break;
            shift += 7;
        }
        int64_t sv = (int64_t)(v >> 1) ^ -(int64_t)(v & 1);
        out[count++] = (int32_t)sv;
    }
    return count;
}

int decode_floats(const uint8_t *b, int blen, float *out, int max_out) {
    int n = blen / 4;
    if (n > max_out) n = max_out;
    for (int i = 0; i < n; i++) {
        uint32_t bits = (uint32_t)b[i*4] | ((uint32_t)b[i*4+1] << 8) |
                        ((uint32_t)b[i*4+2] << 16) | ((uint32_t)b[i*4+3] << 24);
        memcpy(&out[i], &bits, sizeof(float));
    }
    return n;
}

/* ── zlib decompression ────────────────────────────────────────────────────── */

int inflate_zlib(const uint8_t *src, int src_len, uint8_t *out_buf, int out_cap) {
    mz_ulong out_len = (mz_ulong)out_cap;
    int ret = uncompress(out_buf, &out_len, src, (mz_ulong)src_len);
    if (ret != MZ_OK) return -1;
    return (int)out_len;
}

/* ── DCMF → CMF expansions ──────────────────────────────────────────────────── */

void celp_dcmf_to_cmf(const uint8_t *dcmf, int dcmf_len, uint16_t *cmf) {
    int32_t sum = 0;
    for (int n = 0; n < dcmf_len; n++) {
        int32_t tmp = (int32_t)dcmf[n] + 1;
        tmp *= tmp;
        if (tmp > 65535) tmp = 65535;
        cmf[n + 1] = (uint16_t)tmp;
        sum += tmp;
    }
    cmf[0] = 0;
    for (int n = 1; n < dcmf_len + 1; n++) {
        cmf[n] = cmf[n - 1] + (uint16_t)((int32_t)cmf[n] * (32767 - dcmf_len) / sum + 1);
    }
}

void pitch_dcmf_to_cmf(const uint8_t *dcmf, int dcmf_len, uint32_t *cmf) {
    int n = dcmf_len;
    int64_t sum = 0;
    for (int i = 0; i < n; i++) {
        int32_t tmp = (int32_t)dcmf[i] + 1;
        tmp *= tmp;
        if (tmp > 65535) tmp = 65535;
        cmf[i + 1] = (uint32_t)tmp;
        sum += (int64_t)tmp;
    }
    cmf[0] = 0;
    for (int i = 1; i <= n; i++) {
        int64_t prev = (int64_t)cmf[i - 1];
        int64_t add = (int64_t)cmf[i] * (32767 - (int64_t)n) / sum + 1;
        cmf[i] = (uint32_t)(prev + add);
    }
}

void lsf_dcmf_to_cmf(const uint8_t *dcmf, int dcmf_len, uint16_t *cmf) {
    int n = dcmf_len;
    int64_t sum = 0;
    for (int i = 0; i < n; i++) {
        int32_t tmp = (int32_t)dcmf[i] + 1;
        tmp *= tmp;
        if (tmp > 65535) tmp = 65535;
        cmf[i + 1] = (uint16_t)tmp;
        sum += (int64_t)tmp;
    }
    cmf[0] = 0;
    for (int i = 1; i < n + 1; i++) {
        int64_t prev = (int64_t)cmf[i - 1];
        int64_t add = (int64_t)cmf[i] * (int64_t)(32767 - n) / sum + 1;
        cmf[i] = (uint16_t)(prev + add);
    }
}

/* ── f32 helpers ────────────────────────────────────────────────────────────── */

float mlow_sqrtf32(float x)  { return (float)sqrt((double)x); }
float mlow_log2f32(float x) { return (float)log2((double)x); }
float mlow_cosf32(float x)  { return (float)cos((double)x); }
float mlow_sinf32(float x)  { return (float)sin((double)x); }
float mlow_roundf32(float x){ return (float)round((double)x); }

float mlow_maxf32(float a, float b) { return a > b ? a : b; }
float mlow_absf32(float x) { return x < 0 ? -x : x; }