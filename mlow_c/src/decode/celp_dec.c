/*
 * celp_dec.c — CELP synthesis decoder.
 */

#include "decode.h"
#include "../seed.h"
#include <math.h>
#include <string.h>
#include <stdlib.h>

/* ── Constants ──────────────────────────────────────────────────────────────── */
#define CELP_LAG_SUBFR_LEN      40
#define CELP_LTP_INTERPOL_DELAY  8
#define CELP_MAX_PITCH_LAG      320
#define ACBG_M  2
#define ACBG_N  16

static const float pitch_sharp_coef = 0.9881f;
static const float dec_acb_high_boost[2] = {0.35f, 0.18f};

/* lsfInterpol4: [lsf_interpol_idx][sf] */
static const float lsf_interpol4[2][4] = {
    {0.55f, 0.88f, 1.0f, 1.0f},
    {0.3f, 0.65f, 0.95f, 1.0f}
};

/* celpInterpolKernel: 16-tap symmetric LTP interpolation kernel */
static const float celp_interpol_kernel[16] = {
    -6.3925986e-6f, 0.00011064114f, -0.0009153038f, 0.00484772f,
    -0.018698348f, 0.05759091f, -0.15997477f, 0.6170455f,
    0.61704546f, -0.15997475f, 0.057590906f, -0.018698348f,
    0.00484772f, -0.0009153038f, 0.000110641144f, -6.392598e-6f,
};

/* Per-subframe ACB-gain codebook (Q14) */
static const int16_t cb_acbgains_hr_q14[32] = {
    16039, 91, 0, 0, 4310, 4930, -1431, 2862, 2893, 0, 8009, 4075, 2754, 4223, 8367, 354,
    4640, 1254, -176, 2734, -1222, 5017, -476, 1506, 11351, 567, 1243, 0, 10601, 22, 14088, 108,
};
static const int16_t cb_acbgains_lr_q14[32] = {
    2812, 2484, 0, 0, -362, 2465, -337, 703, 3033, 1474, 13536, 220, -2630, 9226, 6032, 3499,
    -220, 441, 7661, 4243, 11521, 0, 1430, 779, 4495, 2724, 15535, 343, -779, 1559, 480, 481,
};

static float min_f32(float a, float b) { return a < b ? a : b; }

/* ── celpDot ───────────────────────────────────────────────────────────────── */
static float celp_dot(const float *a, const float *b, int l) {
    float r = 0.0f;
    for (int i = 0; i < l; i++) r += a[i] * b[i];
    return r;
}

/* ── lpcInterpol ───────────────────────────────────────────────────────────── */
static void lpc_interpol(const float *lsf, float *prev_lsf, const float *interpol,
                          float a_out[4][17], float lsfs_out[4][16]) {
    if (prev_lsf[SMPL_ORDER - 1] == 0.0f) memcpy(prev_lsf, lsf, SMPL_ORDER * sizeof(float));
    float ilsf[16];
    float prev_factor = -1.0f;
    for (int j = 0; j < SMPL_SUBFR_COUNT; j++) {
        if (interpol[j] == prev_factor) {
            memcpy(a_out[j], a_out[j - 1], 17 * sizeof(float));
        } else {
            if (interpol[j] == 1.0f) {
                memcpy(ilsf, lsf, SMPL_ORDER * sizeof(float));
            } else {
                for (int k = 0; k < SMPL_ORDER; k++)
                    ilsf[k] = prev_lsf[k] * (1.0f - interpol[j]) + lsf[k] * interpol[j];
            }
            smpl_nlsf2a(a_out[j], ilsf, SMPL_ORDER);
        }
        prev_factor = interpol[j];
        memcpy(lsfs_out[j], ilsf, SMPL_ORDER * sizeof(float));
    }
    memcpy(prev_lsf, ilsf, SMPL_ORDER * sizeof(float));
}

/* ── acbDequant ─────────────────────────────────────────────────────────────── */
static void acb_dequant(bool low_rate, int32_t acb_idx, float acb_g[2]) {
    const int16_t *cb = low_rate ? cb_acbgains_lr_q14 : cb_acbgains_hr_q14;
    if (acb_idx < 0) acb_idx = 0;
    if (acb_idx > 15) acb_idx = 15;
    const float sc = 1.0f / (float)(1 << 14);
    for (int m = 0; m < ACBG_M; m++) acb_g[m] = (float)cb[acb_idx * ACBG_M + m] * sc;
}

/* ── acbSynthesize ─────────────────────────────────────────────────────────── */
static void acb_synthesize(int fcb_subfr_len, const float *acb_basis, const float acb_g_in[2],
                            float high_boost, float *acb) {
    float acb_g[2] = {acb_g_in[0], acb_g_in[1]};
    if (high_boost != 0.0f) {
        float f0 = acb_g[0] + 2.0f * acb_g[1];
        float f1 = acb_g[0] - acb_g[1];
        float abs_f2_new = min_f32(mlow_absf32(f1) + high_boost, mlow_absf32(f0));
        f1 = f1 * (abs_f2_new / (mlow_absf32(f1) + 1e-12f));
        acb_g[0] = (f0 + 2.0f * f1) / 3.0f;
        acb_g[1] = (f0 - f1) / 3.0f;
    }
    for (int i = 0; i < fcb_subfr_len; i++) acb[i] = acb_g[0] * acb_basis[i];
    for (int i = 0; i < fcb_subfr_len; i++) acb[i] += acb_g[1] * acb_basis[fcb_subfr_len + i];
}

/* ── pitchSharp ────────────────────────────────────────────────────────────── */
static void pitch_sharp(float *x, int lag, int l) {
    for (int i = lag; i < l; i++) x[i] += x[i - lag] * pitch_sharp_coef;
}

/* ── synLTPBasis ───────────────────────────────────────────────────────────── */
static void syn_ltp_basis(const float *lags, int n_lags, float *state, int state_len, float *acb_basis) {
    int p = state_len - n_lags * CELP_LAG_SUBFR_LEN;
    for (int subfr = 0; subfr < n_lags; subfr++) {
        int i_lag = (int)floor((double)lags[subfr]);
        if (i_lag < 1) i_lag = 1;
        if (i_lag > CELP_MAX_PITCH_LAG) i_lag = CELP_MAX_PITCH_LAG;
        if ((float)i_lag == lags[subfr]) {
            int il = i_lag;
            for (int i = 0; i < CELP_LAG_SUBFR_LEN; i++) state[p + i] = state[p + i - il];
            for (int i = 0; i < CELP_LAG_SUBFR_LEN; i++) acb_basis[subfr * CELP_LAG_SUBFR_LEN + i] = state[p + i];
            for (int i = 0; i < CELP_LAG_SUBFR_LEN; i++)
                acb_basis[(n_lags + subfr) * CELP_LAG_SUBFR_LEN + i] = state[p + i - il - 1] + state[p + i - il + 1];
        } else {
            int il = i_lag;
            int base_first = p + (-1 - il - CELP_LTP_INTERPOL_DELAY);
            float first = celp_dot(&state[base_first], celp_interpol_kernel, 2 * CELP_LTP_INTERPOL_DELAY);
            int src_base = p + (-il - CELP_LTP_INTERPOL_DELAY);
            for (int nn = 0; nn < CELP_LAG_SUBFR_LEN; nn++) {
                float ret = 0.0f;
                for (int i = 0; i < 8; i++) {
                    float s0 = state[src_base + nn + i];
                    float s1 = state[src_base + nn + 15 - i];
                    ret += (s0 + s1) * celp_interpol_kernel[i];
                }
                state[p + nn] = ret;
            }
            int base_last = p + (CELP_LAG_SUBFR_LEN - il - CELP_LTP_INTERPOL_DELAY);
            float last = celp_dot(&state[base_last], celp_interpol_kernel, 2 * CELP_LTP_INTERPOL_DELAY);
            for (int i = 0; i < CELP_LAG_SUBFR_LEN; i++) acb_basis[subfr * CELP_LAG_SUBFR_LEN + i] = state[p + i];
            int b1 = (n_lags + subfr) * CELP_LAG_SUBFR_LEN;
            acb_basis[b1] = first + state[p + 1];
            for (int i = 0; i < CELP_LAG_SUBFR_LEN - 2; i++) acb_basis[b1 + 1 + i] = state[p + i] + state[p + i + 2];
            int i_last = CELP_LAG_SUBFR_LEN - 1;
            acb_basis[b1 + i_last] = state[p + i_last - 1] + last;
        }
        p += CELP_LAG_SUBFR_LEN;
    }
}

/* ── celpDecode ────────────────────────────────────────────────────────────── */
static void celp_decode(float *acb_state, int acb_state_len, bool voiced, int32_t acb_gain_idx,
                         const float *lags, int num_lags, int subfr_len, bool low_rate,
                         float normalized_bitrate, float *lpc_res,
                         float *acb_basis_scratch, float *acb_scratch) {
    if (voiced) {
        float high_boost = dec_acb_high_boost[0] + (dec_acb_high_boost[1] - dec_acb_high_boost[0]) * normalized_bitrate;
        int i_lag = (int)lags[num_lags - 1];
        if (low_rate) pitch_sharp(lpc_res, i_lag, subfr_len);
        float *acb_basis = acb_basis_scratch;  /* pre-allocated */
        float *acb = acb_scratch;              /* pre-allocated */
        syn_ltp_basis(lags, num_lags, acb_state, acb_state_len, acb_basis);
        float acb_gain[2];
        acb_dequant(low_rate, acb_gain_idx, acb_gain);
        acb_synthesize(subfr_len, acb_basis, acb_gain, high_boost, acb);
        for (int i = 0; i < subfr_len; i++) lpc_res[i] += acb[i];
    }
    /* Update ACB state */
    memmove(acb_state, acb_state + subfr_len, (acb_state_len - subfr_len) * sizeof(float));
    memcpy(acb_state + acb_state_len - 2 * subfr_len, lpc_res, subfr_len * sizeof(float));
}

/* ── filtAR16 ───────────────────────────────────────────────────────────────── */
static void filt_ar16(const float *x, const float a[17], float *ybuf, int base, int n) {
    for (int nn = 0; nn < n; nn++) {
        float res = x[nn];
        for (int i = 0; i < SMPL_ORDER; i++) res -= a[SMPL_ORDER - i] * ybuf[base + nn - SMPL_ORDER + i];
        ybuf[base + nn] = res;
    }
}

/* ── State alloc/free ──────────────────────────────────────────────────────── */
celp_dec_state_t *celp_dec_state_new(void) {
    celp_dec_state_t *s = (celp_dec_state_t *)calloc(1, sizeof(celp_dec_state_t));
    s->acb_state_len = SMPL_SUBFR_LEN + 2 * CELP_MAX_PITCH_LAG + CELP_LTP_INTERPOL_DELAY;
    s->acb_state = (float *)calloc(s->acb_state_len, sizeof(float));
    hp_postfilter_state_init(&s->hp);
    return s;
}

void celp_dec_state_free(celp_dec_state_t *s) {
    if (!s) return;
    free(s->acb_state);
    free(s->hp.x_old);
    free(s);
}

/* ── SynthFrame ─────────────────────────────────────────────────────────────── */
void celp_dec_synth_frame(celp_dec_state_t *s, const float *nlsf, int lsf_interpol_idx,
                           const int32_t *pulses, const celp_dec_params_t *params,
                           bool low_rate, int32_t frame_length16, float *out) {
    const fcb_gains_t *gains = fcb_gains();
    float a[4][17];
    float lsfs[4][16];

    int idx = lsf_interpol_idx;
    if (idx > 1) idx = 1;
    lpc_interpol(nlsf, s->lsf_prev, lsf_interpol4[idx], a, lsfs);

    float norm_br = smpl_get_normalized_bitrate(params->total_pulses, frame_length16);

    float lpc_res[SMPL_INTF_LEN];
    memset(lpc_res, 0, sizeof(lpc_res));

    const float *gain_tab = params->voiced ? gains->v : gains->uv;
    int gain_tab_max = params->voiced ? 33 : 90;
    for (int pos = 0; pos < SMPL_INTF_LEN; pos++) {
        if (pulses[pos] != 0) {
            int sf = pos / SMPL_SUBFR_LEN;
            int gi = params->fcbg_idx[sf];
            if (gi < 0) gi = 0;
            if (gi > gain_tab_max) gi = gain_tab_max;
            lpc_res[pos] = (float)pulses[pos] * gain_tab[gi];
        }
    }

    float ybuf[SMPL_ORDER + SMPL_INTF_LEN];
    memcpy(ybuf, s->lpc_synth_mem, SMPL_ORDER * sizeof(float));

    for (int sf = 0; sf < SMPL_SUBFR_COUNT; sf++) {
        int base = sf * SMPL_SUBFR_LEN;
        float sf_lags[2] = {params->block_lags[2 * sf], params->block_lags[2 * sf + 1]};
        int32_t acbg = params->acbg_idx[sf]; if (acbg < 0) acbg = 0; if (acbg > 15) acbg = 15;
        int32_t fcbg = params->fcbg_idx[sf]; if (fcbg < 0) fcbg = 0; if (fcbg > 90) fcbg = 90;

        celp_decode(s->acb_state, s->acb_state_len, params->voiced, acbg,
                    sf_lags, 2, SMPL_SUBFR_LEN, low_rate, norm_br, &lpc_res[base],
                    s->acb_basis, s->acb_out);

        float nrgres = smpl_decode_resnrg(params->nrgres_dbq_q14[sf], SMPL_SUBFR_LEN);
        if (!params->voiced) s->prev_nrgres = nrgres;

        float noise[160];
        smpl_celp_gen_noise(&s->noise, &lpc_res[base], SMPL_SUBFR_LEN, params->voiced,
                            params->sf_pulses[sf], nrgres, fcbg,
                            lsfs[sf], norm_br, gains->uv, noise);
        for (int i = 0; i < SMPL_SUBFR_LEN; i++) lpc_res[base + i] += noise[i];

        filt_ar16(&lpc_res[base], a[sf], ybuf, SMPL_ORDER + base, SMPL_SUBFR_LEN);
    }

    memcpy(out, ybuf + SMPL_ORDER, SMPL_INTF_LEN * sizeof(float));
    memcpy(s->lpc_synth_mem, ybuf + SMPL_ORDER + SMPL_INTF_LEN - SMPL_ORDER, SMPL_ORDER * sizeof(float));

    /* Post-LPC HP postfilter */
    float lag = 0.0f;
    if (params->voiced) {
        float sl = 0.0f, sll = 0.0f;
        for (int i = 0; i < 8; i++) { sl += params->block_lags[i]; sll += params->block_lags[i] * params->block_lags[i]; }
        if (sl > 0.0f) lag = sll / sl;
    }
    float hp_out[SMPL_INTF_LEN];
    smpl_hp_postfilter(&s->hp, out, SMPL_INTF_LEN, lag, hp_out);
    memcpy(out, hp_out, SMPL_INTF_LEN * sizeof(float));
}