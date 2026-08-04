/*
 * synth.c — NLSF reconstruction, NLSF→LPC, LTP/ACB synthesis.
 */

#include "decode.h"
#include "../seed.h"
#include <math.h>
#include <string.h>
#include <stdlib.h>

/* ── Constants ──────────────────────────────────────────────────────────────── */
static const float smpl_pi_f32 = 3.1415927410125f;
static const float smpl_nlsf_weight_w_max = 999.9999f;
static const float smpl_nlsf_weight_eps = 0.0009999999f;
static const int   smpl_stabilize_max_loop = 1000;
static const float smpl_stabilize_eps = 9.5367431640625e-07f;
static const float g_ltp = 0.949999988079071f;
static const int   smpl_frac_state_len = 728;
static const int   ltp_hist_len = LTP_HIST_LEN;

/* smplFIR16: 16-tap symmetric fractional-delay interpolation FIR */
static const float smpl_fir16[16] = {
    -0.000006392598606907995f, 0.00011064113641623408f, -0.0009153038263320923f,
    0.0048477197997272015f, -0.018698347732424736f, 0.05759090930223465f,
    -0.15997476875782013f, 0.617045521736145f, 0.6170454621315002f,
    -0.15997475385665894f, 0.05759090557694435f, -0.018698347732424736f,
    0.0048477197997272015f, -0.0009153038263320923f, 0.00011064114369219169f,
    -0.0000063925981521606445f,
};

/* ── smplNLSFLaroiaWeights ─────────────────────────────────────────────────── */
static void smpl_nlsf_laroia_weights(const float *nlsf, float *out) {
    float inv[SMPL_ORDER + 1];
    float gap = nlsf[0];
    inv[0] = (gap > smpl_nlsf_weight_eps) ? 1.0f / gap : smpl_nlsf_weight_w_max;
    float prev = nlsf[0];
    for (int k = 1; k < SMPL_ORDER; k++) {
        gap = nlsf[k] - prev;
        inv[k] = (gap > smpl_nlsf_weight_eps) ? 1.0f / gap : smpl_nlsf_weight_w_max;
        prev = nlsf[k];
    }
    gap = smpl_pi_f32 - nlsf[SMPL_ORDER - 1];
    inv[SMPL_ORDER] = (gap > smpl_nlsf_weight_eps) ? 1.0f / gap : smpl_nlsf_weight_w_max;
    for (int k = 0; k < SMPL_ORDER; k++) out[k] = inv[k] + inv[k + 1];
}

/* ── smplNLSFDecorr ────────────────────────────────────────────────────────── */
static void smpl_nlsf_decorr(const float *mat, const float *vec, float *out) {
    float scr[SMPL_ORDER];
    float v0 = vec[0];
    for (int r = 0; r < SMPL_ORDER; r++) scr[r] = v0 * mat[r];
    for (int c = 1; c < SMPL_ORDER; c++) {
        float v = vec[c];
        const float *base = mat + c * SMPL_ORDER;
        for (int r = 0; r < SMPL_ORDER; r++) scr[r] += base[r] * v;
    }
    memcpy(out, scr, SMPL_ORDER * sizeof(float));
}

/* ── smplStabilizeNLSF ──────────────────────────────────────────────────────── */
static void smpl_stabilize_nlsf(float *nlsf, const float *min_spacing) {
    int L = SMPL_ORDER;
    float marg[SMPL_ORDER + 1];
    marg[0] = nlsf[0] - min_spacing[0];
    for (int i = 1; i < L; i++) marg[i] = nlsf[i] - nlsf[i - 1] - min_spacing[i];
    marg[L] = smpl_pi_f32 - nlsf[L - 1] - min_spacing[L];

    /* argmin */
    float mn = marg[0]; int sel = 0;
    for (int i = 1; i < L + 1; i++) if (marg[i] < mn) { mn = marg[i]; sel = i; }

    int loop_n = 0;
    while (mn < 0.0f) {
        float d = (float)loop_n * smpl_stabilize_eps - mn;
        if (sel == 0) { marg[0] += d; marg[1] -= d; }
        else if (sel == L) { marg[L] += d; marg[L - 1] -= d; }
        else { marg[sel] += d; float half = d * 0.5f; marg[sel - 1] -= half; marg[sel + 1] -= half; }
        /* re-argmin */
        mn = marg[0]; sel = 0;
        for (int i = 1; i < L + 1; i++) if (marg[i] < mn) { mn = marg[i]; sel = i; }
        if (mn < 0.0f) { loop_n++; if (loop_n == smpl_stabilize_max_loop) break; }
    }
    nlsf[0] = min_spacing[0] + marg[0];
    float run = nlsf[0];
    for (int i = 1; i < L; i++) { run = run + marg[i] + min_spacing[i]; nlsf[i] = run; }
}

/* ── SmplReconstructNLSF ────────────────────────────────────────────────────── */
void smpl_reconstruct_nlsf(float *out, int stage1, int config, int grid,
                           const int32_t stage2[16], const float *prev_nlsf) {
    /* Clamp indices to valid ranges (garbage input may produce out-of-range) */
    if (stage1 < 0) stage1 = 0; if (stage1 > 1) stage1 = 1;
    if (config < 0) config = 0; if (config > 1) config = 1;
    if (grid < 0) grid = 0; if (grid > 16) grid = 16;

    float resid[SMPL_ORDER];
    for (int k = 0; k < SMPL_ORDER; k++) {
        int sym = (int)stage2[k];
        if (sym >= 0 && sym < g_smpl_synth.valtables_len[stage1][config][grid][k]) {
            resid[k] = g_smpl_synth.valtables[stage1][config][grid][k][sym];
        } else {
            resid[k] = 0.0f;
        }
    }

    if (grid == 16) {
        float base[SMPL_ORDER];
        const float *base_tbl = g_smpl_synth.grid16_w[1 - stage1];
        float alpha = g_smpl_synth.grid16_alpha[stage1];
        for (int k = 0; k < SMPL_ORDER; k++) {
            float pv = prev_nlsf[k];
            base[k] = pv + alpha * (base_tbl[k] - pv);
        }
        float w[SMPL_ORDER];
        smpl_nlsf_laroia_weights(base, w);
        for (int i = 0; i < SMPL_ORDER; i++) w[i] = mlow_sqrtf32(w[i]);
        float decorr[SMPL_ORDER];
        smpl_nlsf_decorr(g_smpl_synth.grid16_matrices[stage1][config], resid, decorr);
        for (int k = 0; k < SMPL_ORDER; k++) out[k] = base[k] + decorr[k] / w[k];
        smpl_stabilize_nlsf(out, g_smpl_synth.min_spacing[stage1]);
        return;
    }

    /* matrix case (grid < 16) */
    const float *cent = g_smpl_synth.centroids[stage1][grid];
    const float *mat = &g_smpl_synth.matrices[stage1][grid][0][0];
    for (int r = 0; r < SMPL_ORDER; r++) {
        float acc = 2.0f * cent[r];
        for (int c = 0; c < SMPL_ORDER; c++) {
            acc += mat[c * SMPL_ORDER + r] * resid[c];
        }
        out[r] = acc;
    }
    smpl_stabilize_nlsf(out, g_smpl_synth.min_spacing[stage1]);
}

/* ── smplNLSFPoly ──────────────────────────────────────────────────────────── */
static void smpl_nlsf_poly(double *out, const double *cosv, int half, int parity) {
    out[0] = 1.0;
    out[1] = -2.0 * cosv[parity];
    for (int k = 1; k < half; k++) {
        double c = -2.0 * cosv[2 * k + parity];
        out[k + 1] = 2.0 * out[k - 1] + c * out[k];
        for (int n = k; n > 1; n--) out[n] += out[n - 2] + c * out[n - 1];
        out[1] += c;
    }
}

/* ── SmplNLSF2A ────────────────────────────────────────────────────────────── */
void smpl_nlsf2a(float *a, const float *nlsf, int order) {
    int half = order / 2;
    double cosv[16];
    for (int i = 0; i < order; i++) cosv[i] = cos((double)nlsf[i]);
    double p[9], q[9];
    smpl_nlsf_poly(p, cosv, half, 0);
    smpl_nlsf_poly(q, cosv, half, 1);

    a[0] = 1.0f;
    for (int k = 0; k < half; k++) {
        double pt = p[k + 1] + p[k];
        double qt = q[k + 1] - q[k];
        a[k + 1] = (float)(0.5 * (pt + qt));
        a[order - k] = (float)(0.5 * (pt - qt));
    }
}

/* ── smplLPCSynthesis ──────────────────────────────────────────────────────── */
void smpl_lpc_synthesis(const float *ex, const float *a, float *out, float *state, int len) {
    int order = SMPL_ORDER;
    for (int n = 0; n < len; n++) {
        double acc = (double)ex[n];
        for (int j = 1; j <= order; j++) {
            double prev;
            if (n >= j) prev = (double)out[n - j];
            else prev = (double)state[order + n - j];
            acc -= (double)a[j] * prev;
        }
        out[n] = (float)acc;
    }
    if (len >= order) memcpy(state, out + len - order, order * sizeof(float));
}

/* ── SmplGainLin ────────────────────────────────────────────────────────────── */
double smpl_gain_lin(int32_t gain_q) {
    float y = (float)gain_q * 6.103515625e-05f * 0.10000000149011612f * 27749388.0f + 1064866816.0f;
    int32_t i;
    if (y < 2147483648.0f && y > -2147483648.0f) i = (int32_t)y;
    else i = -2147483648;
    uint32_t bits = (uint32_t)i;
    float f;
    memcpy(&f, &bits, sizeof(float));
    f -= 3.1622775509276835e-09f;
    if (f < 0.0f) f = 0.0f;
    return (double)f;
}

/* ── smplFloorF32 ───────────────────────────────────────────────────────────── */
static float smpl_floor_f32(float x) {
    int32_t i = (int32_t)x;
    if ((float)i > x) i--;
    return (float)i;
}

/* ── SmplLTPFracGain ────────────────────────────────────────────────────────── */
float smpl_ltp_frac_gain(double norm_gain) {
    return (float)norm_gain * -0.16999998688697815f + 0.3499999940395355f;
}

/* ── smplFir8 ───────────────────────────────────────────────────────────────── */
static void smpl_fir8(float *sig, int in_base, int out_base, int cnt) {
    for (int jj = 0; jj < cnt; jj++) {
        float acc = 0.0f;
        for (int i = 0; i < 8; i++) {
            acc += (sig[in_base + jj + i] + sig[in_base + jj + 15 - i]) * smpl_fir16[i];
        }
        sig[out_base + jj] = acc;
    }
}

/* ── smplFracLTP ───────────────────────────────────────────────────────────── */
static void smpl_frac_ltp(const float *lag, int num_subfr, float *sig, int sig_end, int state_len, float *out) {
    int lb = sig_end - (40 * num_subfr - state_len);
    for (int sf = 0; sf < num_subfr; sf++) {
        float fl = smpl_floor_f32(lag[sf]);
        int int_lag = (int)fl;
        if ((float)int_lag == lag[sf]) {
            for (int k = 0; k < 40; k++) sig[lb + k] = sig[lb + k - int_lag];
            for (int k = 0; k < 40; k++) {
                out[sf * 40 + k] = sig[lb + k];
                out[(num_subfr + sf) * 40 + k] = sig[lb + k - int_lag - 1] + sig[lb + k - int_lag + 1];
            }
        } else {
            int b = (num_subfr + sf) * 40;
            for (int k = 0; k < 40; k++) out[b + k] = sig[lb - int_lag - 1 + k] + sig[lb - int_lag + 1 + k];
            float l10 = 0.0f;
            for (int j = 0; j < 16; j++) l10 += sig[lb - 9 - int_lag + j] * smpl_fir16[j];
            smpl_fir8(sig, lb - int_lag - 8, lb, 40);
            float l11 = 0.0f;
            for (int j = 0; j < 16; j++) l11 += sig[lb + 32 - int_lag + j] * smpl_fir16[j];
            for (int k = 0; k < 40; k++) out[sf * 40 + k] = sig[lb + k];
            out[b] = l10 + sig[lb + 1];
            for (int k = 0; k < 38; k++) out[b + 1 + k] = sig[lb + k] + sig[lb + 2 + k];
            out[b + 39] = l11 + sig[lb + 38];
        }
        lb += 40;
    }
}

/* ── smplExcGainApply ──────────────────────────────────────────────────────── */
static void smpl_exc_gain_apply(int sub_len, const float *input, smpl_exc_gain_state_t *st, float *out, float gain) {
    if (gain != 0.0f) {
        float s5 = st->s1;
        float s6 = (s5 + s5) + st->s0;
        float d = st->s0 - s5;
        float abs_d = mlow_absf32(d);
        float abs_s6 = mlow_absf32(s6);
        float mn = abs_d + gain;
        if (abs_s6 < mn) mn = abs_s6;
        float t = d * mn / (abs_d + 1e-12f);
        st->s1 = (s6 - t) / 3.0f;
        st->s0 = (2.0f * t + s6) / 3.0f;
    }
    if (sub_len == 0) return;
    float s0 = st->s0;
    for (int n = 0; n < sub_len; n++) out[n] = s0 * input[n];
    float s1 = st->s1;
    for (int n = 0; n < sub_len; n++) out[n] += s1 * input[sub_len + n];
}

/* ── SmplLTPSubframePred ───────────────────────────────────────────────────── */
void smpl_ltp_subframe_pred(float *hist, int hist_pos, float lag_f, float gain_frac,
                                    smpl_exc_gain_state_t *gst, float *pred_out) {
    float frac_out[2 * 2 * 40];
    float lags[2] = {lag_f, lag_f};
    smpl_frac_ltp(lags, 2, hist, hist_pos - 648, smpl_frac_state_len, frac_out);
    smpl_exc_gain_apply(SMPL_SUBFR_LEN, frac_out, gst, pred_out, gain_frac);
}

/* ── FCB gains ──────────────────────────────────────────────────────────────── */
static fcb_gains_t g_fcb_gains;
static int g_fcb_gains_built = 0;

static void build_fcb_gains(void) {
    if (g_fcb_gains_built) return;
    for (int ix = 0; ix <= 90; ix++) {
        g_fcb_gains.uv[ix] = (float)pow(10.0, 0.05 * (double)((float)ix * 1.0f + -90.0f));
    }
    for (int ix = 0; ix < 34; ix++) {
        g_fcb_gains.v[ix] = (float)pow(10.0, 0.05 * (double)((float)ix * 3.0f + -100.0f));
    }
    g_fcb_gains_built = 1;
}

const fcb_gains_t *fcb_gains(void) {
    build_fcb_gains();
    return &g_fcb_gains;
}