#ifndef MLOW_SEED_H
#define MLOW_SEED_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ── Protobuf parsing ──────────────────────────────────────────────────────── */

/* parseProtoBytes: parse length-delimited (wiretype 2) fields into field→bytes.
 * Returns the number of fields found; fields[] is filled with (field_num, ptr, len).
 * Max 32 fields.  Mirrors parseProtoBytes / parseProto.
 */
typedef struct {
    int field;
    int wire;
    uint64_t varint;
    const uint8_t *bytes;
    int len;
} proto_field_t;

int parse_proto(const uint8_t *b, int blen, proto_field_t *fields, int max_fields);

/* decodeVarintsU32: decode packed repeated uint32 varints. */
int decode_varints_u32(const uint8_t *b, int blen, uint32_t *out, int max_out);

/* decodeZigzagVarints: decode packed repeated sint32 (zigzag) varints. */
int decode_zigzag_varints(const uint8_t *b, int blen, int32_t *out, int max_out);

/* decodeFloats: decode packed repeated fixed32 LE floats. */
int decode_floats(const uint8_t *b, int blen, float *out, int max_out);

/* ── zlib decompression (via miniz) ────────────────────────────────────────── */

/* inflate_zlib: decompress zlib data into out_buf.  Returns decompressed length
 * or -1 on error.  out_cap is the capacity of out_buf.
 */
int inflate_zlib(const uint8_t *src, int src_len, uint8_t *out_buf, int out_cap);

/* ── DCMF �?CMF expansion ──────────────────────────────────────────────────── */

/* celp_dcmf_to_cmf: integer dcmf→cmf (truncating-int normalize).
 * cmf must have dcmf_len+1 entries.
 */
void celp_dcmf_to_cmf(const uint8_t *dcmf, int dcmf_len, uint16_t *cmf);

/* pitch_dcmf_to_cmf: integer expansion returning a uint32 CDF of length dcmf_len+1.
 * cmf must have dcmf_len+1 entries.
 */
void pitch_dcmf_to_cmf(const uint8_t *dcmf, int dcmf_len, uint32_t *cmf);

/* lsf_dcmf_to_cmf: integer expansion returning a uint16 CDF of length dcmf_len+1.
 */
void lsf_dcmf_to_cmf(const uint8_t *dcmf, int dcmf_len, uint16_t *cmf);

/* ── f32 helpers ───────────────────────────────────────────────────────────── */

float mlow_sqrtf32(float x);
float mlow_log2f32(float x);
float mlow_cosf32(float x);
float mlow_sinf32(float x);
float mlow_roundf32(float x);
float mlow_maxf32(float a, float b);
float mlow_absf32(float x);

#ifdef __cplusplus
}
#endif

#endif /* MLOW_SEED_H */