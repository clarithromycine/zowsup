/*
 * perc.c �?Perceptual weighting model.
 */
#include "encode.h"
#include "../seed.h"
#include <math.h>
#include <string.h>
#include <stdlib.h>

#define PERCW_NFFT        576
#define PERC_MASK_SMTH    0.1158f
#define PERC_MEL_FC_HZ    320.0f
#define WIN_NEXT_WB_LEN   32
#define WIN_NEXT_WB_LONG  64
#define WIN_PREV_PERC_LEN 192
#define PERC_WIN_110MS    192
#define PERC_WIN_120MS    352
#define SMPL_MAX_L_RESP   33

typedef struct {
    float buf[PERCW_NFFT];
    float smth_coef[PERCW_NFFT / 2 + 1];
    float perc_win_110ms[PERC_WIN_110MS];
    float perc_win_120ms[PERC_WIN_120MS];
    float win3_short[WIN_NEXT_WB_LEN];
    float win3_long[WIN_NEXT_WB_LONG];
    bool  windows_built;
    /* Pre-allocated FFT scratch (eliminates 3 calloc/free per call) */
    float fft_bw[PERCW_NFFT];
    float fft_f[PERCW_NFFT];
    float fft_time[PERCW_NFFT];
} PercModelState;

static void build_windows(PercModelState *s) {
    if (s->windows_built) return;
    for (int i = 0; i < PERC_WIN_110MS; i++)
        s->perc_win_110ms[i] = mlow_sinf32((float)(i+1)/(float)(PERC_WIN_110MS+1)*1.570796f);
    for (int i = 0; i < PERC_WIN_120MS; i++)
        s->perc_win_120ms[i] = mlow_sinf32((float)(i+1)/(float)(PERC_WIN_120MS+1)*1.570796f);
    for (int i = 0; i < WIN_NEXT_WB_LEN; i++)
        s->win3_short[i] = mlow_cosf32((float)(i+1)/(float)(WIN_NEXT_WB_LEN+1)*1.570796f);
    for (int i = 0; i < WIN_NEXT_WB_LONG; i++)
        s->win3_long[i] = mlow_cosf32((float)(i+1)/(float)(WIN_NEXT_WB_LONG+1)*1.570796f);
    s->windows_built = true;
}

void *perc_model_new(void) {
    PercModelState *s = calloc(1, sizeof(PercModelState));
    if (!s) return NULL;
    float fs_step = (16.0f * 1000.0f) / (float)PERCW_NFFT;
    for (int i = 0; i < PERCW_NFFT / 2 + 1; i++) {
        float pw = PERC_MASK_SMTH * (fs_step*(float)i + PERC_MEL_FC_HZ) / fs_step;
        s->smth_coef[i] = pw / (pw + 1.0f);
    }
    build_windows(s);
    return s;
}

void perc_model_free(void *p) { if (p) free(p); }

static void perc_win(const PercModelState *s, const float *in, float *out,
                     int len, int frame_ms, bool use_long) {
    int w1len = PERC_WIN_120MS;
    const float *w1 = s->perc_win_120ms;
    if (frame_ms == 10) { w1len = PERC_WIN_110MS; w1 = s->perc_win_110ms; }
    int w3len = WIN_NEXT_WB_LEN;
    const float *w3 = s->win3_short;
    if (use_long) { w3len = WIN_NEXT_WB_LONG; w3 = s->win3_long; }
    for (int i = 0; i < w1len; i++) out[i] = w1[i] * in[i];
    int mid = len - w1len - WIN_NEXT_WB_LONG;
    memcpy(out + w1len, in + w1len, mid * sizeof(float));
    int base = len - WIN_NEXT_WB_LONG;
    for (int i = 0; i < w3len; i++) out[base+i] = w3[i] * in[base+i];
    if (!use_long)
        for (int i = base+WIN_NEXT_WB_LEN; i < len; i++) out[i] = 0.0f;
}

static void ac2rc_dbl(const double *c, int order, double reg, float *rc) {
    /* Stack arrays �?order �?32, avoids 2 calloc/free per call */
    double c0[SMPL_MAX_L_RESP];
    double c1[SMPL_MAX_L_RESP];
    for (int i = 0; i < order+1; i++) c0[i] = c[i];
    c0[0] *= 1.0 + reg;
    memcpy(c1, c0, (order+1)*sizeof(double));
    for (int i = 0; i < order; i++) rc[i] = 0.0f;
    for (int k = 0; k < order; k++) {
        if (c0[k+1] > c1[0]) { rc[k] = -1.0f; break; }
        if (c0[k+1] < -c1[0]) { rc[k] = 1.0f; break; }
        if (c1[0] == 0.0) break;
        double rt = -c0[k+1] / c1[0];
        rc[k] = (float)rt;
        for (int n = 0; n < order - k; n++) {
            double a = c0[n+k+1], b = c1[n];
            c0[n+k+1] = a + b*rt;
            c1[n] = b + a*rt;
        }
    }
}

static void rc2a(const float *rc, int order, float *a) {
    for (int v = 1; v <= order; v++) a[v] = 0.0f;
    a[0] = 1.0f;
    for (int k = 0; k < order; k++) {
        float rt = rc[k];
        for (int n = 0; n < (k+1)/2; n++) {
            float t1 = a[n+1], t2 = a[k-n];
            a[n+1] = t1 + t2*rt;
            a[k-n] = t2 + t1*rt;
        }
        a[k+1] = rt;
    }
}

static void smth_filt(float *f, const float *sc) {
    int half = PERCW_NFFT / 2;
    float fs = f[0];
    for (int i = 1; i < half; i++) {
        float fn = f[2*i];
        fs = fn + sc[i]*(fs - fn);
        f[2*i] = fs;
    }
    f[1] += sc[half]*(fs - f[1]);
    fs = f[1];
    for (int i = half-1; i > 0; i--) {
        float fn = f[2*i];
        fs = fn + sc[i]*(fs - fn);
        f[2*i] = fs;
    }
    f[0] += sc[0]*(fs - f[0]);
}

static void filt_ma2(const float *x, int n, const float coef[3], float st[2], float *y) {
    for (int i = 0; i < n; i++) y[i] = coef[0]*x[i];
    for (int i = 1; i < n; i++) y[i] += coef[1]*x[i-1];
    for (int i = 2; i < n; i++) y[i] += coef[2]*x[i-2];
    y[0] = coef[0]*x[0] + coef[1]*st[0] + coef[2]*st[1];
    if (n > 1) y[1] += coef[2]*st[0];
    if (n >= 2) { st[0] = x[n-1]; st[1] = x[n-2]; }
}

void smpl_perc_model(void *state, const float *xsubfr, int xsubfr_len,
                     int frame_ms, int is_last, int len_r, float *r) {
    PercModelState *s = (PercModelState *)state;
    int src_off = xsubfr_len - (WIN_NEXT_WB_LONG - WIN_NEXT_WB_LEN);
    int keep = PERCW_NFFT - xsubfr_len;
    memmove(s->buf, s->buf + src_off, keep * sizeof(float));
    memcpy(s->buf + keep, xsubfr, xsubfr_len * sizeof(float));

    int winlen = WIN_PREV_PERC_LEN + frame_ms*16 + WIN_NEXT_WB_LONG;
    int skip = PERCW_NFFT - winlen; if (skip < 0) skip = 0;

    float *bw = s->fft_bw;  /* pre-allocated */
    memset(bw, 0, PERCW_NFFT * sizeof(float));
    perc_win(s, s->buf + skip, bw + skip, winlen, frame_ms, is_last == 0);

    float *f = s->fft_f;  /* pre-allocated */
    rfft_forward_ordered(bw, PERCW_NFFT, f);
    f[0] *= f[0]; f[1] *= f[1];
    for (int i = 1; i < PERCW_NFFT/2; i++) {
        f[2*i] = f[2*i]*f[2*i] + f[2*i+1]*f[2*i+1];
        f[2*i+1] = 0.0f;
    }
    smth_filt(f, s->smth_coef);

    /* Inverse FFT to get autocorrelation */
    float *time_out = s->fft_time;  /* pre-allocated */
    rfft_backward_ordered(f, PERCW_NFFT, time_out);
    for (int i = 0; i < len_r; i++) r[i] = time_out[i] / (float)PERCW_NFFT;
}

void smpl_perc_ac2a(const float *r, int len_r, float perc_emph, int perc_resp_len,
                    float reg, float *a_out) {
    float b[3] = {perc_emph, 1.0f + perc_emph*perc_emph, perc_emph};
    float st[2] = {r[0], r[1]};
    float rt[SMPL_MAX_L_RESP];
    filt_ma2(r + 1, perc_resp_len, b, st, rt);

    double cd[SMPL_MAX_L_RESP];
    for (int i = 0; i < perc_resp_len; i++) cd[i] = (double)rt[i];

    float rc[SMPL_MAX_L_RESP];
    ac2rc_dbl(cd, perc_resp_len - 1, (double)reg, rc);
    rc2a(rc, perc_resp_len - 1, a_out);
}
