/*
 * celp_enc.c �?CELP excitation encoder.
 */
#include "encode.h"
#include "../seed.h"
#include "../decode/decode.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#define SMPL_PI_F32 3.1415926535897f
#define CELP_MAX_PITCH_LAG 320

/* ══════════════════════════════════════════════════════════════════════════════
 * Constants
 * ══════════════════════════════════════════════════════════════════════════════ */
#define CELP_LTP_INTERPOL_DELAY  8
#define CELP_LAG_SUBFR_LEN      40
#define CELP_MAX_PITCH_LEN      320
#define CELP_G_ACB_RD_MU        0.014999999664723873f
#define FCBG_V_DELTA_N          67
#define V_GAIN_MIN_DB          -100.0f
#define V_GAIN_MAX_DB             0.0f
#define V_GAIN_STEP_DB            3.0f
#define UV_GAIN_MIN_DB          -90.0f
#define UV_GAIN_MAX_DB            0.0f
#define UV_GAIN_STEP_DB           1.0f
#define RATE_ACB_SCALE            0.9f
#define PITCH_SHARPENING_COEF     0.9881f
#define CELP_MAX_NUM_SURV         8
#define N_GAIN_STEPS              3

#define ACBG_M  2
#define ACBG_N 16
#define SMPL_MAX_SF_LEN_E        160
#define SMPL_MAX_L_RESP_E         33

#define FCBG_VN  34
#define UV_GAIN_IDX_LEN 90

/* ── celpInterpolKernel ─────────────────────────────────────────────────────── */
static const float celp_interpol_kernel[16] = {
    -6.3925986e-6f, 0.00011064114f, -0.0009153038f, 0.00484772f,
    -0.018698348f, 0.05759091f, -0.15997477f, 0.6170455f,
    0.61704546f, -0.15997475f, 0.057590906f, -0.018698348f,
    0.00484772f, -0.0009153038f, 0.000110641144f, -6.392598e-6f,
};

/* ── cbAcbgains tables ──────────────────────────────────────────────────────── */
static const int16_t cb_acbgains_hr_q14[ACBG_N * ACBG_M] = {
    16039, 91, 0, 0, 4310, 4930, -1431, 2862, 2893, 0, 8009, 4075, 2754, 4223, 8367, 354,
    4640, 1254, -176, 2734, -1222, 5017, -476, 1506, 11351, 567, 1243, 0, 10601, 22, 14088, 108,
};
static const int16_t cb_acbgains_lr_q14[ACBG_N * ACBG_M] = {
    2812, 2484, 0, 0, -362, 2465, -337, 703, 3033, 1474, 13536, 220, -2630, 9226, 6032, 3499,
    -220, 441, 7661, 4243, 11521, 0, 1430, 779, 4495, 2724, 15535, 343, -779, 1559, 480, 481,
};

/* ── FCB gain tables (uvGainIdxLen + 1 = 91) ───────────────────────────────── */
static float fcbgains_uv_tbl[91];
static bool fcbgains_uv_built = false;

/* ══════════════════════════════════════════════════════════════════════════════
 * Leaf math helpers
 * ══════════════════════════════════════════════════════════════════════════════ */

static float celp_dot_prod(const float *a, const float *b, int l) {
    float r = 0.0f;
    for (int i = 0; i < l; i++) r += a[i] * b[i];
    return r;
}

static float celp_nrg(const float *x, int n) {
    float s = 0.0f;
    for (int k = 0; k < n; k++) s += x[k] * x[k];
    return s;
}

static void celp_reverse(float *x, int l) {
    for (int i = 0; i < l/2; i++) {
        float tmp = x[i]; x[i] = x[l-i-1]; x[l-i-1] = tmp;
    }
}

static void celp_sub_vec(const float *y, const float *z, float *x, int l) {
    for (int i = 0; i < l; i++) x[i] = y[i] - z[i];
}

static void celp_add_vec_inplace(const float *y, float *x, int l) {
    for (int i = 0; i < l; i++) x[i] += y[i];
}

static void celp_scale_vec_inplace(float *x, int l, float g) {
    for (int i = 0; i < l; i++) x[i] *= g;
}

static void celp_scale_vec(const float *x, float *y, int l, float g) {
    for (int i = 0; i < l; i++) y[i] = x[i] * g;
}

static void celp_add_scale_vec_inplace(const float *x, float *y, int l, float g) {
    for (int i = 0; i < l; i++) y[i] += g * x[i];
}

static void celp_add_scale_vec(const float *x0, const float *x1, float *y, int l, float g) {
    for (int i = 0; i < l; i++) y[i] = x0[i] + g * x1[i];
}

static void celp_mul_vec_inplace(const float *x, float *y, int l) {
    for (int i = 0; i < l; i++) y[i] *= x[i];
}

static void celp_q(const float *num, const float *den, int l, float *q) {
    for (int i = 0; i < l; i++) q[i] = (num[i] * num[i]) / den[i];
}

/* ══════════════════════════════════════════════════════════════════════════════
 * Toeplitz multiply + filters
 * ══════════════════════════════════════════════════════════════════════════════ */

static void celp_mult_symtoepl2(const float *c, int l_resp, const float *x, float *y, int n) {
    int length = l_resp, nn = 0;
    while (nn < l_resp - 1) {
        y[nn] = celp_dot_prod(c + l_resp - 1 - nn, x, length);
        length++; nn++;
    }
    length = 2 * l_resp;
    while (nn < n - l_resp) {
        y[nn] = celp_dot_prod(c, x + nn + 1 - l_resp, length);
        nn++;
    }
    while (nn < n) {
        length--;
        y[nn] = celp_dot_prod(c, x + nn + 1 - l_resp, length);
        nn++;
    }
}

static void celp_filt_ar16(const float *x, int n, const float *coef, int y_base, float *y) {
    for (int nn = 0; nn < n; nn++) {
        float res = x[nn];
        for (int i = 0; i < 16; i++) res -= coef[16-i] * y[y_base+nn-16+i];
        y[y_base+nn] = res;
    }
}

static void celp_filt_ma(const float *x, int x_base, int n, const float *coef, int coef_len, float *y) {
    int i;
    if (coef[0] == 1.0f) {
        for (int k = 0; k < n; k++) y[k] = x[x_base+k] + coef[1]*x[x_base+k-1];
        i = 2;
    } else {
        for (int k = 0; k < n; k++) y[k] = coef[0] * x[x_base+k];
        i = 1;
    }
    for (; i < coef_len; i++)
        for (int k = 0; k < n; k++)
            y[k] += coef[i] * x[x_base+k-i];
}

static void celp_filt_ma9(const float *x, int x_base, int n, const float *coef, int _unused, float *y) {
    (void)_unused;
    for (int nn = 0; nn < n; nn++) {
        float res = 0.0f;
        for (int i = 0; i < 10; i++) res += coef[i] * x[x_base+nn-i];
        y[nn] = res;
    }
}

/* ══════════════════════════════════════════════════════════════════════════════
 * DCMF/CMF table builders
 * ══════════════════════════════════════════════════════════════════════════════ */

/* Use seed.c's celp_dcmf_to_cmf */

static void celp_cmf_to_bits(const uint16_t *cmf, int cmf_len, float *bits) {
    for (int i = 0; i < cmf_len - 1; i++)
        bits[i] = -(float)log2((double)((float)(cmf[i+1]-cmf[i]) / (float)cmf[cmf_len-1]));
}

static int celp_get_maxi(const float *x, int x_len) {
    int i = 0;
    float mx = x[0];
    for (int n = 1; n < x_len; n++) { if (x[n] > mx) { mx = x[n]; i = n; } }
    return i;
}

static void celp_get_maxi_k(const float *x, int32_t *idx, int x_len, int k) {
    bool taken[256]; /* max x_len is fcbSubfrlen=80 */
    memset(taken, 0, sizeof(taken));
    for (int kk = 0; kk < k; kk++) {
        float best = -1e30f; int bi = 0; bool found = false;
        for (int n = 0; n < x_len; n++) {
            if (!taken[n] && (!found || x[n] > best)) { best = x[n]; bi = n; found = true; }
        }
        taken[bi] = true; idx[kk] = (int32_t)bi;
    }
}

/* ══════════════════════════════════════════════════════════════════════════════
 * CELP tables
 * ══════════════════════════════════════════════════════════════════════════════ */

/* ── DCMF tables ─────────────────────────────────────────────────────────────── */

static const uint8_t celp_acbgains_dcmf_lr[(ACBG_N+1)*ACBG_N] = {
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

static const uint8_t celp_acbgains_dcmf_hr[(ACBG_N+1)*ACBG_N] = {
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

static const uint8_t celp_fcbg_v_dcmf[FCBG_VN] = {
    107, 12, 17, 25, 31, 41, 52, 65, 83, 103, 122, 146, 169, 191, 210, 227,
    240, 249, 255, 253, 246, 229, 200, 161, 120, 82, 51, 29, 14, 6, 2, 2, 2, 2,
};

static const uint8_t celp_fcbg_v_delta_dcmf[FCBG_V_DELTA_N] = {
    1, 1, 1, 1, 1, 1, 1, 1, 2, 3, 4, 6, 8, 10, 12, 12,
    12, 13, 14, 14, 14, 13, 12, 11, 10, 9, 8, 9, 15, 33, 65, 119,
    196, 255, 220, 144, 90, 57, 36, 23, 17, 14, 12, 12, 12, 13, 12, 12,
    12, 12, 12, 11, 11, 10, 9, 7, 6, 4, 3, 2, 1, 1, 1, 1, 1, 1, 1,
};

#define CELP_G_ACB_RD_MU 0.014999999664723873f

typedef struct {
    float acbg_inv_prob_lr[(ACBG_N+1)*ACBG_N];
    float acbg_inv_prob_hr[(ACBG_N+1)*ACBG_N];
    float fcbgains_v[FCBG_VN];
    float fcbg_v_inv_prob[FCBG_VN];
    float fcbg_v_delta_inv_prob[FCBG_V_DELTA_N];
} celp_tables_t;

static celp_tables_t g_celp_tables;
static bool g_celp_tables_built = false;

static void build_celp_tables(void) {
    if (g_celp_tables_built) return;

    if (!fcbgains_uv_built) {
        for (int ix = 0; ix <= UV_GAIN_IDX_LEN; ix++)
            fcbgains_uv_tbl[ix] = (float)pow(10.0, 0.05 * (double)((float)ix * UV_GAIN_STEP_DB + UV_GAIN_MIN_DB));
        fcbgains_uv_built = true;
    }

    for (int ix = 0; ix < FCBG_VN; ix++)
        g_celp_tables.fcbgains_v[ix] = (float)pow(10.0, 0.05 * (double)((float)ix * V_GAIN_STEP_DB + V_GAIN_MIN_DB));

    uint16_t acb_cmf_lr[(ACBG_N+1)*(ACBG_N+1)];
    uint16_t acb_cmf_hr[(ACBG_N+1)*(ACBG_N+1)];
    for (int i = 0; i < ACBG_N + 1; i++) {
        celp_dcmf_to_cmf(celp_acbgains_dcmf_lr + i*ACBG_N, ACBG_N, acb_cmf_lr + i*(ACBG_N+1));
        celp_dcmf_to_cmf(celp_acbgains_dcmf_hr + i*ACBG_N, ACBG_N, acb_cmf_hr + i*(ACBG_N+1));
    }
    for (int i = 0; i < ACBG_N + 1; i++) {
        celp_cmf_to_bits(acb_cmf_lr + i*(ACBG_N+1), ACBG_N+1, g_celp_tables.acbg_inv_prob_lr + i*ACBG_N);
        celp_cmf_to_bits(acb_cmf_hr + i*(ACBG_N+1), ACBG_N+1, g_celp_tables.acbg_inv_prob_hr + i*ACBG_N);
        for (int j = 0; j < ACBG_N; j++) {
            g_celp_tables.acbg_inv_prob_lr[i*ACBG_N+j] = (float)pow(2.0, (double)(g_celp_tables.acbg_inv_prob_lr[i*ACBG_N+j] * CELP_G_ACB_RD_MU));
            g_celp_tables.acbg_inv_prob_hr[i*ACBG_N+j] = (float)pow(2.0, (double)(g_celp_tables.acbg_inv_prob_hr[i*ACBG_N+j] * CELP_G_ACB_RD_MU));
        }
    }

    uint16_t fcbg_v_cmf[FCBG_VN+1];
    uint16_t fcbg_v_delta_cmf[FCBG_V_DELTA_N+1];
    celp_dcmf_to_cmf(celp_fcbg_v_dcmf, FCBG_VN, fcbg_v_cmf);
    celp_dcmf_to_cmf(celp_fcbg_v_delta_dcmf, FCBG_V_DELTA_N, fcbg_v_delta_cmf);
    celp_cmf_to_bits(fcbg_v_cmf, FCBG_VN+1, g_celp_tables.fcbg_v_inv_prob);
    for (int i = 0; i < FCBG_VN; i++)
        g_celp_tables.fcbg_v_inv_prob[i] = (float)pow(2.0, (double)(g_celp_tables.fcbg_v_inv_prob[i] * CELP_G_ACB_RD_MU));
    celp_cmf_to_bits(fcbg_v_delta_cmf, FCBG_V_DELTA_N+1, g_celp_tables.fcbg_v_delta_inv_prob);
    for (int i = 0; i < FCBG_V_DELTA_N; i++)
        g_celp_tables.fcbg_v_delta_inv_prob[i] = (float)pow(2.0, (double)(g_celp_tables.fcbg_v_delta_inv_prob[i] * CELP_G_ACB_RD_MU));

    g_celp_tables_built = true;
}

static celp_tables_t *get_celp_tables(void) {
    build_celp_tables();
    return &g_celp_tables;
}

/* ══════════════════════════════════════════════════════════════════════════════
 * ACB/LTP synthesis
 * ══════════════════════════════════════════════════════════════════════════════ */

static void celp_acb_dequant(bool low_rate, int32_t acb_idx, float acb_g[ACBG_M]) {
    const int16_t *cb = low_rate ? cb_acbgains_lr_q14 : cb_acbgains_hr_q14;
    float sc_q14 = 1.0f / (float)((int32_t)1 << 14);
    for (int m = 0; m < ACBG_M; m++)
        acb_g[m] = (float)cb[(int)acb_idx * ACBG_M + m] * sc_q14;
}

static void celp_acb_synthesize(int fcb_subfrlen, const float *acb_basis, const float acb_g[ACBG_M], float *acb) {
    celp_scale_vec(acb_basis, acb, fcb_subfrlen, acb_g[0]);
    celp_add_scale_vec_inplace(acb_basis + fcb_subfrlen, acb, fcb_subfrlen, acb_g[1]);
}

static void celp_pitch_sharp(float *x, int lag, int l) {
    for (int i = lag; i < l; i++) x[i] += x[i-lag] * PITCH_SHARPENING_COEF;
}

static void celp_syn_ltp_basis(const float *lags, int n_lags, float *state, int state_len, float *acb_basis) {
    int p = state_len - n_lags * CELP_LAG_SUBFR_LEN;
    for (int subfr = 0; subfr < n_lags; subfr++) {
        int i_lag = (int)floorf(lags[subfr]);
        if ((float)i_lag == lags[subfr]) {
            int il = i_lag;
            for (int i = 0; i < CELP_LAG_SUBFR_LEN; i++) state[p+i] = state[(p+i)-il];
            for (int i = 0; i < CELP_LAG_SUBFR_LEN; i++) acb_basis[subfr*CELP_LAG_SUBFR_LEN+i] = state[p+i];
            for (int i = 0; i < CELP_LAG_SUBFR_LEN; i++) {
                float a = state[(p+i)-il-1], b = state[(p+i)-il+1];
                acb_basis[(n_lags+subfr)*CELP_LAG_SUBFR_LEN+i] = a + b;
            }
        } else {
            int il = i_lag;
            int base_first = p + (-1 - il - CELP_LTP_INTERPOL_DELAY);
            float first = celp_dot_prod(state + base_first, celp_interpol_kernel, 2*CELP_LTP_INTERPOL_DELAY);
            int src_base = p + (-il - CELP_LTP_INTERPOL_DELAY);
            for (int nn = 0; nn < CELP_LAG_SUBFR_LEN; nn++) {
                float ret = 0.0f;
                for (int i = 0; i < 8; i++)
                    ret += (state[src_base+nn+i] + state[src_base+nn+15-i]) * celp_interpol_kernel[i];
                state[p+nn] = ret;
            }
            int base_last = p + (CELP_LAG_SUBFR_LEN - 1 - il - CELP_LTP_INTERPOL_DELAY);
            float last = celp_dot_prod(state + base_last, celp_interpol_kernel, 2*CELP_LTP_INTERPOL_DELAY);
            for (int i = 0; i < CELP_LAG_SUBFR_LEN; i++) acb_basis[subfr*CELP_LAG_SUBFR_LEN+i] = state[p+i];
            int b1 = (n_lags + subfr) * CELP_LAG_SUBFR_LEN;
            acb_basis[b1] = first + state[p+1];
            for (int i = 0; i < CELP_LAG_SUBFR_LEN-2; i++) acb_basis[b1+1+i] = state[p+i] + state[p+i+2];
            acb_basis[b1+CELP_LAG_SUBFR_LEN-1] = state[p+CELP_LAG_SUBFR_LEN-2] + last;
        }
        p += CELP_LAG_SUBFR_LEN;
    }
}

/* ══════════════════════════════════════════════════════════════════════════════
 * FCB search helpers
 * ══════════════════════════════════════════════════════════════════════════════ */

static void celp_calc_d_abs_and_sign(const float *d, int l, float *d_abs, float *d_sign) {
    for (int i = 0; i < l; i++) {
        if (d[i] > 0.0f) { d_abs[i] = d[i]; d_sign[i] = 1.0f; }
        else { d_abs[i] = -d[i]; d_sign[i] = -1.0f; }
    }
}

static bool celp_check_if_better(float wnrg, float *nrg_thr, float wnrg_per_pulse) {
    *nrg_thr += wnrg_per_pulse;
    if (wnrg > *nrg_thr) { *nrg_thr = wnrg; return true; }
    return false;
}

static int32_t celp_phi_col_offset(int32_t col) { return (int32_t)SMPL_MAX_SF_LEN_E - col; }

static void celp_non_zero_range(int32_t col, int perc_resp_len, int fcb_subfrlen, int *lo, int *hi) {
    *lo = (int)(col - (int32_t)perc_resp_len + 1); if (*lo < 0) *lo = 0;
    *hi = (int)(col + (int32_t)perc_resp_len); if (*hi > fcb_subfrlen) *hi = fcb_subfrlen;
}

/* ══════════════════════════════════════════════════════════════════════════════
 * Gain helpers
 * ══════════════════════════════════════════════════════════════════════════════ */

static float celp_wnrg2(const float *c, const float *x) {
    return x[0]*(c[0]*x[0]+c[1]*x[1]) + x[1]*(c[2]*x[0]+c[3]*x[1]);
}

static float celp_wnrg3(const float *c, const float *x) {
    return x[0]*(c[0]*x[0]+c[1]*x[1]+c[2]*x[2]) +
           x[1]*(c[3]*x[0]+c[4]*x[1]+c[5]*x[2]) +
           x[2]*(c[6]*x[0]+c[7]*x[1]+c[8]*x[2]);
}

static int16_t celp_quant_gain_uv(float gain_from_search) {
    float gain_db = 20.0f * log10f(gain_from_search + 1e-16f);
    if (gain_db < UV_GAIN_MIN_DB) gain_db = UV_GAIN_MIN_DB;
    if (gain_db > UV_GAIN_MAX_DB) gain_db = UV_GAIN_MAX_DB;
    return (int16_t)roundf((gain_db - UV_GAIN_MIN_DB) / UV_GAIN_STEP_DB);
}

static void celp_fcb_synthesize(int fcb_subfrlen, const int16_t *pulses, int n_pulses, float *fcb) {
    for (int i = 0; i < fcb_subfrlen; i++) fcb[i] = 0.0f;
    for (int n = 0; n < n_pulses; n++) {
        int32_t sign = 1 + 2*((int32_t)pulses[n] >> 15);
        int32_t pos = (int32_t)pulses[n] * sign - 1;
        fcb[pos] += (float)sign;
    }
}

/* ══════════════════════════════════════════════════════════════════════════════
 * acbgParams + CelpEncoder struct
 * ══════════════════════════════════════════════════════════════════════════════ */

typedef struct {
    float  werr_in;
    float  phi_acb[ACBG_M * ACBG_M];
    float  d_acb_lpc[ACBG_M];
    float *acb_basis_phi;
} acbg_params_t;

struct CelpEncoder {
    float   *state_wght_buf;   /* smplMaxSfLen + SmplLPCOrder */
    float    state_err_lpc_syn[SMPL_LPC_ORDER];
    float    hanning_win[SMPL_MAX_L_RESP_E];
    uint64_t sgntrs[SMPL_MAX_SF_LEN_E];
    float   *acb_state;
    int      acb_state_len;
    int32_t  prev_acb_idx[2];
    int32_t  prev_fcb_idx[2];
    int32_t  subfr_cnt;
    int32_t  subfr_per_packet;
    int      fcb_subfrlen;
    int      perc_resp_len;
    bool     low_rate;
    bool     ignore_zir;
    float    fcbgain;
    bool     use_ma9;
    float   *imp_lpc_buf;
    float   *phi;
    float   *phi_flip;
    /* Pre-allocated scratch buffers (eliminate per-subframe calloc) */
    float    res_lpc_pad[SMPL_MAX_SF_LEN_E + SMPL_MAX_L_RESP_E]; /* fcb_subfrlen + l_resp + 1 */
    float    acb_basis_phi[ACBG_M * SMPL_MAX_SF_LEN_E];
    float    acb_basis[ACBG_M * SMPL_MAX_SF_LEN_E];
    float    acb_tmp[SMPL_MAX_SF_LEN_E]; /* used in calc_acb_gain */
};

/* ── percFiltMa method ──────────────────────────────────────────────────────── */
static void perc_filt_ma(const CelpEncoder *e, const float *x, int x_base, int n,
                          const float *coef, int coef_len, float *y) {
    if (e->use_ma9) celp_filt_ma9(x, x_base, n, coef, coef_len, y);
    else celp_filt_ma(x, x_base, n, coef, coef_len, y);
}

/* ══════════════════════════════════════════════════════════════════════════════
 * Greedy FCB search
 * ══════════════════════════════════════════════════════════════════════════════ */

static void smpl_fcb_search(CelpEncoder *e, const float *d,
                            const float wnrg_per_pulse[2],
                            const int16_t fcb_pulses_max[2],
                            int16_t pulses[2][SMPL_MAX_PULSES_PER_SF_E],
                            int16_t n_pulses[2],
                            float wnrg[2], float gain_from_search[2], float fcb_wnrg[2]) {
    int fcb_subfrlen = e->fcb_subfrlen;
    int perc_resp_len = e->perc_resp_len;
    n_pulses[0] = n_pulses[1] = 0;

    int32_t positions[SMPL_MAX_PULSES_PER_SF_E];
    float d_abs[SMPL_MAX_SF_LEN_E], d_sign[SMPL_MAX_SF_LEN_E];
    float num[SMPL_MAX_SF_LEN_E], den[SMPL_MAX_SF_LEN_E];
    float phi0 = e->phi[0];

    celp_calc_d_abs_and_sign(d, fcb_subfrlen, d_abs, d_sign);
    for (int i = 0; i < fcb_subfrlen; i++) den[i] = phi0 + 1e-16f;
    memcpy(num, d_abs, fcb_subfrlen * sizeof(float));
    positions[0] = (int32_t)celp_get_maxi(num, fcb_subfrlen);

    float nrg_thr[2] = {0, 0};
    int p0 = (int)positions[0];
    float ratio = num[p0] / den[p0];
    float wnrg0 = num[p0] * ratio;

    if (celp_check_if_better(wnrg0, &nrg_thr[1], wnrg_per_pulse[1])) {
        n_pulses[1] = 1; wnrg[1] = wnrg0;
        gain_from_search[1] = ratio; fcb_wnrg[1] = den[p0];
        if (fcb_pulses_max[0] > 0) {
            n_pulses[0] = 1; wnrg[0] = wnrg0;
            gain_from_search[0] = ratio; fcb_wnrg[0] = den[p0];
        }
    }

    for (int pulse_nr = 1; pulse_nr < (int)fcb_pulses_max[1]; pulse_nr++) {
        int32_t position = positions[pulse_nr-1];
        float sgn = d_sign[position];
        for (int i = 0; i < fcb_subfrlen; i++) num[i] += d_abs[position];

        int nz0, nz1;
        celp_non_zero_range(position, perc_resp_len, fcb_subfrlen, &nz0, &nz1);
        int32_t col_off = celp_phi_col_offset(position);
        float d_den = 0.0f;
        for (int i = 0; i < pulse_nr - 1; i++) {
            int pi = (int)positions[i];
            d_den += e->phi_flip[(int)(col_off + pi)] * d_sign[pi];
        }
        d_den *= 2.0f * sgn;
        d_den += e->phi_flip[(int)(col_off + position)];
        for (int i = 0; i < fcb_subfrlen; i++) den[i] += d_den;
        for (int i = nz0; i < nz1; i++)
            den[i] += 2.0f * sgn * d_sign[i] * e->phi_flip[(int)(col_off + i)];

        float q[SMPL_MAX_SF_LEN_E];
        celp_q(num, den, fcb_subfrlen, q);
        positions[pulse_nr] = (int32_t)celp_get_maxi(q, fcb_subfrlen);
        int pp = (int)positions[pulse_nr];

        if (celp_check_if_better(q[pp], &nrg_thr[1], wnrg_per_pulse[1])) {
            n_pulses[1] = (int16_t)(pulse_nr + 1);
            wnrg[1] = q[pp]; gain_from_search[1] = num[pp] / den[pp]; fcb_wnrg[1] = den[pp];
        }
        if ((int)fcb_pulses_max[0] >= pulse_nr &&
            celp_check_if_better(q[pp], &nrg_thr[0], wnrg_per_pulse[0])) {
            n_pulses[0] = (int16_t)(pulse_nr + 1);
            wnrg[0] = q[pp]; gain_from_search[0] = num[pp] / den[pp]; fcb_wnrg[0] = den[pp];
        }
    }

    for (int r = 0; r <= 1; r++) {
        if (nrg_thr[r] > 0.0f) {
            for (int i = 0; i < (int)n_pulses[r]; i++) {
                int32_t pos = positions[i];
                pulses[r][i] = d_sign[pos] > 0.0f ? (int16_t)(1 + pos) : (int16_t)(-(1 + pos));
            }
        } else {
            wnrg[r] = 0.0f; gain_from_search[r] = 0.0f; fcb_wnrg[r] = 0.0f; n_pulses[r] = 0;
        }
    }
}

/* ══════════════════════════════════════════════════════════════════════════════
 * calcAcbGain
 * ══════════════════════════════════════════════════════════════════════════════ */

static int32_t calc_acb_gain(CelpEncoder *e, int l_resp, const float *acb_basis,
                              const float *d_lpc, acbg_params_t *acbg, float *d_ltp) {
    int fcb_subfrlen = e->fcb_subfrlen;
    float *tmp = e->acb_tmp;  /* pre-allocated, no calloc */

    for (int m = 0; m < ACBG_M; m++) {
        int c_off = SMPL_MAX_SF_LEN_E - l_resp + 1;
        celp_mult_symtoepl2(e->phi_flip + c_off, l_resp, acb_basis + m*fcb_subfrlen, tmp, fcb_subfrlen);
        memcpy(acbg->acb_basis_phi + m*fcb_subfrlen, tmp, fcb_subfrlen * sizeof(float));
        for (int i = 0; i < ACBG_M; i++)
            acbg->phi_acb[m*ACBG_M+i] = celp_dot_prod(acb_basis + i*fcb_subfrlen, acbg->acb_basis_phi + m*fcb_subfrlen, fcb_subfrlen);
        acbg->d_acb_lpc[m] = celp_dot_prod(acb_basis + m*fcb_subfrlen, d_lpc, fcb_subfrlen);
    }

    float best_rd = 1e30f; int32_t best_acbg_idx = 0;
    int32_t transition_idx = 0;
    if (e->prev_acb_idx[1] != -1) transition_idx = e->prev_acb_idx[1] + 1;

    celp_tables_t *tbl = get_celp_tables();
    const float *inv_prob = (e->low_rate ? tbl->acbg_inv_prob_lr : tbl->acbg_inv_prob_hr)
                            + (int)transition_idx * ACBG_N;
    const int16_t *cb = e->low_rate ? cb_acbgains_lr_q14 : cb_acbgains_hr_q14;
    float sc_q14 = 1.0f / (float)((int32_t)1 << 14);

    float acb_gains[ACBG_M];
    for (int n = 0; n < ACBG_N; n++) {
        for (int m = 0; m < ACBG_M; m++) acb_gains[m] = (float)cb[n*ACBG_M+m] * sc_q14;
        float werr_out = acbg->werr_in + celp_wnrg2(acbg->phi_acb, acb_gains)
                       - 2.0f*(acbg->d_acb_lpc[0]*acb_gains[0] + acbg->d_acb_lpc[1]*acb_gains[1]);
        float rd = werr_out * inv_prob[n];
        if (rd < best_rd) { best_rd = rd; best_acbg_idx = (int32_t)n; }
    }

    float g0 = -(float)cb[(int)best_acbg_idx * ACBG_M] * sc_q14;
    celp_add_scale_vec(d_lpc, acbg->acb_basis_phi, d_ltp, fcb_subfrlen, g0);
    float g1 = -(float)cb[(int)best_acbg_idx * ACBG_M + 1] * sc_q14;
    celp_add_scale_vec_inplace(acbg->acb_basis_phi + fcb_subfrlen, d_ltp, fcb_subfrlen, g1);
    return best_acbg_idx;
}

/* ══════════════════════════════════════════════════════════════════════════════
 * calcGainsV
 * ══════════════════════════════════════════════════════════════════════════════ */

static float calc_gains_v(CelpEncoder *e, float fcb_wnrg, float gain_from_search,
                           const float *exc_fcb, const float *d_lpc,
                           acbg_params_t *acbg, int rate_idx,
                           int16_t acb_idx[2], int16_t fcb_idx[2]) {
    celp_tables_t *tbl = get_celp_tables();
    int fcb_subfrlen = e->fcb_subfrlen;

    float fcbgain = gain_from_search;
    if (fcbgain < 0.0f) fcbgain = 0.0f;
    float gain_db = 20.0f * log10f(fcbgain + 1e-16f);
    if (gain_db < V_GAIN_MIN_DB) gain_db = V_GAIN_MIN_DB;
    if (gain_db > V_GAIN_MAX_DB) gain_db = V_GAIN_MAX_DB;
    int32_t max_gain_idx = (int32_t)roundf((V_GAIN_MAX_DB - V_GAIN_MIN_DB) / V_GAIN_STEP_DB);

    float acb_fcb[ACBG_M];
    for (int i = 0; i < ACBG_M; i++)
        acb_fcb[i] = celp_dot_prod(acbg->acb_basis_phi + i*fcb_subfrlen, exc_fcb, fcb_subfrlen);

    int stride = ACBG_M + 1;
    float phi_all[(ACBG_M+1)*(ACBG_M+1)];
    for (int i = 0; i < ACBG_M; i++)
        for (int j = 0; j < ACBG_M; j++)
            phi_all[i*stride+j] = acbg->phi_acb[i*ACBG_M+j];
    for (int i = 0; i < ACBG_M; i++) {
        phi_all[i*stride+ACBG_M] = acb_fcb[i];
        phi_all[ACBG_M*stride+i] = acb_fcb[i];
    }
    phi_all[ACBG_M*stride+ACBG_M] = fcb_wnrg;

    float dall[ACBG_M+1];
    memcpy(dall, acbg->d_acb_lpc, ACBG_M * sizeof(float));
    dall[ACBG_M] = celp_dot_prod(d_lpc, exc_fcb, fcb_subfrlen);

    int32_t first_gain_idx = (int32_t)floorf((gain_db-V_GAIN_MIN_DB)/V_GAIN_STEP_DB) - (N_GAIN_STEPS-1)/2;
    if (first_gain_idx < 0) first_gain_idx = 0;
    if (first_gain_idx > max_gain_idx - 1) first_gain_idx = max_gain_idx - 1;

    int32_t gain_idxs[N_GAIN_STEPS];
    float fcbgains[N_GAIN_STEPS], fcbg_inv_prob[N_GAIN_STEPS];
    int32_t offset = (int32_t)floorf((V_GAIN_MIN_DB - V_GAIN_MAX_DB) / V_GAIN_STEP_DB);
    for (int i = 0; i < N_GAIN_STEPS; i++) {
        gain_idxs[i] = first_gain_idx + (int32_t)i;
        fcbgains[i] = tbl->fcbgains_v[gain_idxs[i]];
        if (e->prev_fcb_idx[rate_idx] == -1)
            fcbg_inv_prob[i] = tbl->fcbg_v_inv_prob[gain_idxs[i]];
        else {
            int32_t delta = e->prev_fcb_idx[rate_idx] - gain_idxs[i];
            int cmf_idx = (int)(delta - offset);
            fcbg_inv_prob[i] = tbl->fcbg_v_delta_inv_prob[cmf_idx];
        }
    }

    float best_rd = 1e30f; int32_t best_acbg_idx = 0, best_fcbg_idx = 0;
    int32_t transition_idx = 0;
    if (e->prev_acb_idx[rate_idx] != -1) transition_idx = e->prev_acb_idx[rate_idx] + 1;

    const int16_t *cb = e->low_rate ? cb_acbgains_lr_q14 : cb_acbgains_hr_q14;
    const float *inv_prob = (e->low_rate ? tbl->acbg_inv_prob_lr : tbl->acbg_inv_prob_hr)
                            + (int)transition_idx * ACBG_N;
    float sc_q14 = 1.0f / (float)((int32_t)1 << 14);

    for (int n = 0; n < ACBG_N; n++) {
        float gains[ACBG_M+1];
        for (int m = 0; m < ACBG_M; m++) gains[m] = (float)cb[n*ACBG_M+m] * sc_q14;
        for (int i = 0; i < N_GAIN_STEPS; i++) {
            gains[ACBG_M] = fcbgains[i];
            float werr_out = acbg->werr_in + celp_wnrg3(phi_all, gains)
                           - 2.0f*(dall[0]*gains[0]+dall[1]*gains[1]+dall[2]*gains[2]);
            float rd = werr_out * fcbg_inv_prob[i] * inv_prob[n];
            if (rd < best_rd) { best_rd = rd; best_acbg_idx = (int32_t)n; best_fcbg_idx = gain_idxs[i]; }
        }
    }

    acb_idx[rate_idx] = (int16_t)best_acbg_idx;
    fcb_idx[rate_idx] = (int16_t)best_fcbg_idx;
    if (fcb_idx[rate_idx] < 0) fcb_idx[rate_idx] = 0;
    if (fcb_idx[rate_idx] > (int16_t)max_gain_idx) fcb_idx[rate_idx] = (int16_t)max_gain_idx;
    return tbl->fcbgains_v[fcb_idx[rate_idx]];
}

/* ══════════════════════════════════════════════════════════════════════════════
 * EncodeSubframe �?MAIN FUNCTION
 * ══════════════════════════════════════════════════════════════════════════════ */

void celp_encode_subframe(CelpEncoder *e, const float *res_lpc, const float predcoef[17],
                          const float *perc_wght_resp, const float lags[2],
                          int16_t fcb_pulses_max[2], int16_t surv_in[4],
                          const float subfr_importance[2],
                          int16_t pulses_out[2][SMPL_MAX_PULSES_PER_SF_E],
                          int16_t n_pulses_out[2], int16_t acb_idx_out[2],
                          int16_t gain_idx_out[2], float *exc_lpc_out) {
    int l_resp = e->perc_resp_len;
    int fcb_subfrlen = e->fcb_subfrlen;
    bool voiced = lags[1] > 0.0f;
    (void)surv_in; /* greedy mode for now */

    /* ── Impulse response ── */
    celp_filt_ar16(perc_wght_resp, l_resp, predcoef, SMPL_LPC_ORDER, e->imp_lpc_buf);
    celp_mul_vec_inplace(e->hanning_win, e->imp_lpc_buf + SMPL_LPC_ORDER, l_resp);

    /* Build phi (auto-correlation of impulse response) */
    {
        float imp_lpc_rev[2*SMPL_MAX_L_RESP_E-1];
        int rev_base = SMPL_MAX_L_RESP_E - 1;
        memset(imp_lpc_rev, 0, sizeof(imp_lpc_rev));
        const float *imp = e->imp_lpc_buf + SMPL_LPC_ORDER;
        for (int i = 0; i < l_resp; i++) imp_lpc_rev[rev_base+i] = imp[l_resp-i-1];

        float phi[SMPL_MAX_SF_LEN_E];
        perc_filt_ma(e, imp_lpc_rev, rev_base, l_resp, imp, l_resp, phi);
        celp_reverse(phi, l_resp);
        for (int i = l_resp; i < fcb_subfrlen; i++) phi[i] = 0.0f;
        memcpy(e->phi, phi, fcb_subfrlen * sizeof(float));
    }

    /* Build phi_flip */
    memset(e->phi_flip, 0, 2 * SMPL_MAX_SF_LEN_E * sizeof(float));
    e->phi_flip[SMPL_MAX_SF_LEN_E] = e->phi[0];
    for (int i = 0; i < l_resp + 1; i++) {
        e->phi_flip[SMPL_MAX_SF_LEN_E - i] = e->phi[i];
        e->phi_flip[SMPL_MAX_SF_LEN_E + i] = e->phi[i];
    }

    /* ── dLpc ── */
    /* res_lpc_pad pre-allocated in e->res_lpc_pad */
    memset(e->res_lpc_pad, 0, (fcb_subfrlen + l_resp + 1) * sizeof(float));
    memcpy(e->res_lpc_pad, res_lpc, fcb_subfrlen * sizeof(float));
    float d_lpc[SMPL_MAX_SF_LEN_E];
    {
        int c_off = SMPL_MAX_SF_LEN_E - l_resp + 1;
        celp_mult_symtoepl2(e->phi_flip + c_off, l_resp, e->res_lpc_pad, d_lpc, fcb_subfrlen);
    }

    /* ── ZIR (zero-input response) ── */
    acbg_params_t acbg;
    acbg.acb_basis_phi = e->acb_basis_phi;  /* pre-allocated */
    float zir_lpc[SMPL_MAX_SF_LEN_E];
    memset(zir_lpc, 0, sizeof(zir_lpc));

    if (!e->ignore_zir) {
        float zir_tmp[SMPL_MAX_SF_LEN_E + SMPL_MAX_L_RESP_E - 1];
        memset(zir_tmp, 0, sizeof(zir_tmp));
        int zt = SMPL_MAX_L_RESP_E - 1;
        int state_len = SMPL_LPC_ORDER;
        if (l_resp - 1 > state_len) state_len = l_resp - 1;
        for (int i = 0; i < state_len; i++)
            zir_tmp[zt-state_len+i] = e->state_wght_buf[SMPL_LPC_ORDER+(fcb_subfrlen-state_len)+i];

        for (int nn = 0; nn < l_resp; nn++) {
            float res = zir_tmp[zt+nn];
            for (int i = 0; i < 16; i++) res -= predcoef[16-i] * zir_tmp[zt+nn-16+i];
            zir_tmp[zt+nn] = res;
        }
        perc_filt_ma(e, zir_tmp, zt, l_resp, perc_wght_resp, l_resp, zir_lpc);

        float ht_zir[2*SMPL_MAX_L_RESP_E-1];
        memset(ht_zir, 0, sizeof(ht_zir));
        int ht = SMPL_MAX_L_RESP_E - 1;

        for (int i = 0; i < l_resp; i++) zir_tmp[zt+i] = zir_lpc[l_resp-i-1];
        for (int i = 0; i < l_resp - 1; i++) zir_tmp[zt-(l_resp-1)+i] = 0.0f;
        {
            const float *imp = e->imp_lpc_buf + SMPL_LPC_ORDER;
            perc_filt_ma(e, zir_tmp, zt, l_resp, imp, l_resp, ht_zir + ht);
        }
        celp_reverse(ht_zir + ht, l_resp);

        if (voiced)
            acbg.werr_in = celp_dot_prod(d_lpc, res_lpc, fcb_subfrlen)
                         + 2.0f*celp_dot_prod(ht_zir+ht, res_lpc, l_resp)
                         + celp_nrg(zir_lpc, l_resp);
        for (int i = 0; i < l_resp; i++) d_lpc[i] += ht_zir[ht+i];
    } else {
        if (voiced) acbg.werr_in = celp_dot_prod(d_lpc, res_lpc, fcb_subfrlen);
    }

    /* ── ACB basis + ACB gain search (voiced only) ── */
    float *acb_basis = e->acb_basis;  /* pre-allocated */
    float acb[SMPL_MAX_SF_LEN_E];
    float d_ltp[SMPL_MAX_SF_LEN_E];
    int16_t acb_idx[2] = {-1, -1};

    if (voiced) {
        celp_syn_ltp_basis(lags, fcb_subfrlen/CELP_LAG_SUBFR_LEN, e->acb_state, e->acb_state_len, acb_basis);
        int32_t idx = calc_acb_gain(e, l_resp, acb_basis, d_lpc, &acbg, d_ltp);
        acb_idx[1] = (int16_t)idx;
        float acb_gain[ACBG_M];
        celp_acb_dequant(e->low_rate, (int32_t)acb_idx[1], acb_gain);
        celp_acb_synthesize(fcb_subfrlen, acb_basis, acb_gain, acb);
        acb_idx[0] = acb_idx[1];
    }

    /* ── Weighted target for FCB search ── */
    float wtgt_tmp[SMPL_MAX_SF_LEN_E + 2*SMPL_MAX_L_RESP_E - 1];
    memset(wtgt_tmp, 0, sizeof(wtgt_tmp));
    int wt = SMPL_MAX_L_RESP_E - 1;
    memcpy(wtgt_tmp + wt, res_lpc, fcb_subfrlen * sizeof(float));
    if (voiced) {
        for (int i = 0; i < fcb_subfrlen; i++) wtgt_tmp[wt+i] += -RATE_ACB_SCALE * acb[i];
    }
    float wtgt[SMPL_MAX_SF_LEN_E + SMPL_MAX_L_RESP_E];
    {
        const float *imp = e->imp_lpc_buf + SMPL_LPC_ORDER;
        perc_filt_ma(e, wtgt_tmp, wt, fcb_subfrlen+l_resp, imp, l_resp, wtgt);
    }
    for (int i = 0; i < l_resp; i++) wtgt[i] += zir_lpc[i];

    float nrg_wtgt = celp_nrg(wtgt, fcb_subfrlen + l_resp);
    float wnrg_per_pulse[2];
    for (int r = 0; r < 2; r++)
        wnrg_per_pulse[r] = nrg_wtgt / (subfr_importance[r] + 1e-3f);

    int32_t i_lag = (int32_t)lags[(fcb_subfrlen/CELP_LAG_SUBFR_LEN)-1];

    /* ── FCB search ── */
    int16_t n_pulses[2] = {0, 0};
    float gain_from_search[2] = {0, 0};
    float fcb_wnrg[2] = {0, 0};
    float wnrg[2] = {0, 0};
    int16_t pulses[2][SMPL_MAX_PULSES_PER_SF_E];
    memset(pulses, 0, sizeof(pulses));

    if (fcb_pulses_max[1] > 0) {
        const float *target = voiced ? d_ltp : d_lpc;
        smpl_fcb_search(e, target, wnrg_per_pulse, fcb_pulses_max,
                        pulses, n_pulses, wnrg, gain_from_search, fcb_wnrg);
    }

    /* ── Gain quantization ── */
    int16_t gain_idx[2] = {-1, -1};
    float fcbgain_val = 0.0f;
    float exc_fcb[SMPL_MAX_SF_LEN_E];
    celp_tables_t *tbl = get_celp_tables();

    for (int r = 0; r < 2; r++) {
        float exc_fcb_raw[SMPL_MAX_SF_LEN_E];
        celp_fcb_synthesize(fcb_subfrlen, pulses[r], (int)n_pulses[r], exc_fcb_raw);
        memcpy(exc_fcb, exc_fcb_raw, fcb_subfrlen * sizeof(float));

        if (n_pulses[r] > 0) {
            if (voiced) {
                if (e->low_rate) celp_pitch_sharp(exc_fcb, (int)i_lag, fcb_subfrlen);
                fcbgain_val = calc_gains_v(e, fcb_wnrg[r], gain_from_search[r],
                                           exc_fcb, d_lpc, &acbg, r, acb_idx, gain_idx);
            } else {
                gain_idx[r] = celp_quant_gain_uv(gain_from_search[r]);
                fcbgain_val = fcbgains_uv_tbl[gain_idx[r]];
            }
            celp_scale_vec_inplace(exc_fcb, fcb_subfrlen, fcbgain_val);
        }
    }

    /* ── Excitation = FCB + ACB ── */
    float exc_lpc[SMPL_MAX_SF_LEN_E];
    memcpy(exc_lpc, exc_fcb, fcb_subfrlen * sizeof(float));
    if (voiced) {
        float acb_gain[ACBG_M];
        celp_acb_dequant(e->low_rate, (int32_t)acb_idx[1], acb_gain);
        celp_acb_synthesize(fcb_subfrlen, acb_basis, acb_gain, acb);
        celp_add_vec_inplace(acb, exc_lpc, fcb_subfrlen);
    }

    /* ── Update ACB state ── */
    memmove(e->acb_state, e->acb_state + fcb_subfrlen,
            (e->acb_state_len - fcb_subfrlen) * sizeof(float));
    int write_off = e->acb_state_len - 2*fcb_subfrlen;
    memcpy(e->acb_state + write_off, exc_lpc, fcb_subfrlen * sizeof(float));

    /* ── Update ZIR state ── */
    if (!e->ignore_zir) {
        float lpc_res_err[SMPL_MAX_SF_LEN_E];
        celp_sub_vec(res_lpc, exc_lpc, lpc_res_err, fcb_subfrlen);
        for (int i = 0; i < SMPL_LPC_ORDER; i++)
            e->state_wght_buf[i] = e->state_err_lpc_syn[i];
        celp_filt_ar16(lpc_res_err, fcb_subfrlen, predcoef, SMPL_LPC_ORDER, e->state_wght_buf);
        for (int i = 0; i < SMPL_LPC_ORDER; i++)
            e->state_err_lpc_syn[i] = e->state_wght_buf[SMPL_LPC_ORDER+(fcb_subfrlen-SMPL_LPC_ORDER)+i];
    }

    /* ── Update prev_acb_idx / prev_fcb_idx ── */
    e->subfr_cnt++;
    if (e->subfr_cnt == e->subfr_per_packet) {
        for (int r = 0; r < 2; r++) { e->prev_acb_idx[r] = -1; e->prev_fcb_idx[r] = -1; }
        e->subfr_cnt = 0;
    } else {
        for (int r = 0; r < 2; r++) {
            if (voiced) { e->prev_acb_idx[r] = (int32_t)acb_idx[r]; e->prev_fcb_idx[r] = (int32_t)gain_idx[r]; }
            else { e->prev_acb_idx[r] = -1; e->prev_fcb_idx[r] = -1; }
        }
    }
    e->fcbgain = fcbgain_val;

    /* ── Output ── */
    for (int r = 0; r < 2; r++) {
        int n = (int)n_pulses[r]; if (n < 0) n = 0;
        memcpy(pulses_out[r], pulses[r], n * sizeof(int16_t));
        n_pulses_out[r] = (int16_t)n;
    }
    acb_idx_out[0] = acb_idx[0]; acb_idx_out[1] = acb_idx[1];
    gain_idx_out[0] = gain_idx[0]; gain_idx_out[1] = gain_idx[1];
    memcpy(exc_lpc_out, exc_lpc, fcb_subfrlen * sizeof(float));

    /* No frees needed �?all scratch pre-allocated in CelpEncoder */
}

/* ══════════════════════════════════════════════════════════════════════════════
 * NewCelpEncoder / celp_encoder_free
 * ══════════════════════════════════════════════════════════════════════════════ */

CelpEncoder *celp_encoder_new(bool low_rate, int perc_resp_len, int fcb_subfrlen, int subfr_per_packet) {
    build_celp_tables();
    int acb_state_len = fcb_subfrlen + CELP_MAX_PITCH_LEN + CELP_LTP_INTERPOL_DELAY;

    CelpEncoder *e = (CelpEncoder *)calloc(1, sizeof(CelpEncoder));
    if (!e) return NULL;

    e->state_wght_buf = (float *)calloc(SMPL_MAX_SF_LEN_E + SMPL_LPC_ORDER, sizeof(float));
    e->acb_state = (float *)calloc(CELP_MAX_PITCH_LAG + SMPL_MAX_SF_LEN_E + CELP_LTP_INTERPOL_DELAY, sizeof(float));
    e->imp_lpc_buf = (float *)calloc(SMPL_MAX_SF_LEN_E + SMPL_LPC_ORDER, sizeof(float));
    e->phi = (float *)calloc(SMPL_MAX_SF_LEN_E, sizeof(float));
    e->phi_flip = (float *)calloc(2 * SMPL_MAX_SF_LEN_E, sizeof(float));

    e->acb_state_len = acb_state_len;
    e->prev_acb_idx[0] = e->prev_acb_idx[1] = -1;
    e->prev_fcb_idx[0] = e->prev_fcb_idx[1] = -1;
    e->subfr_per_packet = (int32_t)subfr_per_packet;
    e->fcb_subfrlen = fcb_subfrlen;
    e->perc_resp_len = perc_resp_len;
    e->low_rate = low_rate;
    e->use_ma9 = (perc_resp_len == 10);

    /* sgntrs: LCG-based hash */
    uint64_t s = 0x9E3779B97F4A7C15ULL;
    for (int i = 0; i < SMPL_MAX_SF_LEN_E; i++) {
        s = s * 6364136223846793005ULL + 1442695040888963407ULL;
        e->sgntrs[i] = s;
    }

    /* hanningWin: sine-based window */
    float scale = 1.0f / (float)(2*SMPL_PERC_R_LEN+1);
    for (int i = 0; i < perc_resp_len; i++)
        e->hanning_win[i] = sinf(SMPL_PI_F32 * (float)(perc_resp_len+i+1) * scale);

    return e;
}

void celp_encoder_free(CelpEncoder *e) {
    if (!e) return;
    free(e->state_wght_buf);
    free(e->acb_state);
    free(e->imp_lpc_buf);
    free(e->phi);
    free(e->phi_flip);
    free(e);
}
