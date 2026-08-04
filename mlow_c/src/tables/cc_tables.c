/*
 * cc_tables.c �?Energy/gains/pulse decode tables (Group A/B/C/E).
 *
 * Includes SILK fixed-point primitives and the split/runlen CDF builders.
 */

#include "cc_tables.h"
#include "../seed.h"
#include "../range_coder.h"
#include <stdlib.h>
#include <string.h>
#include <math.h>

#include "cc_seed_data.h"

/* ── Global singleton ──────────────────────────────────────────────────────── */
cc_tables_t g_cc_tables;

/* ── Constants ──────────────────────────────────────────────────────────────── */
static const int16_t cb_acbgains_hr_q14[32] = {
    16039, 91, 0, 0, 4310, 4930, -1431, 2862, 2893, 0, 8009, 4075, 2754, 4223, 8367, 354,
    4640, 1254, -176, 2734, -1222, 5017, -476, 1506, 11351, 567, 1243, 0, 10601, 22, 14088, 108,
};
static const int16_t cb_acbgains_lr_q14[32] = {
    2812, 2484, 0, 0, -362, 2465, -337, 703, 3033, 1474, 13536, 220, -2630, 9226, 6032, 3499,
    -220, 441, 7661, 4243, 11521, 0, 1430, 779, 4495, 2724, 15535, 343, -779, 1559, 480, 481,
};

/* celpAcbgainsDcmfLR / HR */
static const uint8_t celp_acbgains_dcmf_lr[272] = {
    103, 70, 48, 3, 122, 135, 47, 192, 2, 255, 99, 96, 186, 194, 4, 28,
    161, 90, 76, 3, 181, 60, 37, 219, 2, 132, 81, 146, 255, 43, 3, 36,
    114, 222, 55, 6, 203, 34, 42, 154, 6, 255, 33, 209, 225, 78, 6, 45,
    198, 161, 110, 8, 239, 26, 35, 162, 4, 117, 42, 214, 255, 33, 6, 72,
    55, 255, 124, 55, 124, 55, 55, 55, 55, 78, 55, 215, 111, 55, 55, 167,
    154, 136, 77, 4, 220, 33, 38, 166, 2, 144, 50, 196, 255, 43, 4, 41,
    56, 21, 19, 3, 48, 255, 38, 220, 2, 225, 107, 31, 122, 227, 2, 11,
    63, 38, 23, 4, 77, 85, 58, 190, 4, 255, 53, 53, 145, 138, 4, 14,
    95, 47, 33, 2, 110, 146, 53, 255, 2, 219, 79, 73, 198, 122, 2, 15,
    84, 255, 84, 84, 147, 84, 84, 84, 84, 120, 84, 120, 84, 84, 84, 84,
    73, 58, 25, 1, 95, 99, 52, 175, 1, 255, 48, 69, 151, 184, 1, 15,
    105, 32, 43, 2, 84, 225, 34, 255, 2, 156, 129, 49, 189, 124, 3, 19,
    152, 230, 89, 6, 253, 28, 40, 153, 2, 195, 31, 255, 249, 58, 5, 61,
    138, 84, 54, 3, 173, 96, 45, 247, 2, 176, 83, 128, 255, 69, 2, 26,
    22, 17, 8, 1, 23, 106, 26, 88, 1, 182, 37, 18, 50, 255, 1, 6,
    218, 174, 228, 65, 186, 65, 65, 92, 65, 65, 65, 255, 174, 65, 65, 174,
    117, 255, 101, 16, 180, 20, 33, 94, 10, 131, 20, 222, 143, 38, 15, 105,
};

static const uint8_t celp_acbgains_dcmf_hr[272] = {
    254, 105, 212, 26, 110, 255, 202, 93, 152, 121, 110, 43, 150, 20, 81, 176,
    255, 28, 100, 5, 26, 184, 61, 29, 36, 26, 28, 9, 61, 4, 27, 116,
    121, 255, 161, 39, 195, 215, 191, 75, 186, 178, 119, 82, 68, 41, 43, 56,
    188, 65, 243, 15, 74, 255, 205, 79, 123, 84, 95, 26, 139, 13, 67, 154,
    81, 219, 173, 70, 219, 165, 234, 102, 231, 255, 191, 119, 87, 60, 62, 59,
    106, 255, 182, 49, 242, 196, 233, 95, 247, 228, 152, 96, 81, 45, 54, 61,
    236, 55, 178, 10, 56, 255, 131, 54, 85, 58, 59, 18, 93, 9, 43, 133,
    123, 95, 224, 24, 113, 202, 255, 105, 186, 134, 135, 38, 141, 18, 82, 111,
    126, 97, 204, 34, 126, 186, 255, 141, 210, 147, 149, 46, 165, 22, 113, 122,
    96, 156, 185, 42, 188, 178, 255, 116, 248, 199, 157, 66, 109, 29, 69, 75,
    102, 207, 194, 57, 224, 193, 255, 107, 253, 242, 180, 95, 97, 44, 60, 64,
    105, 119, 202, 39, 140, 189, 255, 110, 207, 173, 165, 54, 119, 24, 75, 85,
    74, 255, 142, 59, 214, 150, 182, 76, 194, 215, 138, 122, 61, 56, 41, 45,
    200, 53, 255, 17, 66, 238, 222, 109, 129, 78, 101, 21, 227, 11, 110, 243,
    74, 255, 128, 50, 187, 149, 154, 63, 165, 184, 115, 101, 52, 47, 37, 34,
    159, 66, 232, 26, 86, 196, 255, 146, 171, 113, 134, 31, 245, 16, 145, 190,
    255, 29, 182, 7, 33, 235, 115, 55, 59, 37, 47, 11, 139, 6, 60, 234,
};

/* ── SILK fixed-point primitives ───────────────────────────────────────────── */

static int32_t cc_smulbb(int32_t a, int32_t b) {
    return (int32_t)((int16_t)a) * (int32_t)((int16_t)b);
}

static int32_t cc_smlawb(int32_t a, int32_t b, int32_t c) {
    /* return int32(int64(a) + ((int64(b) * int64(int16(c))) >> 16)) */
    return (int32_t)((int64_t)a + (((int64_t)b * (int64_t)(int16_t)c) >> 16));
}

static void cc_clz_frac(int32_t in, int32_t *lz, int32_t *fracQ7) {
    uint32_t u = (uint32_t)in;
    *lz = (int32_t)__builtin_clz(u);
    /* bits.RotateLeft32(u, -int((24-lz)&31)) — rotate RIGHT by (24-lz)&31 */
    int rot = (24 - *lz) & 31;
    if (rot == 0) {
        *fracQ7 = (int32_t)(u & 0x7f);
    } else {
        *fracQ7 = (int32_t)(((u >> rot) | (u << (32 - rot))) & 0x7f);
    }
}

static int32_t cc_lin2log(int32_t inLin) {
    int32_t lz, fracQ7;
    cc_clz_frac(inLin, &lz, &fracQ7);
    /* return ccSmlawb(fracQ7, fracQ7*(128-fracQ7), 179) + ((31 - lz) << 7) */
    return cc_smlawb(fracQ7, fracQ7 * (128 - fracQ7), 179) + ((31 - lz) << 7);
}

static int32_t cc_log2lin(int32_t inLogQ7) {
    if (inLogQ7 < 0) return 0;
    if (inLogQ7 >= 3967) return 0x7fffffff;
    int32_t out = 1 << (inLogQ7 >> 7);
    int32_t fracQ7 = inLogQ7 & 0x7f;
    int32_t inner = cc_smlawb(fracQ7, fracQ7 * (128 - fracQ7), -174); /* plain multiply */
    if (inLogQ7 < 2048) {
        out += (out * inner) >> 7;
    } else {
        out += (out >> 7) * inner;
    }
    return out;
}

static int32_t cc_sigm_q15(int32_t inQ5) {
    static const int32_t slope[6] = {237, 153, 73, 30, 12, 7};
    static const int32_t pos[6] = {16384, 23955, 28861, 31213, 32178, 32548};
    static const int32_t neg[6] = {16384, 8812, 3906, 1554, 589, 219};
    if (inQ5 < 0) {
        int32_t v = -inQ5;
        if (v >= 6 * 32) return 0;
        int32_t ind = v >> 5;
        return neg[ind] - cc_smulbb(slope[ind], v & 0x1f);
    }
    if (inQ5 >= 6 * 32) return 32767;
    int32_t ind = inQ5 >> 5;
    return pos[ind] + cc_smulbb(slope[ind], inQ5 & 0x1f);
}

/* ── pdfToCmf ──────────────────────────────────────────────────────────────── */
static void pdf_to_cmf(const int32_t *pdf, int pdf_len, uint16_t *cmf) {
    int64_t n = (int64_t)pdf_len;
    int64_t maxval = 32767;
    int64_t sump = 0;
    for (int i = 0; i < pdf_len; i++) sump += (int64_t)pdf[i];
    if (sump == 0) {
        /* Degenerate case: all-zero PDF �?uniform CDF */
        for (int i = 0; i <= pdf_len; i++) {
            cmf[i] = (uint16_t)((maxval * (int64_t)i) / n);
        }
        return;
    }
    cmf[0] = 0;
    for (int i = 0; i < pdf_len; i++) {
        int64_t p = (int64_t)pdf[i] * (maxval - n) / sump + 1;
        cmf[i + 1] = (uint16_t)((int32_t)cmf[i] + (int32_t)p);
    }
}

/* ── Stirling / probSplit ──────────────────────────────────────────────────── */
#define CC_LOG2_EXP1_Q15 47274
#define CC_LOG2_2PI_Q14  43442
#define CC_ONE_Q31        ((int64_t)1 << 31)

static int32_t cc_stirling(int32_t n) {
    if (n == 0) return 0;
    int32_t ret = ((n << 1) + 1) * (cc_lin2log(n) << 7);
    ret -= (int32_t)CC_LOG2_EXP1_Q15 * n;
    ret += CC_LOG2_2PI_Q14;
    return ret + CC_LOG2_EXP1_Q15 / (12 * n);
}

static int32_t cc_prob_split_fast(int32_t k, int32_t n) {
    int32_t tmp = cc_stirling(n) - cc_stirling(k) - cc_stirling(n - k) - n * (1 << 15);
    if (tmp == 0) return 1 << 30;
    int32_t ret = cc_log2lin((-tmp) >> 8);
    if (ret == 0) return 1;
    return (1 << 30) / ret;
}

/* ── createSplitCmfs ────────────────────────────────────────────────────────── */
static void create_split_cmfs(cc_tables_t *t) {
    int offset = 0;
    t->split_cmfs_offsets[0] = 0;
    for (int32_t numPulses = 1; numPulses <= CC_SPLIT_NUM_TABLES; numPulses++) {
        int32_t minSplit = numPulses - CC_MAX_PULSES_PER_SF * 2;
        if (minSplit < 0) minSplit = 0;
        int32_t maxSplit = numPulses - minSplit;
        int32_t p[200]; /* max split range */
        int plen = maxSplit - minSplit + 1;
        for (int32_t k = minSplit; k <= maxSplit; k++) {
            p[k - minSplit] = cc_prob_split_fast(k, numPulses);
        }
        pdf_to_cmf(p, plen, &t->split_cmfs_data[offset]);
        offset += plen + 1;
        t->split_cmfs_offsets[numPulses] = offset;
    }
    t->num_split_cmfs = CC_SPLIT_NUM_TABLES;
}

/* ── createRunlenTable ─────────────────────────────────────────────────────── */
static void create_runlen_table(cc_tables_t *t, int32_t maxSamples, int oct) {
    int32_t ms = maxSamples;
    int32_t p[200] = {0}; /* maxSamples max = 20*8 = 160 */
    for (int32_t nump = 1; nump <= CC_MAX_PULSES_PER_SF; nump++) {
        int64_t plongerQ31 = CC_ONE_Q31;
        for (int32_t nums = 1; nums <= ms; nums++) {
            int64_t tmp = CC_ONE_Q31 - (CC_ONE_Q31 / (int64_t)(ms - nums + 1));
            int64_t p1Q31 = tmp;
            for (int32_t r = 0; r < nump - 1; r++) {
                p1Q31 = (p1Q31 * tmp) >> 31;
            }
            p1Q31 = CC_ONE_Q31 - p1Q31;
            if (p1Q31 > 2147376274) p1Q31 = 2147376274;

            int32_t logOutQ7;
            if (nump > ms) {
                logOutQ7 = cc_lin2log((nump << 10) / ms) - 10 * 128;
            } else {
                logOutQ7 = -(cc_lin2log((ms << 10) / nump) - 10 * 128);
            }
            const int32_t sigmBiasQ5 = 146;
            const int32_t scaleMaxQ15 = 36000;
            const int32_t scaleMinQ15 = 26000;
            int32_t scaleFacQ15 = scaleMaxQ15 - (((scaleMaxQ15 - scaleMinQ15) * cc_sigm_q15((logOutQ7 >> 2) + sigmBiasQ5)) >> 15);
            p1Q31 = CC_ONE_Q31 - (int64_t)cc_log2lin(((scaleFacQ15 * (cc_lin2log((int32_t)(CC_ONE_Q31 - p1Q31)) - 31 * 128)) >> 15) + 31 * 128);
            if (p1Q31 > 2147376274) p1Q31 = 2147376274;
            p[nums - 1] = (int32_t)((plongerQ31 * p1Q31) >> 31);
            plongerQ31 = (plongerQ31 * (CC_ONE_Q31 - p1Q31)) >> 31;
        }
        pdf_to_cmf(p, ms, &t->runlen_data[t->runlen_offsets[oct - 1] + (nump - 1) * (ms + 1)]);
    }
    t->runlen_max_samples[oct - 1] = ms;
}

/* ── ccDcmf / ccDcmfChunks ─────────────────────────────────────────────────── */
static void cc_dcmf(const uint8_t *dcmf, int dcmf_len, uint16_t *cmf) {
    celp_dcmf_to_cmf(dcmf, dcmf_len, cmf);
}

/* ── ccSeed ────────────────────────────────────────────────────────────────── */
typedef struct {
    const uint8_t *nrgresGain4Dcmf;
    int nrgresGain4DcmfLen;
    const uint8_t *nrgresShape4Dcmf;
    int nrgresShape4DcmfLen;
    const uint8_t *fcbgOffsetDcmf;
    int fcbgOffsetDcmfLen;
    const uint8_t *acbgainsHrDcmf;
    int acbgainsHrDcmfLen;
    const uint8_t *fcbgainsVDcmf;
    int fcbgainsVDcmfLen;
    const uint8_t *fcbgainsVDeltaDcmf;
    int fcbgainsVDeltaDcmfLen;
    int32_t acbgainsCbHrQ14[200];
    int acbgainsCbHrQ14Len;
    uint32_t gainReconBase;
    const uint8_t *gainRecon;
    int gainReconLen;
    const uint8_t *nPulsesDcmfBgn;
    int nPulsesDcmfBgnLen;
    const uint8_t *nPulsesDcmfUv;
    int nPulsesDcmfUvLen;
    const uint8_t *nPulsesDcmfV;
    int nPulsesDcmfVLen;
} cc_seed_t;

/* Helper: find a proto field by number. */
static const proto_field_t *find_pf_cc(const proto_field_t *fields, int nf, int num) {
    for (int i = 0; i < nf; i++)
        if (fields[i].field == num) return &fields[i];
    return NULL;
}

static void load_cc_seed(cc_seed_t *s) {
    uint8_t raw[65536];
    int raw_len = inflate_zlib(cc_seed_data, cc_seed_data_len, raw, sizeof(raw));
    if (raw_len < 0) abort();

    proto_field_t fields[32];
    int nf = parse_proto(raw, raw_len, fields, 32);

    const proto_field_t *f;

    /* Helper: copy field bytes to heap, f.bytes...)) */
    #define HEAP_COPY(dst, dstLen, fld) do { \
        if (fld) { \
            (dst) = (uint8_t *)malloc((fld)->len); \
            memcpy((dst), (fld)->bytes, (fld)->len); \
            (dstLen) = (fld)->len; \
        } else { (dst) = NULL; (dstLen) = 0; } \
    } while(0)

    f = find_pf_cc(fields, nf, 1);  HEAP_COPY(s->nrgresGain4Dcmf, s->nrgresGain4DcmfLen, f);
    f = find_pf_cc(fields, nf, 2);  HEAP_COPY(s->nrgresShape4Dcmf, s->nrgresShape4DcmfLen, f);
    f = find_pf_cc(fields, nf, 3);  HEAP_COPY(s->fcbgOffsetDcmf, s->fcbgOffsetDcmfLen, f);
    f = find_pf_cc(fields, nf, 4);  HEAP_COPY(s->acbgainsHrDcmf, s->acbgainsHrDcmfLen, f);
    f = find_pf_cc(fields, nf, 5);  HEAP_COPY(s->fcbgainsVDcmf, s->fcbgainsVDcmfLen, f);
    f = find_pf_cc(fields, nf, 6);  HEAP_COPY(s->fcbgainsVDeltaDcmf, s->fcbgainsVDeltaDcmfLen, f);

    f = find_pf_cc(fields, nf, 7);
    s->acbgainsCbHrQ14Len = f ? decode_zigzag_varints(f->bytes, f->len, s->acbgainsCbHrQ14, 200) : 0;

    f = find_pf_cc(fields, nf, 8);  s->gainReconBase = f ? (uint32_t)f->varint : 0;
    f = find_pf_cc(fields, nf, 9);  HEAP_COPY(s->gainRecon, s->gainReconLen, f);
    f = find_pf_cc(fields, nf, 10); HEAP_COPY(s->nPulsesDcmfBgn, s->nPulsesDcmfBgnLen, f);
    f = find_pf_cc(fields, nf, 11); HEAP_COPY(s->nPulsesDcmfUv, s->nPulsesDcmfUvLen, f);
    f = find_pf_cc(fields, nf, 12); HEAP_COPY(s->nPulsesDcmfV, s->nPulsesDcmfVLen, f);

    #undef HEAP_COPY
}

/* ── Build ─────────────────────────────────────────────────────────────────── */
void cc_tables_build(void) {
    cc_seed_t s;
    memset(&s, 0, sizeof(s));
    load_cc_seed(&s);

    /* nrgres gain/shape */
    g_cc_tables.nrgres_gain4 = (uint16_t *)malloc((s.nrgresGain4DcmfLen + 1) * sizeof(uint16_t));
    cc_dcmf(s.nrgresGain4Dcmf, s.nrgresGain4DcmfLen, g_cc_tables.nrgres_gain4);
    g_cc_tables.nrgres_gain4_len = s.nrgresGain4DcmfLen + 1;

    g_cc_tables.nrgres_shape4 = (uint16_t *)malloc((s.nrgresShape4DcmfLen + 1) * sizeof(uint16_t));
    cc_dcmf(s.nrgresShape4Dcmf, s.nrgresShape4DcmfLen, g_cc_tables.nrgres_shape4);
    g_cc_tables.nrgres_shape4_len = s.nrgresShape4DcmfLen + 1;

    /* fcbg offset: chunks of CC_FCBG_OFFSET_STEPS */
    int num_offset_rows = s.fcbgOffsetDcmfLen / CC_FCBG_OFFSET_STEPS;
    for (int i = 0; i + CC_FCBG_OFFSET_STEPS <= s.fcbgOffsetDcmfLen; i += CC_FCBG_OFFSET_STEPS) {
        int row = i / CC_FCBG_OFFSET_STEPS;
        cc_dcmf(s.fcbgOffsetDcmf + i, CC_FCBG_OFFSET_STEPS, g_cc_tables.fcbg_offset[row]);
    }
    g_cc_tables.num_fcbg_offset_rows = num_offset_rows;

    /* acbgains HR: chunks of CC_ACBG_N */
    int hr_rows = s.acbgainsHrDcmfLen / CC_ACBG_N;
    for (int i = 0; i + CC_ACBG_N <= s.acbgainsHrDcmfLen; i += CC_ACBG_N) {
        int row = i / CC_ACBG_N;
        cc_dcmf(s.acbgainsHrDcmf + i, CC_ACBG_N, &g_cc_tables.acbgains_hr[row * (CC_ACBG_N + 1)]);
    }
    /* acbgains LR: from const DCMF */
    for (int i = 0; i + CC_ACBG_N <= (int)sizeof(celp_acbgains_dcmf_lr); i += CC_ACBG_N) {
        int row = i / CC_ACBG_N;
        cc_dcmf(celp_acbgains_dcmf_lr + i, CC_ACBG_N, &g_cc_tables.acbgains_lr[row * (CC_ACBG_N + 1)]);
    }

    /* acbgains codebook weights */
    for (int i = 0; i < s.acbgainsCbHrQ14Len && i < (int)(sizeof(g_cc_tables.acbgains_cb_hr_q14)/sizeof(int16_t)); i++) {
        g_cc_tables.acbgains_cb_hr_q14[i] = (int16_t)s.acbgainsCbHrQ14[i];
    }
    memcpy(g_cc_tables.acbgains_cb_lr_q14, cb_acbgains_lr_q14, sizeof(cb_acbgains_lr_q14));

    /* fcbgains V / VDelta */
    cc_dcmf(s.fcbgainsVDcmf, s.fcbgainsVDcmfLen, g_cc_tables.fcbgains_v);
    cc_dcmf(s.fcbgainsVDeltaDcmf, s.fcbgainsVDeltaDcmfLen, g_cc_tables.fcbgains_v_delta);

    /* gain recon */
    g_cc_tables.gain_recon_base = s.gainReconBase;
    g_cc_tables.gain_recon_len = s.gainReconLen / 2;
    g_cc_tables.gain_recon = (int16_t *)malloc(g_cc_tables.gain_recon_len * sizeof(int16_t));
    for (int i = 0; i + 1 < s.gainReconLen; i += 2) {
        g_cc_tables.gain_recon[i / 2] = (int16_t)((uint16_t)s.gainRecon[i] | ((uint16_t)s.gainRecon[i + 1] << 8));
    }

    /* nPulse CDFs */
    g_cc_tables.n_pulse_cmfs[0] = (uint16_t *)malloc((s.nPulsesDcmfBgnLen + 1) * sizeof(uint16_t));
    cc_dcmf(s.nPulsesDcmfBgn, s.nPulsesDcmfBgnLen, g_cc_tables.n_pulse_cmfs[0]);
    g_cc_tables.n_pulse_cmfs_len[0] = s.nPulsesDcmfBgnLen + 1;

    g_cc_tables.n_pulse_cmfs[1] = (uint16_t *)malloc((s.nPulsesDcmfUvLen + 1) * sizeof(uint16_t));
    cc_dcmf(s.nPulsesDcmfUv, s.nPulsesDcmfUvLen, g_cc_tables.n_pulse_cmfs[1]);
    g_cc_tables.n_pulse_cmfs_len[1] = s.nPulsesDcmfUvLen + 1;

    g_cc_tables.n_pulse_cmfs[2] = (uint16_t *)malloc((s.nPulsesDcmfVLen + 1) * sizeof(uint16_t));
    cc_dcmf(s.nPulsesDcmfV, s.nPulsesDcmfVLen, g_cc_tables.n_pulse_cmfs[2]);
    g_cc_tables.n_pulse_cmfs_len[2] = s.nPulsesDcmfVLen + 1;

    /* split CDFs */
    create_split_cmfs(&g_cc_tables);

    /* runlen CDFs */
    int rl_offset = 0;
    for (int oct = 1; oct <= CC_NUM_RUNLEN_CMFS; oct++) {
        g_cc_tables.runlen_offsets[oct - 1] = rl_offset;
        int32_t ms = oct * CC_RUNLENGTH_STEP;
        rl_offset += CC_MAX_PULSES_PER_SF * (ms + 1);
    }
    g_cc_tables.runlen_offsets[CC_NUM_RUNLEN_CMFS] = rl_offset;
    g_cc_tables.num_runlen = CC_NUM_RUNLEN_CMFS;

    for (int oct = 1; oct <= CC_NUM_RUNLEN_CMFS; oct++) {
        create_runlen_table(&g_cc_tables, oct * CC_RUNLENGTH_STEP, oct);
    }
}