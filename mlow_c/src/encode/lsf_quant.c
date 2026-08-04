/*
 * lsf_quant.c — LSF quantizer.
 */
#include "encode.h"
#include "../seed.h"
#include "../tables/lsf_seed.h"
#include <math.h>
#include <string.h>
#include <stdlib.h>

static const float smpl_pi = 3.1415926535897f;
static const float lsf_qstep_cond_mult = 0.9f;

/* ── Helpers ──────────────────────────────────────────────────────────────── */
static int32_t smpl_sign(float a) { return a > 0 ? 1 : (a == 0 ? 0 : -1); }

static void sub_vec(const float *y, const float *z, float *out) {
    for (int i = 0; i < SMPL_LPC_ORDER; i++) out[i] = y[i] - z[i];
}

static float dot_prod(const float *a, const float *b) {
    float s = 0.0f;
    for (int i = 0; i < SMPL_LPC_ORDER; i++) s += a[i] * b[i];
    return s;
}

static float werr(const float *x, const float *y, const float *w) {
    float s = 0.0f;
    for (int k = 0; k < SMPL_LPC_ORDER; k++) { float e = x[k] - y[k]; s += w[k] * e * e; }
    return s;
}

static void matrix_mult_transp16(const float c[16][16], const float *x, float *y, int len_x) {
    float yt[16];
    float xtmp = x[0];
    for (int i = 0; i < 16; i++) yt[i] = c[0][i] * xtmp;
    for (int j = 1; j < len_x; j++) {
        xtmp = x[j];
        for (int i = 0; i < 16; i++) yt[i] += c[j][i] * xtmp;
    }
    memcpy(y, yt, 16 * sizeof(float));
}

static void get_maxi_k(const float *x, int n, int32_t *idx, int k) {
    bool *used = (bool *)calloc(n, sizeof(bool));
    for (int slot = 0; slot < k; slot++) {
        int32_t best_i = -1;
        float best_v = -INFINITY;
        for (int i = 0; i < n; i++) {
            if (used[i]) continue;
            if (x[i] > best_v) { best_v = x[i]; best_i = (int32_t)i; }
        }
        idx[slot] = best_i < 0 ? 0 : best_i;
        if (best_i >= 0) used[best_i] = true;
    }
    free(used);
}

/* ── lsfWeightsSpectral ────────────────────────────────────────────────────── */
static void lsf_weights_spectral(const float *a, const float *lsf, float *lsfw) {
    for (int i = 0; i < SMPL_LPC_ORDER; i++) {
        float e_re = mlow_cosf32(lsf[i]), e_im = mlow_sinf32(lsf[i]);
        float acc_re = 1.0f, acc_im = 0.0f;
        float ep_re = e_re, ep_im = e_im;
        for (int j = 1; j < SMPL_LPC_ORDER; j++) {
            acc_re += ep_re * a[j];
            acc_im -= ep_im * a[j];
            float nr = ep_re * e_re - ep_im * e_im;
            float ni = ep_re * e_im + ep_im * e_re;
            ep_re = nr; ep_im = ni;
        }
        acc_re += ep_re * a[SMPL_LPC_ORDER];
        acc_im -= ep_im * a[SMPL_LPC_ORDER];
        lsfw[i] = acc_re * acc_re + acc_im * acc_im;
    }
    float min_lsfw = lsfw[0];
    for (int i = 1; i < SMPL_LPC_ORDER; i++) if (lsfw[i] < min_lsfw) min_lsfw = lsfw[i];
    float scale = 1.0f / min_lsfw;
    for (int i = 0; i < SMPL_LPC_ORDER; i++) lsfw[i] = 1.0f / mlow_sqrtf32(lsfw[i] * scale);
}

/* ── LsfWeightsLaroia ──────────────────────────────────────────────────────── */
static void lsf_weights_laroia(const float *lsf, float *lsfw) {
    float min_dist = 1e-3f;
    float inv_delta[17];
    inv_delta[0] = 1.0f / mlow_maxf32(lsf[0], min_dist);
    for (int i = 1; i < SMPL_LPC_ORDER; i++)
        inv_delta[i] = 1.0f / mlow_maxf32(lsf[i] - lsf[i-1], min_dist);
    inv_delta[SMPL_LPC_ORDER] = 1.0f / mlow_maxf32(smpl_pi - lsf[SMPL_LPC_ORDER-1], min_dist);
    for (int i = 0; i < SMPL_LPC_ORDER; i++) lsfw[i] = inv_delta[i] + inv_delta[i+1];
}

/* ── lsfMinDist ──────────────────────────────────────────────────────────────── */
static void lsf_min_dist(float *lsfs, const float *min_dist) {
    int n = SMPL_LPC_ORDER;
    float dlsfs[17];
    dlsfs[0] = lsfs[0] - min_dist[0];
    for (int i = 1; i < n; i++) dlsfs[i] = (lsfs[i] - lsfs[i-1]) - min_dist[i];
    dlsfs[n] = (smpl_pi - lsfs[n-1]) - min_dist[n];
    for (int k = 0; k < 1000; k++) {
        float dm = dlsfs[0]; int min_ix = 0;
        for (int i = 1; i < n+1; i++) if (dlsfs[i] < dm) { dm = dlsfs[i]; min_ix = i; }
        if (dm >= 0.0f) {
            lsfs[0] = dlsfs[0] + min_dist[0];
            for (int i = 1; i < n; i++) lsfs[i] = lsfs[i-1] + (dlsfs[i] + min_dist[i]);
            return;
        }
        float delta = (float)k * 1e-6f - dm;
        dlsfs[min_ix] += delta;
        if (min_ix == 0) dlsfs[1] -= delta;
        else if (min_ix == n) dlsfs[n-1] -= delta;
        else { delta *= 0.5f; dlsfs[min_ix-1] -= delta; dlsfs[min_ix+1] -= delta; }
    }
}

/* ── rotApplyWght ───────────────────────────────────────────────────────────── */
static void rot_apply_wght(const float rot[16][16], const float *lsf,
                            float we[16][16], float wie[16][16]) {
    float lsfw[16];
    lsf_weights_laroia(lsf, lsfw);
    for (int i = 0; i < 16; i++) lsfw[i] = mlow_sqrtf32(lsfw[i]);
    float lsfw_inv[16];
    for (int i = 0; i < 16; i++) lsfw_inv[i] = 1.0f / lsfw[i];
    for (int i = 0; i < 16; i++)
        for (int j = 0; j < 16; j++) {
            we[i][j] = rot[i][j] * lsfw_inv[j];
            wie[j][i] = rot[i][j] * lsfw[j];
        }
}

/* ── condParams ─────────────────────────────────────────────────────────────── */
typedef struct {
    float st1_cbhalf[16];
    float st1_cb_cinv[16];
    float st1_we[16][16];
    float st1_wie[16][16];
} cond_params_t;

/* ── vqTemp ──────────────────────────────────────────────────────────────────── */
static void vq_temp(const float *lsf, const float cbhalf[16][16], const float cb_cinv[16][16],
                    const cond_params_t *cond, int surv, int32_t *idxs) {
    float err[17];
    float tmp[16];
    for (int s = 0; s < 16; s++) {
        sub_vec(cbhalf[s], lsf, tmp);
        err[s] = -dot_prod(tmp, cb_cinv[s]);
    }
    int cb_centroids = 16;
    if (cond) {
        sub_vec(cond->st1_cbhalf, lsf, tmp);
        err[16] = -dot_prod(tmp, cond->st1_cb_cinv);
        cb_centroids = 17;
    }
    get_maxi_k(err, cb_centroids, idxs, surv);
}

/* ── lsfQuantCore ───────────────────────────────────────────────────────────── */
static void lsf_quant_core(const lsf_cb_t *cb, const float *a, const float *nlsf,
                           int voiced, int low_rate, const cond_params_t *cond,
                           float rd_w_adj, int surv,
                           int32_t qi[17], float qlsf[16]) {
    const lsf_st1_t *st1 = &cb->st1[voiced];
    const float (*min_dist)[17] = (voiced == 1) ? &cb->min_dist_v : &cb->min_dist_uv;
    float lsf[16]; memcpy(lsf, nlsf, 16 * sizeof(float));
    float wlsf[16]; lsf_weights_spectral(a, lsf, wlsf);

    float qstep = cb->qstep[voiced][low_rate];
    float qstep_cond = qstep * lsf_qstep_cond_mult;

    int32_t qim1[17];
    vq_temp(lsf, st1->cbhalf, st1->cb_cinv, cond, surv, qim1);

    float rd_best = INFINITY;
    int32_t out_qi[17] = {0};
    float out_qlsf[16] = {0};

    for (int s1 = 0; s1 < surv; s1++) {
        int qi1 = (int)qim1[s1];
        bool is_cond = (qi1 == 16);

        float lsfq1[16];
        if (is_cond) {
            for (int i = 0; i < 16; i++) lsfq1[i] = cond->st1_cbhalf[i] * 2.0f;
        } else {
            for (int i = 0; i < 16; i++) lsfq1[i] = st1->cbhalf[qi1][i] * 2.0f;
        }

        float qerr_in[16]; sub_vec(lsf, lsfq1, qerr_in);
        float qerr[16];
        const float (*wie_ptr)[16] = is_cond ? cond->st1_wie : st1->wie[qi1];
        matrix_mult_transp16(wie_ptr, qerr_in, qerr, 16);

        float inv_qstep = is_cond ? 1.0f / qstep_cond : 1.0f / qstep;
        for (int i = 0; i < 16; i++) qerr[i] *= inv_qstep;

        float bits;
        if (cond == NULL) bits = st1->bits[qi1];
        else bits = st1->bits_cond[qi1];

        int32_t alt[16], qi2[16];
        float abs_qerr[16], qres[16];
        const lsf_st2_t *st2 = &cb->st2[voiced][low_rate][qi1];
        for (int i = 0; i < 16; i++) {
            int32_t qi2i = (int32_t)mlow_roundf32(qerr[i]);
            int32_t mn = cb->min_qi[voiced][low_rate][qi1][i];
            int32_t mx = cb->max_qi[voiced][low_rate][qi1][i];
            if (qi2i > mx) qi2i = mx;
            if (qi2i < mn) qi2i = mn;
            qerr[i] -= (float)qi2i;
            alt[i] = smpl_sign(qerr[i]);
            if ((qi2i == mx && alt[i] > 0) || (qi2i == mn && alt[i] < 0))
                abs_qerr[i] = -1.0f;
            else
                abs_qerr[i] = mlow_absf32(qerr[i]);
            qi2i -= mn;
            int qi2u = (int)qi2i;
            bits += st2->num_bits[i][qi2u];
            qres[i] = st2->qlvls[i][qi2u];
            qi2[i] = qi2i;
        }

        int32_t i_alt[16];
        get_maxi_k(abs_qerr, 16, i_alt, surv);

        const float (*we_ptr)[16] = is_cond ? cond->st1_we : st1->we[qi1];
        float lsfq[16];
        matrix_mult_transp16(we_ptr, qres, lsfq, 16);
        for (int i = 0; i < 16; i++) lsfq[i] += lsfq1[i];

        int surv2 = surv - s1;
        int32_t ind_chgd = -1;
        float lsfq_base[16]; memcpy(lsfq_base, lsfq, 16 * sizeof(float));
        float cur_bits = bits;
        float bits_orig = bits;

        for (int s2 = 0; s2 < surv2; s2++) {
            float lsfq_copy[16]; memcpy(lsfq_copy, lsfq, 16 * sizeof(float));
            lsf_min_dist(lsfq_copy, *min_dist);
            float w = werr(lsf, lsfq_copy, wlsf);
            float rd = 0.5f * 16.0f * mlow_log2f32(w) * rd_w_adj + cur_bits;
            if (rd < rd_best) {
                rd_best = rd;
                out_qi[0] = (int32_t)qi1;
                memcpy(&out_qi[1], qi2, 16 * sizeof(int32_t));
                memcpy(out_qlsf, lsfq_copy, 16 * sizeof(float));
            }
            if (s2 == surv2 - 1 || abs_qerr[i_alt[s2]] < 0.25f) break;
            if (s2 > 0) { int ic = (int)ind_chgd; qi2[ic] -= alt[ic]; }
            ind_chgd = i_alt[s2];
            int ic = (int)ind_chgd;
            int32_t qi2_old = qi2[ic];
            qi2[ic] += alt[ic];
            int32_t qi2_new = qi2[ic];
            float qlvls_diff = st2->qlvls[ic][qi2_new] - st2->qlvls[ic][qi2_old];
            for (int i = 0; i < 16; i++) lsfq[i] = lsfq_base[i] + qlvls_diff * we_ptr[ic][i];
            cur_bits = bits_orig + st2->num_bits[ic][qi2_new] - st2->num_bits[ic][qi2_old];
        }
    }
    memcpy(qi, out_qi, 17 * sizeof(int32_t));
    memcpy(qlsf, out_qlsf, 16 * sizeof(float));
}

/* ── LsfQuant ────────────────────────────────────────────────────────────────── */
int lsf_quant(const float *a, const float *nlsf, int voiced, int config,
              float rdw_adj, int surv, int32_t qi[17], float qlsf[16]) {
    lsf_quant_core(&g_lsf_cb, a, nlsf, voiced, 0, NULL, rdw_adj, surv, qi, qlsf);
    return 0;
}

/* ── LsfQuantCond ────────────────────────────────────────────────────────────── */
int lsf_quant_cond(const float *a, const float *nlsf, const float *prev_lsfq,
                   int voiced, int config, float rdw_adj, int surv,
                   int32_t qi[17], float qlsf[16]) {
    const lsf_st1_t *st1 = &g_lsf_cb.st1[voiced];
    const float *cb_mean = (voiced == 1) ? g_lsf_cb.mean_v : g_lsf_cb.mean_uv;
    float reg = g_lsf_cb.reg_cond[voiced];

    float lsfq_prev_reg[16], st1_cbhalf[16];
    for (int i = 0; i < 16; i++) {
        lsfq_prev_reg[i] = prev_lsfq[i] + reg * (cb_mean[i] - prev_lsfq[i]);
        st1_cbhalf[i] = 0.5f * lsfq_prev_reg[i];
    }
    float st1_cb_cinv[16];
    matrix_mult_transp16(st1->cinv, lsfq_prev_reg, st1_cb_cinv, 16);

    cond_params_t cond;
    memcpy(cond.st1_cbhalf, st1_cbhalf, 16 * sizeof(float));
    memcpy(cond.st1_cb_cinv, st1_cb_cinv, 16 * sizeof(float));
    rot_apply_wght(st1->rotcond[0], lsfq_prev_reg, cond.st1_we, cond.st1_wie);

    lsf_quant_core(&g_lsf_cb, a, nlsf, voiced, 0, &cond, rdw_adj, surv, qi, qlsf);
    return 0;
}