/*
 * lpc.c — LPC analysis: window → FFT-autocorr → A/NLSF.
 */
#include "encode.h"
#include "../seed.h"
#include <math.h>
#include <string.h>
#include <stdlib.h>

static const double smpl_pi_f64 = (double)(float)(3.1415926535897);
static const float smpl_pi = 3.1415926535897f;
static const float smpl_lpc_reg = 5e-7f;
static const float smpl_lpc_bwe = 0.9999f;
static const int   smpl_lpc_win120ms_len = 264;
static const int   smpl_win3_long_len = 64;
static const int   smpl_win3_short_len = 32;
static const int   smpl_subfrs = 4;
static const float max_rc_stable = 0.9995f;

static const int lsf_cos_tab_sz_fix = 128;
static const int bin_div_steps_a2nlsf_fix = 3;
static const int max_iterations_a2nlsf_fix = 16;
static const int silk_int16_max = 32767;

/* silkLSFCosTabFIXQ12 */
extern const int32_t silk_lsf_cos_tab_fix_q12[];

static const float smpl_lsf_interpol4_tbl[2][4] = {
    {0.55f, 0.88f, 1.0f, 1.0f},
    {0.3f, 0.65f, 0.95f, 1.0f},
};

/* ── Window generation ──────────────────────────────────────────────────────── */
static void gen_sin_win(int n, float *w) {
    for (int i = 0; i < n; i++) {
        float t = ((float)i + 1.0f) / ((float)n + 1.0f) * smpl_pi / 2.0f;
        w[i] = mlow_sinf32(t);
    }
}
static void gen_cos_win(int n, float *w) {
    for (int i = 0; i < n; i++) {
        float t = ((float)i + 1.0f) / ((float)n + 1.0f) * smpl_pi / 2.0f;
        w[i] = mlow_cosf32(t);
    }
}

void smpl_window_lpc20(const float *input, bool use_long_win, float *out) {
    float win1[264];
    gen_sin_win(smpl_lpc_win120ms_len, win1);
    float win3[64];
    int win3len;
    if (use_long_win) { gen_cos_win(smpl_win3_long_len, win3); win3len = smpl_win3_long_len; }
    else              { gen_cos_win(smpl_win3_short_len, win3); win3len = smpl_win3_short_len; }

    for (int i = 0; i < smpl_lpc_win120ms_len; i++) out[i] = input[i] * win1[i];
    int mid = SMPL_LPC_BUF_LEN - smpl_lpc_win120ms_len - smpl_win3_long_len;
    for (int i = 0; i < mid; i++) out[smpl_lpc_win120ms_len + i] = input[smpl_lpc_win120ms_len + i];
    int base = SMPL_LPC_BUF_LEN - smpl_win3_long_len;
    for (int i = 0; i < win3len; i++) out[base + i] = input[base + i] * win3[i];
    if (!use_long_win) {
        for (int s = base + smpl_win3_short_len; s < base + smpl_win3_long_len; s++) out[s] = 0.0f;
    }
}

/* ── DCT tables ──────────────────────────────────────────────────────────────── */
static void gen_cos_row(double domega, double scale, double *row) {
    double omega = 0.0;
    double two_pi = 2.0 * smpl_pi_f64;
    for (int k = 0; k < NFFT4; k++) {
        row[k] = cos(omega) * scale;
        omega = fmod(omega + domega, two_pi);
        if (omega < 0) omega += two_pi;
    }
}

typedef struct {
    double cdif[8][NFFT4];
    double csumdiff[4][NFFT4];
    double csumsum[4][NFFT4];
} dct_tables_t;

static void build_dct_tables(dct_tables_t *t) {
    double two_pi = 2.0 * smpl_pi_f64;
    double nfft = (double)SMPL_LPC_NFFT;
    for (int j = 0; j < SMPL_LPC_ORDER/2; j++)
        gen_cos_row((double)(1 + j*2) * two_pi / nfft, 2.0 / nfft, t->cdif[j]);
    for (int j = 0; j < SMPL_LPC_ORDER/4; j++)
        gen_cos_row((double)(2 + j*4) * two_pi / nfft, 1.0 / nfft, t->csumdiff[j]);
    for (int j = 0; j < SMPL_LPC_ORDER/4; j++)
        gen_cos_row((double)(4 + j*4) * two_pi / nfft, 1.0 / nfft, t->csumsum[j]);
}

static void brute_dct(const dct_tables_t *t, const double *f2, int order, double *r) {
    int half = SMPL_LPC_NFFT / 2;
    double f2sum = 0.0;
    double f2dif[NFFT4], f2sumsum[NFFT4], f2sumdif[NFFT4];
    for (int n = 0; n < NFFT4; n++) {
        f2sum += f2[n] + f2[NFFT4 + n];
        f2dif[n] = f2[n] - f2[half - n];
        f2sumsum[n] = f2[n] + f2[half - n] + f2[NFFT4 + n] + f2[NFFT4 - n];
        f2sumdif[n] = f2[n] + f2[half - n] - f2[NFFT4 + n] - f2[NFFT4 - n];
    }
    f2dif[0] *= 0.5;
    r[0] = (2.0 * f2sum - f2[0] + f2[half]) / (double)SMPL_LPC_NFFT;
    for (int j = 0; j < order/2; j++) {
        double rtmp = 0.0; const double *row = t->cdif[j];
        for (int k = 0; k < NFFT4; k++) rtmp += row[k] * f2dif[k];
        r[1 + j*2] = rtmp;
    }
    for (int j = 0; j < order/4; j++) {
        double rtmp = 0.0; const double *row = t->csumdiff[j];
        for (int k = 0; k < NFFT4; k++) rtmp += row[k] * f2sumdif[k];
        r[2 + j*4] = rtmp;
    }
    for (int j = 0; j < order/4; j++) {
        double rtmp = 0.0; const double *row = t->csumsum[j];
        for (int k = 0; k < NFFT4; k++) rtmp += row[k] * f2sumsum[k];
        r[4 + j*4] = rtmp;
    }
}

static void ac2rc_dbl(const double *corr, int order, float reg, float *rc) {
    double *c0 = (double *)calloc(order + 1, sizeof(double));
    double *c1 = (double *)calloc(order + 1, sizeof(double));
    for (int i = 0; i <= order; i++) c0[i] = corr[i];
    c0[0] *= (double)(1.0f + reg);
    memcpy(c1, c0, (order + 1) * sizeof(double));
    for (int i = 0; i < order; i++) rc[i] = 0.0f;
    for (int k = 0; k < order; k++) {
        if (c0[k+1] > c1[0]) { rc[k] = -1.0f; break; }
        if (c0[k+1] < -c1[0]) { rc[k] = 1.0f; break; }
        if (c1[0] == 0.0) break;
        double rc_tmp = -c0[k+1] / c1[0];
        rc[k] = (float)rc_tmp;
        for (int n = 0; n < order - k; n++) {
            double ctmp1 = c0[n + k + 1], ctmp2 = c1[n];
            c0[n + k + 1] = ctmp1 + ctmp2 * rc_tmp;
            c1[n] = ctmp2 + ctmp1 * rc_tmp;
        }
    }
    free(c0); free(c1);
}

static void rc2a(const float *rc, int order, float *a) {
    for (int i = 1; i < order + 1; i++) a[i] = 0.0f;
    a[0] = 1.0f;
    for (int k = 0; k < order; k++) {
        float rc_tmp = rc[k];
        for (int n = 0; n < (k+1)/2; n++) {
            float tmp1 = a[n+1], tmp2 = a[k-n];
            a[n+1] = tmp1 + tmp2 * rc_tmp;
            a[k-n] = tmp2 + tmp1 * rc_tmp;
        }
        a[k+1] = rc_tmp;
    }
}

static void bwe_expand(float *a, int order, float bwe) {
    float c = bwe;
    for (int i = 1; i < order + 1; i++) { a[i] *= c; c *= bwe; }
}

void smpl_lpc_analyze_with_f2(const float *windowed, float *a, float *f2) {
    float xbuf[SMPL_LPC_NFFT];
    memset(xbuf, 0, sizeof(xbuf));
    memcpy(xbuf, windowed, SMPL_LPC_BUF_LEN * sizeof(float));

    float f[SMPL_LPC_NFFT];
    rfft_forward_ordered(xbuf, SMPL_LPC_NFFT, f);

    double f2d[SMPL_F_LEN];
    f2[0] = f[0] * f[0];
    f2[SMPL_LPC_NFFT/2] = f[1] * f[1];
    f2d[0] = (double)f2[0];
    f2d[SMPL_LPC_NFFT/2] = (double)f2[SMPL_LPC_NFFT/2];
    for (int i = 1; i < SMPL_LPC_NFFT/2; i++) {
        f2[i] = f[2*i] * f[2*i] + f[2*i+1] * f[2*i+1];
        f2d[i] = (double)f2[i];
    }

    dct_tables_t tables;
    build_dct_tables(&tables);
    double r[SMPL_LPC_ORDER + 1];
    brute_dct(&tables, f2d, SMPL_LPC_ORDER, r);

    float rc[SMPL_LPC_ORDER];
    ac2rc_dbl(r, SMPL_LPC_ORDER, smpl_lpc_reg, rc);
    rc2a(rc, SMPL_LPC_ORDER, a);
    a[0] = 1.0f;
    bwe_expand(a, SMPL_LPC_ORDER, smpl_lpc_bwe);
}

/* ── LPC stability + interpol ───────────────────────────────────────────────── */
static bool lpc_is_stable(const float *a) {
    int order = SMPL_LPC_ORDER;
    if (a[order] * a[order] > max_rc_stable) return false;
    double a0[SMPL_LPC_ORDER], a1[SMPL_LPC_ORDER];
    for (int i = 0; i < order; i++) a0[i] = (double)a[i+1];
    int m = order - 1;
    for (;;) {
        double den = 1.0 - a0[m] * a0[m];
        if (den == 0.0) return false;
        double inv = 1.0 / den;
        for (int k = 0; k < m; k++) a1[k] = (a0[k] - a0[m] * a0[m - k - 1]) * inv;
        if (a1[m-1] * a1[m-1] > (double)max_rc_stable) return false;
        if (m == 1) return true;
        m--;
        den = 1.0 - a1[m] * a1[m];
        if (den == 0.0) return false;
        inv = 1.0 / den;
        for (int k = 0; k < m; k++) a0[k] = (a1[k] - a1[m] * a1[m - k - 1]) * inv;
        if (a0[m-1] * a0[m-1] > (double)max_rc_stable) return false;
        if (m == 1) return true;
        m--;
    }
}

static void lpc_stabilize(float *a) {
    if (lpc_is_stable(a)) return;
    for (int iter = 1; ; iter++) {
        bwe_expand(a, SMPL_LPC_ORDER, 1.0f - (float)iter * 0.001f);
        if (lpc_is_stable(a)) return;
    }
}

void smpl_lpc_interpol(const float *lsf, const float *prev_lsf, int interpol_idx,
                       float predcoefs[4][17], float *ilsf_out) {
    const float *interp = smpl_lsf_interpol4_tbl[interpol_idx > 1 ? 1 : interpol_idx];
    float prev[16];
    if (prev_lsf[15] != 0.0f) memcpy(prev, prev_lsf, 16 * sizeof(float));
    else memcpy(prev, lsf, 16 * sizeof(float));

    float ilsf[16];
    for (int j = 0; j < smpl_subfrs; j++) {
        float w = interp[j];
        if (w == 1.0f) memcpy(ilsf, lsf, 16 * sizeof(float));
        else for (int k = 0; k < 16; k++) ilsf[k] = (1.0f - w) * prev[k] + w * lsf[k];

        float a_int[17];
        smpl_nlsf2a(a_int, ilsf, SMPL_LPC_ORDER);
        a_int[0] = 1.0f;
        lpc_stabilize(a_int);
        memcpy(predcoefs[j], a_int, 17 * sizeof(float));
    }
    memcpy(ilsf_out, ilsf, 16 * sizeof(float));
}

/* ── silkA2NLSF ──────────────────────────────────────────────────────────────── */
static int32_t silk_rshift_round(int32_t a, int shift) {
    if (shift == 1) return (a >> 1) + (a & 1);
    return ((a >> (shift - 1)) + 1) >> 1;
}

static int32_t silk_smlaww(int32_t a32, int32_t b32, int32_t c32) {
    return (int32_t)((int64_t)a32 + (((int64_t)b32 * (int64_t)c32) >> 16));
}

static void silk_bwexpander32(int32_t *ar, int d, int32_t chirpQ16) {
    int32_t chirp = chirpQ16;
    int32_t chirp_minus_one = chirpQ16 - 65536;
    for (int i = 0; i < d - 1; i++) {
        ar[i] = (int32_t)(((int64_t)chirp * (int64_t)ar[i]) >> 16);
        int32_t mul = chirp * chirp_minus_one;
        chirp += silk_rshift_round(mul, 16);
    }
    ar[d-1] = (int32_t)(((int64_t)chirp * (int64_t)ar[d-1]) >> 16);
}

static void silk_a2nlsf_trans_poly(int32_t *p, int dd) {
    for (int k = 2; k <= dd; k++) {
        for (int n = dd; n >= k + 1; n--) p[n-2] -= p[n];
        p[k-2] -= p[k] << 1;
    }
}

static int32_t silk_a2nlsf_eval_poly(const int32_t *p, int32_t x, int dd) {
    int32_t xQ16 = x << 4;
    int32_t y32 = p[dd];
    for (int n = dd - 1; n >= 0; n--) y32 = silk_smlaww(p[n], y32, xQ16);
    return y32;
}

static void silk_a2nlsf_init(const int32_t *aQ16, int32_t *p, int32_t *q, int dd) {
    p[dd] = 1 << 16;
    q[dd] = 1 << 16;
    for (int k = 0; k < dd; k++) {
        p[k] = -aQ16[dd - k - 1] - aQ16[dd + k];
        q[k] = -aQ16[dd - k - 1] + aQ16[dd + k];
    }
    for (int k = dd; k >= 1; k--) { p[k-1] -= p[k]; q[k-1] += q[k]; }
    silk_a2nlsf_trans_poly(p, dd);
    silk_a2nlsf_trans_poly(q, dd);
}

static void silk_a2nlsf(int32_t *nlsf, int32_t *aQ16, int d) {
    int dd = d >> 1;
    int32_t *p = (int32_t *)calloc(dd + 1, sizeof(int32_t));
    int32_t *q = (int32_t *)calloc(dd + 1, sizeof(int32_t));
    silk_a2nlsf_init(aQ16, p, q, dd);

    bool use_q = false;
    #define POLY() (use_q ? q : p)

    int32_t xlo = silk_lsf_cos_tab_fix_q12[0];
    int32_t ylo = silk_a2nlsf_eval_poly(POLY(), xlo, dd);

    int root_ix = 0;
    if (ylo < 0) { nlsf[0] = 0; use_q = true; ylo = silk_a2nlsf_eval_poly(q, xlo, dd); root_ix = 1; }
    int k = 1;
    int32_t thr = 0;
    int iter = 0;
    for (;;) {
        int32_t xhi = silk_lsf_cos_tab_fix_q12[k];
        int32_t yhi = silk_a2nlsf_eval_poly(POLY(), xhi, dd);

        if ((ylo <= 0 && yhi >= thr) || (ylo >= 0 && yhi <= -thr)) {
            thr = (yhi == 0) ? 1 : 0;
            int32_t xloL = xlo, yloL = ylo, xhiL = xhi;
            int32_t ffrac = -256;
            for (int m = 0; m < bin_div_steps_a2nlsf_fix; m++) {
                int32_t xmid = silk_rshift_round(xloL + xhiL, 1);
                int32_t ymid = silk_a2nlsf_eval_poly(POLY(), xmid, dd);
                if ((yloL <= 0 && ymid >= 0) || (yloL >= 0 && ymid <= 0)) {
                    xhiL = xmid; yhi = ymid;
                } else {
                    xloL = xmid; yloL = ymid;
                    ffrac += 128 >> m;
                }
            }
            int32_t abs_yloL = yloL < 0 ? -yloL : yloL;
            if (abs_yloL < 65536) {
                int32_t den = yloL - yhi;
                int32_t nom = (yloL << (8 - bin_div_steps_a2nlsf_fix)) + (den >> 1);
                ffrac += (den != 0) ? nom / den : 0;
            } else {
                ffrac += yloL / ((yloL - yhi) >> (8 - bin_div_steps_a2nlsf_fix));
            }
            int32_t val = ((int32_t)k << 8) + ffrac;
            nlsf[root_ix] = val < silk_int16_max ? val : silk_int16_max;

            root_ix++;
            if (root_ix >= d) break;
            use_q = (root_ix & 1) != 0;
            xlo = silk_lsf_cos_tab_fix_q12[k - 1];
            ylo = (1 - (root_ix & 2)) << 12;
        } else {
            k++;
            xlo = xhi; ylo = yhi; thr = 0;
            if (k > lsf_cos_tab_sz_fix) {
                iter++;
                if (iter > max_iterations_a2nlsf_fix) {
                    nlsf[0] = (1 << 15) / (d + 1);
                    for (int kk = 1; kk < d; kk++) nlsf[kk] = nlsf[kk-1] + nlsf[0];
                    free(p); free(q); return;
                }
                silk_bwexpander32(aQ16, d, 65536 - (1 << iter));
                silk_a2nlsf_init(aQ16, p, q, dd);
                use_q = false;
                xlo = silk_lsf_cos_tab_fix_q12[0];
                ylo = silk_a2nlsf_eval_poly(p, xlo, dd);
                if (ylo < 0) { nlsf[0] = 0; use_q = true; ylo = silk_a2nlsf_eval_poly(q, xlo, dd); root_ix = 1; }
                else root_ix = 0;
                k = 1;
            }
        }
    }
    free(p); free(q);
}

void smpl_a2nlsf16(const float *a, float *nlsf) {
    int32_t aQ16[SMPL_LPC_ORDER];
    for (int i = 0; i < SMPL_LPC_ORDER; i++)
        aQ16[i] = (int32_t)round((double)(-a[i+1] * 65536.0f));
    int32_t lsfQ15[SMPL_LPC_ORDER];
    silk_a2nlsf(lsfQ15, aQ16, SMPL_LPC_ORDER);
    for (int i = 0; i < SMPL_LPC_ORDER; i++)
        nlsf[i] = (float)lsfQ15[i] / 32768.0f * smpl_pi;
}