/*
 * vad.c �?Voice Activity Detection (SILK-based).
 *
 * Processes one 60ms packet = 3 × 20ms internal frames.
 * Uses SILK analysis filterbank (2-stage QMF) to split 0-8kHz into 4 bands,
 * then computes SNR per band, sums the weighted SNRs through a sigmoid to
 * produce a speech activity probability (SA, 0-255).
 */
#include "encode.h"
#include <stdlib.h>
#include <string.h>

/* ── Constants ─────────────────────────────────────────────────────────────── */
#define VAD_NBANDS                 4
#define VAD_INTERNAL_SUBFRAMES_LOG2 2
#define VAD_INTERNAL_SUBFRAMES      (1 << VAD_INTERNAL_SUBFRAMES_LOG2) /* 4 */
#define VAD_NOISE_LEVEL_SMOOTH_COEF_Q16 1024
#define VAD_NOISE_LEVELS_BIAS       50
#define VAD_NEGATIVE_OFFSET_Q5      128
#define VAD_SNR_FACTOR_Q16          45000
#define AFB120                      7788   /* 3894 << 1 */
#define AFB121                     -29322
#define SPEECH_ACTIVITY_DTX_THRES_Q8 12

#define SILK_INT32_MAX  ((int32_t)0x7FFFFFFF)
#define SILK_INT16_MAX  ((int32_t)32767)
#define SILK_INT16_MIN  ((int32_t)(-0x8000))
#define SILK_UINT8_MAX  ((int32_t)0xFF)

static const int32_t tilt_weights[VAD_NBANDS] = {30000, 6000, -12000, -12000};

/* ── VAD internal state ────────────────────────────────────────────────────── */
typedef struct {
    int32_t ana_state[2];
    int32_t ana_state1[2];
    int32_t ana_state2[2];
    int32_t xnrg_subfr[VAD_NBANDS];
    int32_t nl[VAD_NBANDS];
    int32_t inv_nl[VAD_NBANDS];
    int32_t noise_level_bias[VAD_NBANDS];
    int32_t counter;
    int32_t hp_state;
    int32_t noise_lvl_update_speed;
    int32_t non_binariness;
    int32_t highpass_sharpness;
    int32_t remaining_dtx_hangover;
    int32_t hangover_ms;
} vad_state_t;

/* ── SILK fixed-point primitives ────────────────────────────────────────────── */

static inline int32_t sat16(int32_t a) {
    if (a < SILK_INT16_MIN) return SILK_INT16_MIN;
    if (a > SILK_INT16_MAX) return SILK_INT16_MAX;
    return a;
}

static inline int32_t smulwb(int32_t a, int32_t b) {
    return (int32_t)(((int64_t)a * (int64_t)(int16_t)b) >> 16);
}

static inline int32_t smlawb(int32_t a, int32_t b, int32_t c) {
    /* return int32(int64(a) + ((int64(b) * int64(int16(c))) >> 16)) */
    return (int32_t)((int64_t)a + (((int64_t)b * (int64_t)(int16_t)c) >> 16));
}

static inline int32_t smulww(int32_t a, int32_t b) {
    return (int32_t)(((int64_t)a * (int64_t)b) >> 16);
}

static inline int32_t smulbb(int32_t a, int32_t b) {
    return (int32_t)(int16_t)a * (int32_t)(int16_t)b;
}

static inline int32_t smlabb(int32_t a, int32_t b, int32_t c) {
    return a + (int32_t)(int16_t)b * (int32_t)(int16_t)c;
}

static inline int32_t add_pos_sat32(int32_t a, int32_t b) {
    uint32_t ua = (uint32_t)a;
    uint32_t ub = (uint32_t)b;
    if (((ua + ub) & 0x80000000u) != 0) return SILK_INT32_MAX;
    return (int32_t)(ua + ub);
}

static inline int32_t div32(int32_t a, int32_t b) {
    return a / b;
}

static int32_t clz32(int32_t x) {
    uint32_t ux = (uint32_t)x;
    if (ux == 0) return 32;
#ifdef _MSC_VER
    unsigned long idx;
    _BitScanReverse(&idx, ux);
    return (int32_t)(31 - idx);
#else
    return (int32_t)__builtin_clz(ux);
#endif
}

static int32_t ror32(int32_t a32, int32_t rot) {
    uint32_t u = (uint32_t)a32;
    int32_t r = rot & 31;
    return (int32_t)((u >> r) | (u << (32 - r)));
}

static void clz_frac(int32_t inp, int32_t *lz, int32_t *frac_q7) {
    *lz = clz32(inp);
    *frac_q7 = ror32(inp, 24 - (*lz)) & 0x7f;
}

static int32_t lin2log(int32_t in_lin) {
    int32_t lz, frac_q7;
    clz_frac(in_lin, &lz, &frac_q7);
    return smlawb(frac_q7, frac_q7 * (128 - frac_q7), 179) + ((31 - lz) << 7);
}

static int32_t sqrt_approx(int32_t x) {
    if (x <= 0) return 0;
    int32_t lz, frac_q7;
    clz_frac(x, &lz, &frac_q7);
    int32_t y;
    if (lz & 1) y = 32768;
    else        y = 46214;
    y >>= (lz >> 1);
    return smlawb(y, y, smulbb(213, frac_q7));
}

static int32_t sigm_q15(int32_t in_q5) {
    static const int32_t slope[6] = {237, 153, 73, 30, 12, 7};
    static const int32_t pos[6]   = {16384, 23955, 28861, 31213, 32178, 32548};
    static const int32_t neg[6]   = {16384, 8812, 3906, 1554, 589, 219};
    if (in_q5 < 0) {
        in_q5 = -in_q5;
        if (in_q5 >= 6 * 32) return 0;
        int32_t ind = in_q5 >> 5;
        return neg[ind] - smulbb(slope[ind], in_q5 & 0x1F);
    }
    if (in_q5 >= 6 * 32) return 32767;
    int32_t ind = in_q5 >> 5;
    return pos[ind] + smulbb(slope[ind], in_q5 & 0x1F);
}

static int32_t rshift_round(int32_t a, int32_t shift) {
    if (shift == 1) return (a >> 1) + (a & 1);
    return ((a >> (shift - 1)) + 1) >> 1;
}

/* ── VAD methods ────────────────────────────────────────────────────────────── */

static void filt_hp(vad_state_t *s, int32_t *x, int32_t b_q16, int32_t a_neg_q16, int length) {
    for (int i = 0; i < length; i++) {
        int32_t inval = smulwb(b_q16, x[i]);
        int32_t outval = sat16(s->hp_state - inval);
        s->hp_state = smlawb(inval, a_neg_q16, outval);
        x[i] = outval;
    }
}

/* ana_filt_bank1: non-in-place QMF split, writes to separate lo/hi arrays */
static void ana_filt_bank1(const int32_t *inp, int32_t s[2], int32_t *out_l, int32_t *out_h, int n) {
    int n2 = n >> 1;
    for (int k = 0; k < n2; k++) {
        int32_t in32 = inp[2*k] << 10;
        int32_t y = in32 - s[0];
        int32_t x = smlawb(y, y, AFB121);
        int32_t out1 = s[0] + x;
        s[0] = in32 + x;

        in32 = inp[2*k+1] << 10;
        y = in32 - s[1];
        x = smulwb(y, AFB120);
        int32_t out2 = s[1] + x;
        s[1] = in32 + x;

        out_l[k] = sat16(rshift_round(out2 + out1, 11));
        out_h[k] = sat16(rshift_round(out2 - out1, 11));
    }
}

/* ana_filt_bank1_inplace: in-place QMF split on x[]; lo in x[0..n2-1], hi in x[hi_off..] */
static void ana_filt_bank1_inplace(int32_t *x, int hi_off, int32_t s[2], int n) {
    int n2 = n >> 1;
    for (int k = 0; k < n2; k++) {
        int32_t in32 = x[2*k] << 10;
        int32_t y = in32 - s[0];
        int32_t xx = smlawb(y, y, AFB121);
        int32_t out1 = s[0] + xx;
        s[0] = in32 + xx;

        in32 = x[2*k+1] << 10;
        y = in32 - s[1];
        xx = smulwb(y, AFB120);
        int32_t out2 = s[1] + xx;
        s[1] = in32 + xx;

        x[hi_off + k] = sat16(rshift_round(out2 - out1, 11));
        x[k] = sat16(rshift_round(out2 + out1, 11));
    }
}

static void get_noise_levels(vad_state_t *s, int32_t pX[VAD_NBANDS]) {
    int32_t min_coef = 0;
    if (s->counter < 1000) {
        min_coef = div32(SILK_INT16_MAX, (s->counter >> 4) + 1);
        s->counter++;
    }
    for (int b = 0; b < VAD_NBANDS; b++) {
        int32_t nl = s->nl[b];
        int32_t nrg = add_pos_sat32(pX[b], s->noise_level_bias[b]);
        int32_t inv_nrg = div32(SILK_INT32_MAX, nrg);
        int32_t coef;
        if (nrg > (nl << 3))
            coef = VAD_NOISE_LEVEL_SMOOTH_COEF_Q16 >> 3;
        else if (nrg < nl)
            coef = VAD_NOISE_LEVEL_SMOOTH_COEF_Q16;
        else
            coef = smulwb(smulww(inv_nrg, nl), VAD_NOISE_LEVEL_SMOOTH_COEF_Q16 << 1);

        coef = (coef * (100 + s->noise_lvl_update_speed)) / 100;
        if (coef < min_coef) coef = min_coef;

        s->inv_nl[b] = smlawb(s->inv_nl[b], inv_nrg - s->inv_nl[b], coef);
        int32_t v = div32(SILK_INT32_MAX, s->inv_nl[b]);
        if (v > 0x00FFFFFF) v = 0x00FFFFFF;
        s->nl[b] = v;
    }
}

static int32_t get_sa_q8(vad_state_t *s, const int32_t *p_in, int framelen) {
    int dec_fl1 = framelen >> 1;
    int dec_fl2 = framelen >> 2;
    int dec_fl3 = framelen >> 3;

    int x_offset[VAD_NBANDS];
    x_offset[0] = 0;
    x_offset[1] = dec_fl3 + dec_fl2;
    x_offset[2] = x_offset[1] + dec_fl3;
    x_offset[3] = x_offset[2] + dec_fl2;
    int x_total = x_offset[3] + dec_fl1;

    /* Stack-allocate: max ~320 for 16kHz */
    int32_t *x = (int32_t *)malloc((size_t)x_total * sizeof(int32_t));
    if (!x) return 0;

    /* Stage 1: QMF split into lo/hi halves */
    ana_filt_bank1(p_in, s->ana_state, x, x + x_offset[3], framelen);
    /* Stage 2: split lo half again */
    ana_filt_bank1_inplace(x, x_offset[2], s->ana_state1, dec_fl1);
    /* Stage 3: split result lo quarter */
    ana_filt_bank1_inplace(x, x_offset[1], s->ana_state2, dec_fl2);

    /* HP filter on lowest band (-3dB @ 66Hz) */
    int32_t a_neg_q16 = 53084;
    a_neg_q16 = (a_neg_q16 * (100 - s->highpass_sharpness)) / 100;
    int32_t b_q16 = (65536 + a_neg_q16) / 2;
    filt_hp(s, x, b_q16, a_neg_q16, dec_fl3);

    /* Energy per band */
    int32_t xnrg[VAD_NBANDS];
    for (int b = 0; b < VAD_NBANDS; b++) {
        int shift = VAD_NBANDS - b;
        if (shift > VAD_NBANDS - 1) shift = VAD_NBANDS - 1;
        int dec = framelen >> shift;
        int dec_subfr_len = dec >> VAD_INTERNAL_SUBFRAMES_LOG2;
        int dec_subfr_offset = 0;
        xnrg[b] = s->xnrg_subfr[b];
        int32_t sum_squared = 0;
        for (int sub = 0; sub < VAD_INTERNAL_SUBFRAMES; sub++) {
            sum_squared = 0;
            for (int i = 0; i < dec_subfr_len; i++) {
                int32_t x_tmp = x[x_offset[b] + i + dec_subfr_offset] >> 3;
                sum_squared = smlabb(sum_squared, x_tmp, x_tmp);
            }
            if (sub < VAD_INTERNAL_SUBFRAMES - 1)
                xnrg[b] = add_pos_sat32(xnrg[b], sum_squared);
            else
                xnrg[b] = add_pos_sat32(xnrg[b], sum_squared >> 1);
            dec_subfr_offset += dec_subfr_len;
        }
        s->xnrg_subfr[b] = sum_squared;
    }

    get_noise_levels(s, xnrg);

    /* Signal-plus-noise to noise ratio */
    int32_t sum_squared_snr = 0;
    int32_t input_tilt = 0;
    for (int b = 0; b < VAD_NBANDS; b++) {
        int32_t speech_nrg = xnrg[b] - s->nl[b];
        if (speech_nrg > 0) {
            int32_t ratio_q8;
            if ((xnrg[b] & (int32_t)0xFF800000u) == 0)
                ratio_q8 = div32(xnrg[b] << 8, s->nl[b] + 1);
            else
                ratio_q8 = div32(xnrg[b], (s->nl[b] >> 8) + 1);
            int32_t snr_q7 = lin2log(ratio_q8) - 8 * 128;
            sum_squared_snr = smlabb(sum_squared_snr, snr_q7, snr_q7);
            if (speech_nrg < (1 << 20))
                snr_q7 = smulwb(sqrt_approx(speech_nrg) << 6, snr_q7);
            input_tilt = smlawb(input_tilt, tilt_weights[b], snr_q7);
        }
    }
    sum_squared_snr = div32(sum_squared_snr, VAD_NBANDS);
    int32_t p_snr_db_q7 = (int32_t)(int16_t)(3 * sqrt_approx(sum_squared_snr));

    int32_t vad_snr_factor_q16 = (VAD_SNR_FACTOR_Q16 * (150 - s->non_binariness)) / 150;
    int32_t sa_q15 = sigm_q15(smulwb(vad_snr_factor_q16, p_snr_db_q7) - VAD_NEGATIVE_OFFSET_Q5);

    (void)input_tilt;
    int32_t r = sa_q15 >> 7;
    if (r > SILK_UINT8_MAX) r = SILK_UINT8_MAX;

    free(x);
    return r;
}

/* ── Public API ─────────────────────────────────────────────────────────────── */

void *vad_state_new(void) {
    vad_state_t *s = (vad_state_t *)calloc(1, sizeof(vad_state_t));
    if (!s) return NULL;
    s->counter = 15;
    s->remaining_dtx_hangover = 60;
    s->hangover_ms = 60;
    for (int b = 0; b < VAD_NBANDS; b++) {
        int32_t bias = VAD_NOISE_LEVELS_BIAS / (int32_t)(b + 1);
        if (bias < 1) bias = 1;
        s->noise_level_bias[b] = bias;
        s->nl[b] = 100 * bias;
        s->inv_nl[b] = SILK_INT32_MAX / s->nl[b];
    }
    return s;
}

void vad_state_free(void *vs) {
    free(vs);
}

void vad_process_packet(void *vs, const int16_t *pcm, int subfr_len,
                        float *vad_results, bool *coded_as_active) {
    vad_state_t *s = (vad_state_t *)vs;
    const int frames_per_packet = 3;
    const int packet_ms = 60;

    *coded_as_active = false;
    for (int i = 0; i < frames_per_packet; i++) {
        /* Copy 20ms PCM �?int32 for SILK analysis */
        int32_t *frame = (int32_t *)malloc((size_t)subfr_len * sizeof(int32_t));
        if (!frame) {
            vad_results[i] = 0.0f;
            continue;
        }
        for (int j = 0; j < subfr_len; j++)
            frame[j] = (int32_t)pcm[i * subfr_len + j];

        int32_t sa_q8 = get_sa_q8(s, frame, subfr_len);
        vad_results[i] = (float)sa_q8 / 256.0f;

        int32_t vad_type; /* 0=inactive, 1=active */
        if (sa_q8 > SPEECH_ACTIVITY_DTX_THRES_Q8)
            vad_type = 1; /* active */
        else
            vad_type = 0; /* inactive */

        if (vad_type == 1) {
            s->remaining_dtx_hangover = s->hangover_ms;
        } else if (s->remaining_dtx_hangover > 0) {
            s->remaining_dtx_hangover -= packet_ms / frames_per_packet;
        }
        if (vad_type != 0 || s->remaining_dtx_hangover > 0)
            *coded_as_active = true;

        free(frame);
    }
}