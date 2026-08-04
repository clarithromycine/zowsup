/*
 * post_filter.c — Harmonic postfilter (HP comb + per-packet harm postfilter).
 */

#include "decode.h"
#include "../seed.h"
#include <math.h>
#include <string.h>
#include <stdlib.h>

/* ── Constants ──────────────────────────────────────────────────────────────── */
static const float lo_emph[2] = {1.0f, -0.995f};
static const float smpl_pi_f32 = 3.1415927410125f;

static const float hp_pitch_maf = 0.1f;
static const float hp_def_maf = 0.1f;
static const float hp_def_fcorner_hz = 50.0f;
static const float lag_change_threshold = 1.25f;
static const float hp_postf_transition_speed = 2.0f;

static const float hp_pitch_arf[2] = {0.608057355f, 0.070939485f};
static const float hp_pitch_arr[2] = {-2.187380512f, 2.291030664f};
static const float hp_def_arf[2] = {0.728508218f, 0.476039848f};
static const float hp_def_arr[2] = {-4.363803713f, 8.441854006f};

#define HARM_MAX_FRAMES_PER_PACKET 6
#define HARM_MIN_PITCH_LAG        32
#define HARM_MAX_PITCH_LAG        320
#define HARM_LAG_SUBFR_LEN        40
#define HARM_FB_DELAY             8
#define HARM_DELAY                40
#define HARM_PITCH_NUM_SUBFRAMES  8
#define HARM_FB_STRENGTH          0.4734f
#define HARM_STRENGTH             0.6438f
#define HARM_CUTOFF_HZ            4000.0f
#define HARM_N_HARM_CUTOFF        6.3f
#define HARM_REDUCTION_FAC        0.0579f
#define HARM_LP_FILT_RES          2500
#define HARM_NUM_LP_FILT          (HARM_LP_FILT_RES/80 - HARM_LP_FILT_RES/HARM_MAX_PITCH_LAG + 1)

/* ── cosApprox ─────────────────────────────────────────────────────────────── */
static float cos_approx(float x) { return 1.0f - 0.5f * x * x; }

/* ── smplPfFir3 ────────────────────────────────────────────────────────────── */
static void smpl_pf_fir3(const float *input, int n, const float coef[3], float state[2], float *out) {
    float xm1 = state[0], xm2 = state[1];
    for (int i = 0; i < n; i++) {
        float p1, p2;
        if (i >= 1) p1 = input[i - 1]; else p1 = xm1;
        if (i >= 2) p2 = input[i - 2]; else if (i == 1) p2 = xm1; else p2 = xm2;
        out[i] = coef[0] * input[i] + coef[1] * p1 + coef[2] * p2;
    }
    if (n >= 2) { state[0] = input[n - 1]; state[1] = input[n - 2]; }
    else if (n == 1) { state[1] = xm1; state[0] = input[0]; }
}

/* ── pfFiltAR2 ─────────────────────────────────────────────────────────────── */
static void pf_filt_ar2(const float *input, int n, float c1, float c2, float state[2], float *out) {
    float ytmp0 = state[1], ytmp1 = state[0];
    float ar1 = -c1, ar2 = -c2;
    float ar1_2 = ar1 * ar1, ar1_3 = ar1 * ar1_2, ar1_4 = ar1 * ar1_3;
    float imp1 = ar1, imp2 = ar1_2 + ar2, imp3 = ar1_3 + 2.0f * ar1 * ar2;
    float imp4 = ar1_4 + ar2 * ar2 + 3.0f * ar1_2 * ar2;
    float ymp1 = ar2, ymp2 = ar2 * imp1, ymp3 = ar2 * imp2, ymp4 = ar2 * imp3;
    int nn = 0;
    for (; nn + 3 < n; nn += 4) {
        float xtmp0 = input[nn], xtmp1 = input[nn + 1], xtmp2 = input[nn + 2];
        out[nn + 2] = xtmp2 + imp1 * xtmp1 + imp2 * xtmp0 + imp3 * ytmp1 + ymp3 * ytmp0;
        float xtmp3 = input[nn + 3];
        out[nn + 3] = xtmp3 + imp1 * xtmp2 + imp2 * xtmp1 + imp3 * xtmp0 + imp4 * ytmp1 + ymp4 * ytmp0;
        out[nn] = xtmp0 + imp1 * ytmp1 + ymp1 * ytmp0;
        out[nn + 1] = xtmp1 + imp1 * xtmp0 + imp2 * ytmp1 + ymp2 * ytmp0;
        ytmp0 = out[nn + 2]; ytmp1 = out[nn + 3];
    }
    for (; nn < n; nn++) {
        out[nn] = input[nn] + ar1 * ytmp1 + ar2 * ytmp0;
        ytmp0 = ytmp1; ytmp1 = out[nn];
    }
    state[1] = ytmp0; state[0] = ytmp1;
}

/* ── pfFiltAR1 ─────────────────────────────────────────────────────────────── */
static void pf_filt_ar1(const float *input, int n, float c1, float *state, float *out) {
    float ar1 = -c1;
    float ar1_2 = ar1 * ar1, ar1_3 = ar1 * ar1_2, ar1_4 = ar1 * ar1_3, ar1_5 = ar1 * ar1_4;
    float ytmp = *state;
    int nn = 0;
    for (; nn + 4 < n; nn += 5) {
        float x0 = input[nn], x1 = input[nn+1], x2 = input[nn+2], x3 = input[nn+3], x4 = input[nn+4];
        out[nn + 4] = x4 + ar1*x3 + ar1_2*x2 + ar1_3*x1 + ar1_4*x0 + ar1_5*ytmp;
        out[nn] = x0 + ar1*ytmp;
        out[nn + 1] = x1 + ar1*x0 + ar1_2*ytmp;
        out[nn + 2] = x2 + ar1*x1 + ar1_2*x0 + ar1_3*ytmp;
        out[nn + 3] = x3 + ar1*x2 + ar1_2*x1 + ar1_3*x0 + ar1_4*ytmp;
        ytmp = out[nn + 4];
    }
    for (; nn < n; nn++) { ytmp = input[nn] + ytmp * ar1; out[nn] = ytmp; }
    *state = ytmp;
}

/* ── pfFiltMA1 ─────────────────────────────────────────────────────────────── */
static void pf_filt_ma1(const float *input, int n, float c1, float *state, float *out) {
    float prev = *state;
    for (int i = n - 1; i >= 1; i--) out[i] = input[i] + c1 * input[i - 1];
    if (n > 0) { out[0] = input[0] + c1 * prev; *state = input[n - 1]; }
}

/* ── smplCalcHPCoefs ────────────────────────────────────────────────────────── */
static void smpl_calc_hp_coefs(float maf, const float arf[2], const float arr[2], float f,
                                float coef_ma[3], float coef_ar[3]) {
    coef_ma[0] = 1.0f; coef_ma[1] = -2.0f * cos_approx(2.0f * smpl_pi_f32 * maf * f); coef_ma[2] = 1.0f;
    float far = arf[0] * f + arf[1] * f * f;
    float rar = arr[0] * f + arr[1] * f * f;
    coef_ar[0] = 1.0f;
    coef_ar[1] = -2.0f * cos_approx(2.0f * smpl_pi_f32 * far) * (1.0f + rar);
    coef_ar[2] = 1.0f + (2.0f * rar + rar * rar);
    float sc = (1.0f - coef_ar[1] + coef_ar[2]) / (1.0f - coef_ma[1] + coef_ma[2]);
    coef_ma[0] *= sc; coef_ma[1] *= sc; coef_ma[2] *= sc;
}

/* ── SmplFiltArma2 ─────────────────────────────────────────────────────────── */
static void smpl_filt_arma2(const float *input, int n, const float coef_ma[3], const float coef_ar[3],
                             float state[4], float *out, float *tmp) {
    float ma_st[2] = {state[0], state[1]};
    smpl_pf_fir3(input, n, coef_ma, ma_st, tmp);
    state[0] = ma_st[0]; state[1] = ma_st[1];
    float ar_st[2] = {state[2], state[3]};
    pf_filt_ar2(tmp, n, coef_ar[1], coef_ar[2], ar_st, out);
    state[2] = ar_st[0]; state[3] = ar_st[1];
}

/* ── newCoefs ──────────────────────────────────────────────────────────────── */
static void new_coefs(hp_postfilter_state_t *st, float lag) {
    if (lag > 0.0f) {
        smpl_calc_hp_coefs(hp_pitch_maf, hp_pitch_arf, hp_pitch_arr, 1.0f / lag, st->coef_ma, st->coef_ar);
    } else {
        float fc = hp_def_fcorner_hz;
        smpl_calc_hp_coefs(hp_def_maf, hp_def_arf, hp_def_arr, fc / 16000.0f, st->coef_ma, st->coef_ar);
    }
}

/* ── rampDn ────────────────────────────────────────────────────────────────── */
static float ramp_dn_tab[SMPL_INTF_LEN];
static int ramp_dn_built = 0;

static const float *ramp_dn(void) {
    if (ramp_dn_built) return ramp_dn_tab;
    float d_omega = smpl_pi_f32 / (2.0f * ((float)SMPL_INTF_LEN + 1.0f));
    float omega = d_omega;
    for (int i = 0; i < SMPL_INTF_LEN; i++) {
        ramp_dn_tab[i] = (float)pow((double)mlow_cosf32(omega), (double)hp_postf_transition_speed);
        omega += d_omega;
    }
    ramp_dn_built = 1;
    return ramp_dn_tab;
}

/* ── SmplHpPostfilter ──────────────────────────────────────────────────────── */
void smpl_hp_postfilter(hp_postfilter_state_t *st, const float *x_in, int n, float lag, float *out) {
    float *x = st->scratch_x;
    pf_filt_ar1(x_in, n, lo_emph[1], &st->state_lo_emph1, x);

    bool overlap = false;
    float *y_old = st->scratch_y_old;
    if (st->lag_old < 0.0f) {
        new_coefs(st, lag);
        st->lag_old = lag;
    } else if (lag > lag_change_threshold * st->lag_old || lag_change_threshold * lag < st->lag_old) {
        overlap = true;
        smpl_filt_arma2(x, n, st->coef_ma, st->coef_ar, st->state_hp, y_old, st->scratch_arma_tmp);
        new_coefs(st, lag);
        st->lag_old = lag;
        float *x_old_copy = st->scratch_x_old_copy;
        memcpy(x_old_copy, st->x_old, n * sizeof(float));
        float *dummy = st->scratch_dummy;
        smpl_filt_arma2(x_old_copy, n, st->coef_ma, st->coef_ar, st->state_hp, dummy, st->scratch_arma_tmp);
    } else if (lag != st->lag_old) {
        new_coefs(st, lag);
        st->lag_old = lag;
    }
    memcpy(st->x_old, x, n * sizeof(float));

    float *y_tmp = st->scratch_y_tmp;
    smpl_filt_arma2(x, n, st->coef_ma, st->coef_ar, st->state_hp, y_tmp, st->scratch_arma_tmp);

    if (overlap) {
        const float *ramp = ramp_dn();
        for (int i = 0; i < n; i++) y_tmp[i] += (y_old[i] - y_tmp[i]) * ramp[i];
    }

    pf_filt_ma1(y_tmp, n, lo_emph[1], &st->state_lo_emph2, out);
}

/* ── hp_postfilter_state_init ──────────────────────────────────────────────── */
void hp_postfilter_state_init(hp_postfilter_state_t *st) {
    memset(st, 0, sizeof(*st));
    st->lag_old = -1.0f;
    st->x_old = (float *)calloc(SMPL_INTF_LEN, sizeof(float));
}

/* ── Harm postfilter ────────────────────────────────────────────────────────── */
static int lag_to_filt_ix(int32_t lag) {
    int d = lag + 30;
    if (d < 80) d = 80;
    return HARM_LP_FILT_RES / d - HARM_LP_FILT_RES / HARM_MAX_PITCH_LAG;
}

/* LP filter tables */
static float lp_filters[HARM_NUM_LP_FILT][2 * HARM_FB_DELAY + 1];
static int lp_filters_built = 0;

static void harm_create_lp_filter(float omega0, const float *filt_win, float *blp) {
    float omega_c = omega0 * HARM_N_HARM_CUTOFF;
    float lim = HARM_CUTOFF_HZ / 16000.0f * smpl_pi_f32;
    if (lim < omega_c) omega_c = lim;
    float sum_b = 0.0f;
    float omega_c_sum = omega_c;
    for (int i = 0; i < HARM_FB_DELAY; i++) {
        float b = filt_win[i] * mlow_sinf32(omega_c_sum);
        omega_c_sum += omega_c;
        blp[HARM_FB_DELAY + i + 1] = b;
        blp[HARM_FB_DELAY - i - 1] = b;
        sum_b += 2.0f * b;
    }
    blp[HARM_FB_DELAY] = omega_c;
    sum_b += omega_c;
    float sc = 1.0f / sum_b;
    for (int k = 0; k < 2 * HARM_FB_DELAY + 1; k++) blp[k] *= sc;
}

static void build_lp_filters(void) {
    if (lp_filters_built) return;
    float filt_win[HARM_FB_DELAY];
    float d_omega = (0.5f * smpl_pi_f32) / ((float)HARM_FB_DELAY + 1.0f);
    float omega = d_omega;
    for (int i = 0; i < HARM_FB_DELAY; i++) {
        filt_win[i] = mlow_cosf32(omega) / ((float)i + 1.0f);
        omega += d_omega;
    }
    int ix_prev = -1;
    for (int lag = HARM_MIN_PITCH_LAG; lag <= HARM_MAX_PITCH_LAG; lag++) {
        int ix = lag_to_filt_ix(lag);
        if (ix != ix_prev) {
            harm_create_lp_filter(2.0f * smpl_pi_f32 / (float)lag, filt_win, lp_filters[ix]);
            ix_prev = ix;
        }
    }
    lp_filters_built = 1;
}

/* ── harmDotProd / harmNrg ─────────────────────────────────────────────────── */
static float harm_dot_prod(const float *a, const float *b, int l) {
    float r = 0.0f;
    for (int i = 0; i < l; i++) r += a[i] * b[i];
    return r;
}

static float harm_nrg(const float *x, int n) {
    float r = 0.0f;
    for (int i = 0; i < n; i++) r += x[i] * x[i];
    return r;
}

/* ── harmFiltMA16Sym ───────────────────────────────────────────────────────── */
static void harm_filt_ma16_sym(const float *buf, int x_base, int n, const float coef[17], float *out) {
    for (int nn = 0; nn < n; nn++) {
        int c = x_base + nn;
        float res = buf[c - 8] * coef[8];
        for (int i = 0; i < 8; i++) res += coef[i] * (buf[c - i] + buf[c - 16 + i]);
        out[nn] = res;
    }
}

/* ── harmPostfilterCore ────────────────────────────────────────────────────── */
static void harm_postfilter_core(float lpcoefs[17], const float *comb, int comb_x,
                                   int32_t future_samples, int32_t lag,
                                   float *diff, int diff_base, float *out, int out_off, int l,
                                   float fb_strength, int32_t *prev_did_filter) {
    build_lp_filters();
    int lag_u = (int)lag;
    float xy = 0.0f;
    if (lag > 0) {
        int lookforward = l + lag - future_samples;
        if (lookforward > 0) {
            int l2 = l - lookforward;
            if (l2 < 0) l2 = 0;
            for (int i = 0; i < l2; i++) out[out_off + i] = comb[comb_x + i - lag_u] + comb[comb_x + i + lag_u];
            for (int i = 0; i < l - l2; i++) out[out_off + l2 + i] = comb[comb_x + l2 + i - lag_u] + comb[comb_x + l2 + i];
        } else {
            for (int i = 0; i < l; i++) out[out_off + i] = comb[comb_x + i - lag_u] + comb[comb_x + i + lag_u];
        }
        xy = harm_dot_prod(&comb[comb_x], &out[out_off], l);
    }

    if (lag > 0 && xy > 0.0f) {
        float xx = harm_nrg(&comb[comb_x], l);
        float yy = 0.25f * harm_nrg(&out[out_off], l);
        float denom = yy;
        if (xx > denom) denom = xx;
        float strength = 0.5f * xy / denom;
        float high_lag_reduction = 1.0f - HARM_REDUCTION_FAC * ((float)(lag - HARM_MIN_PITCH_LAG) / (float)(HARM_MAX_PITCH_LAG - HARM_MIN_PITCH_LAG));
        strength = strength * high_lag_reduction * HARM_STRENGTH;
        for (int i = 0; i < l; i++) out[out_off + i] *= 0.5f * strength;
        for (int i = 0; i < l; i++) diff[diff_base + i] = out[out_off + i] + (-strength) * comb[comb_x + i];
        const float *kernel = lp_filters[lag_to_filt_ix(lag)];
        for (int k = 0; k < 2 * HARM_FB_DELAY + 1; k++) lpcoefs[k] = kernel[k] * fb_strength;
        float yh[40];
        harm_filt_ma16_sym(diff, diff_base, l, lpcoefs, yh);
        for (int i = 0; i < l; i++) out[out_off + i] = yh[i] + comb[comb_x - HARM_FB_DELAY + i];
        *prev_did_filter = 1;
    } else {
        for (int i = 0; i < 40; i++) diff[diff_base + i] = 0.0f;
        if (*prev_did_filter != 0) {
            float yh[2 * HARM_FB_DELAY];
            harm_filt_ma16_sym(diff, diff_base, 2 * HARM_FB_DELAY, lpcoefs, yh);
            for (int i = 0; i < 2 * HARM_FB_DELAY; i++) out[out_off + i] = yh[i] + comb[comb_x - HARM_FB_DELAY + i];
            for (int i = 2 * HARM_FB_DELAY; i < l; i++) out[out_off + i] = comb[comb_x + HARM_FB_DELAY + i - 2 * HARM_FB_DELAY];
        } else {
            for (int i = 0; i < l; i++) out[out_off + i] = comb[comb_x - HARM_FB_DELAY + i];
        }
        *prev_did_filter = 0;
    }
}

/* ── SmplHarmPostfilter ────────────────────────────────────────────────────── */
void smpl_harm_postfilter(harm_postfilter_state_t *st, float *x, int x_len,
                          const float *lags, int n_lags, float normalized_bitrate) {
    int diff_prefix = 2 * HARM_FB_DELAY;
    /* diff needs to hold diff_prefix + up to 8*40=320 samples + margin for harm_filt_ma16_sym */
    /* harm_filt_ma16_sym accesses buf[c-16+i] where c = diff_base+nn, i up to 7 */
    /* max index = diff_prefix + 320 + 39 + 7 = 16 + 320 + 46 = 382 */
    int diff_size = diff_prefix + HARM_PITCH_NUM_SUBFRAMES * HARM_LAG_SUBFR_LEN + 64;
    float *diff = (float *)calloc(diff_size, sizeof(float));

    int32_t lag = st->prev_lag;
    int comb_cur = HARM_MAX_PITCH_LAG + HARM_DELAY;
    memcpy(&st->state_comb[comb_cur], x, x_len * sizeof(float));

    float fb_strength = 1.0f - HARM_FB_STRENGTH * normalized_bitrate;
    int offset1 = 0;
    int lag_ctr = 0;
    while (lag_ctr < n_lags) {
        int offset2 = 0;
        memcpy(&diff[diff_prefix - 16], st->state1, 16 * sizeof(float));
        int lag_ctr_end = lag_ctr + HARM_PITCH_NUM_SUBFRAMES;
        if (lag_ctr_end > n_lags) lag_ctr_end = n_lags;
        while (lag_ctr < lag_ctr_end) {
            int comb_x = HARM_MAX_PITCH_LAG + offset1;
            int32_t future_samples = HARM_DELAY + x_len - offset1;
            harm_postfilter_core(st->lpcoefs, st->state_comb, comb_x, future_samples, lag,
                                  diff, diff_prefix + offset2, x, offset1, HARM_LAG_SUBFR_LEN,
                                  fb_strength, &st->prev_did_filter);
            offset1 += HARM_LAG_SUBFR_LEN;
            offset2 += HARM_LAG_SUBFR_LEN;
            lag = (int32_t)round((double)lags[lag_ctr]);
            lag_ctr++;
        }
        memcpy(st->state1, &diff[diff_prefix + offset2 - 16], 16 * sizeof(float));
    }

    st->prev_lag = lag;
    memcpy(&st->state_comb[0], &st->state_comb[x_len], comb_cur * sizeof(float));
    free(diff);
}

/* ── harm_postfilter_state_init / new / free ───────────────────────────────── */
void harm_postfilter_state_init(harm_postfilter_state_t *st) {
    memset(st, 0, sizeof(*st));
    st->state_comb = (float *)calloc(HARM_STATE_COMB_LEN, sizeof(float));
}

harm_postfilter_state_t *harm_postfilter_state_new(void) {
    harm_postfilter_state_t *st = (harm_postfilter_state_t *)calloc(1, sizeof(harm_postfilter_state_t));
    harm_postfilter_state_init(st);
    return st;
}

void harm_postfilter_state_free(harm_postfilter_state_t *st) {
    if (!st) return;
    free(st->state_comb);
    free(st);
}