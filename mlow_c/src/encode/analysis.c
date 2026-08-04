/*
 * analysis.c �?Encoder analysis front-end + voiced/unvoiced classifier.
 */
#include "encode.h"
#include "../seed.h"
#include "../range_coder.h"
#include <math.h>
#include <string.h>
#include <stdlib.h>

/* ── Constants ──────────────────────────────────────────────────────────────── */
static const float smpl_vuv_weights[5] = {1.0f, 0.5f, 0.5f, 0.7f, 0.3f};
static const float smpl_vuv_bias = -0.1038f;
static const float smpl_vuv_hyst = 0.05f;
static const int   transition_ix = SMPL_F_LEN / 3;
static const float harmonicity_undef = -10000.0f;
static const float smpl_perc_reg = 1e-3f;
#define NUM_HARMS 4
#define MAX_LTP_BUF_LEN 659

/* ── Forward declarations ───────────────────────────────────────────────────── */
static float smpl_inv_sigmoid(float x);
static float smpl_sigmoid_enc(float x);
static float vuv_dot(const float *a, const float *b, int l);
static float vuv_sum(const float *x, int l);
static void front_end_quantize(front_end_lsf_t *fe, int voiced, const float *prev_nlsf,
                                int32_t *grid, int32_t stage2[16], float *committed,
                                float predcoef[17]);

/* ══════════════════════════════════════════════════════════════════════════════
 * Utility helpers
 * ══════════════════════════════════════════════════════════════════════════════ */

static float smpl_inv_sigmoid(float x) {
    return -(float)log(1.0 / (double)x - 1.0);
}

static float smpl_sigmoid_enc(float x) {
    if (x > 80.0f) return 1.0f;
    if (x < -80.0f) return 0.0f;
    return 1.0f / (1.0f + (float)exp((double)(-x)));
}

static float vuv_dot(const float *a, const float *b, int l) {
    float s = 0.0f;
    for (int i = 0; i < l; i++) s += a[i] * b[i];
    return s;
}

static float vuv_sum(const float *x, int l) {
    float s = 0.0f;
    for (int i = 0; i < l; i++) s += x[i];
    return s;
}

static float smpl_floor_f32(float x) {
    int i = (int)x;
    if ((float)i > x) i--;
    return (float)i;
}

/* ══════════════════════════════════════════════════════════════════════════════
 * smplHarmStrengthAt (HarmStrengthAt �?recomputeHarmonicity)
 * ══════════════════════════════════════════════════════════════════════════════ */

float smpl_harm_strength_at(float avg_lag, const float *f2w, int f2w_len) {
    float harm_hz = 16000.0f / avg_lag;
    float inv_f2_step = 2.0f * (float)(f2w_len - 1) / 16000.0f;
    float harm_width = harm_hz * inv_f2_step;
    float harm_strength = 0.1f;

    if (harm_width > 1.97f) {
        float peak_valley_mags[9]; /* 2*NUM_HARMS+1 */
        float inv_harm_width = 1.0f / harm_width;
        for (int nh = 0; nh < 9; nh++) {
            float ix_start = 0.5f * (float)nh * harm_width;
            float ix_end = ix_start + harm_width;
            int idx_start = (int)ceilf(ix_start);
            int idx_end   = (int)floorf(ix_end);
            int weights_len = idx_end - idx_start + 1;
            if (weights_len < 0) weights_len = 0;
            if (weights_len > 20) weights_len = 20;
            float weights[20] = {0};
            for (int i = 0; i < weights_len; i++) {
                float tmp = ((float)idx_start - ix_start + (float)i) * inv_harm_width;
                tmp -= tmp * tmp;
                weights[i] = tmp * tmp;
            }
            int base = idx_start;
            if (base < 0) base = 0;
            if (base > f2w_len) base = f2w_len;
            int avail = f2w_len - base;
            if (avail > weights_len) avail = weights_len;
            float nrg = vuv_dot(f2w + base, weights, avail) / vuv_sum(weights, weights_len);
            peak_valley_mags[nh] = sqrtf(nrg + 1e-30f);
        }
        float mag_ratios_log[4], mag_weights_f[4];
        float mag_peak_w[3] = {1.0f, 10.0f, 1.0f};
        float mag_valley_w[3] = {5.0f, 2.0f, 5.0f};
        for (int nh = 0; nh < 4; nh++) {
            float mpeak = mag_peak_w[0]*peak_valley_mags[2*nh]
                        + mag_peak_w[1]*peak_valley_mags[2*nh+1]
                        + mag_peak_w[2]*peak_valley_mags[2*nh+2];
            float mval  = mag_valley_w[0]*peak_valley_mags[2*nh]
                        + mag_valley_w[1]*peak_valley_mags[2*nh+1]
                        + mag_valley_w[2]*peak_valley_mags[2*nh+2];
            mag_ratios_log[nh] = logf(mpeak / mval);
            mag_weights_f[nh] = sqrtf(mpeak + mval + 1e-30f);
        }
        harm_strength = vuv_dot(mag_weights_f, mag_ratios_log, 4) / vuv_sum(mag_weights_f, 4);
    }
    return harm_strength;
}

/* ══════════════════════════════════════════════════════════════════════════════
 * smplGetSignalMode (SmplGetSignalMode)
 * ══════════════════════════════════════════════════════════════════════════════ */

float smpl_get_signal_mode(float pitchcorr, const float *lags, float avg_lag,
                           float harm_strength, const float *f2, float sp_act_prob,
                           vuv_mode_t *vuv) {
    float pc = pitchcorr;
    if (pc < 0.0f) pc = 0.0f;
    else if (pc > 1.0f) pc = 1.0f;
    float corr_strength = smpl_inv_sigmoid(0.1f + 0.75f * pc);
    float vad_strength = 0.04f * (1.0f - 1.04f / (sp_act_prob + 0.04f));

    float nrg_lo = 0.0f;
    for (int i = 2; i < transition_ix; i++) {
        float tmp = f2[i] * (float)(i + 3);
        nrg_lo += tmp * (float)(transition_ix - i);
    }
    float nrg_hi = 0.0f;
    for (int i = transition_ix; i < SMPL_F_LEN; i++) {
        float tmp = f2[i] * (float)(i + 3);
        nrg_hi += tmp * (float)(i - transition_ix);
    }
    if (vad_strength < -0.1f) {
        float smth_coef = -0.5f * vad_strength;
        vuv->nrg_lo_bgn += smth_coef * (nrg_lo - vuv->nrg_lo_bgn);
        vuv->nrg_hi_bgn += smth_coef * (nrg_hi - vuv->nrg_hi_bgn);
    }
    float lo_diff = nrg_lo - vuv->nrg_lo_bgn; if (lo_diff < 0.0f) lo_diff = 0.0f;
    float hi_diff = nrg_hi - vuv->nrg_hi_bgn; if (hi_diff < 0.0f) hi_diff = 0.0f;
    float tilt_lin = (lo_diff - hi_diff) / (nrg_lo + nrg_hi + 1e-9f);
    float tilt_strength = tilt_lin * tilt_lin * tilt_lin;
    float lag_strength = -smpl_sigmoid_enc(0.25f * (38.0f - avg_lag));

    float voicing_strength = (smpl_vuv_weights[0] * corr_strength +
        smpl_vuv_weights[1] * vad_strength +
        smpl_vuv_weights[2] * tilt_strength +
        smpl_vuv_weights[3] * harm_strength +
        smpl_vuv_weights[4] * lag_strength) / vuv_sum(smpl_vuv_weights, 5) + smpl_vuv_bias;

    if (vuv->last_lag_prev > 0.0f) {
        float tmp = (float)log2((double)(lags[0] / vuv->last_lag_prev));
        if (tmp > 0.0f) tmp *= 0.5f;
        vuv->voicing_prev /= 0.4f + tmp * tmp;
    }
    voicing_strength += vuv->voicing_prev * smpl_vuv_hyst;
    vuv->voicing_prev = (float)tanh(3.0 * voicing_strength);
    vuv->last_lag_prev = lags[7]; /* lags[len-1] */
    return voicing_strength;
}

/* ══════════════════════════════════════════════════════════════════════════════
 * smplAutocorr (smplAutocorr)
 * ══════════════════════════════════════════════════════════════════════════════ */

void smpl_autocorr(const double *x, int n, int order, double *r) {
    for (int lag = 0; lag <= order; lag++) {
        double s = 0.0;
        for (int i = lag; i < n; i++) s += x[i] * x[i - lag];
        r[lag] = s;
    }
}

/* ══════════════════════════════════════════════════════════════════════════════
 * smplAnalysisResidualSubfr (smplAnalysisResidualSubfr)
 * ══════════════════════════════════════════════════════════════════════════════ */

void smpl_analysis_residual_subfr(const float a_syn[17], const float *win_n, int sf, float *res) {
    for (int n = 0; n < SMPL_SUBFR_LEN; n++) {
        int idx = SMPL_ORDER + sf * SMPL_SUBFR_LEN + n;
        float acc = win_n[idx];
        for (int j = 1; j <= SMPL_ORDER; j++) {
            acc += a_syn[j] * win_n[idx - j];
        }
        res[n] = acc;
    }
}

/* ══════════════════════════════════════════════════════════════════════════════
 * smplLsfInterpolSearch (smplLsfInterpolSearch)
 * ══════════════════════════════════════════════════════════════════════════════ */

int smpl_lsf_interpol_search_full(const float *brec, const float *prev_lsfq,
                                   const float *win_n, float predcoefs[4][17],
                                   float *res_lpc) {
    /* Helper: evaluate one interpolation index */
    struct { float pc[4][17]; float r[320]; float rms; } evals[2];

    for (int idx = 0; idx < 2; idx++) {
        /* smplLPCInterpolIdx(brec, prev_lsfq, idx, SmplNLSF2A) */
        float ilsf_out[16], pc4[4][17];
        smpl_lpc_interpol(brec, prev_lsfq, idx, pc4, ilsf_out);

        float sum_rms = 0.0f;
        for (int sf = 0; sf < SMPL_SUBFR_COUNT; sf++) {
            float r[80];
            smpl_analysis_residual_subfr(pc4[sf], win_n, sf, r);
            float nrg = 0.0f;
            for (int i = 0; i < SMPL_SUBFR_LEN; i++) nrg += r[i] * r[i];
            sum_rms += sqrtf(nrg + 1e-30f);
            memcpy(evals[idx].r + sf * SMPL_SUBFR_LEN, r, SMPL_SUBFR_LEN * sizeof(float));
        }
        memcpy(evals[idx].pc, pc4, sizeof(pc4));
        evals[idx].rms = sum_rms;
    }

    int best = (evals[1].rms < evals[0].rms * 0.998f) ? 1 : 0;
    memcpy(predcoefs, evals[best].pc, 4 * 17 * sizeof(float));
    memcpy(res_lpc, evals[best].r, SMPL_INTF_LEN * sizeof(float));
    return best;
}

/* ══════════════════════════════════════════════════════════════════════════════
 * smplBuildPulseParams (smplBuildPulseParams)
 * ══════════════════════════════════════════════════════════════════════════════ */

void smpl_build_pulse_params(const int32_t *pulse, smpl_pulse_params_t *pp) {
    const int p3 = 4;
    int pos_per = SMPL_INTF_LEN / p3;
    memset(pp, 0, sizeof(*pp));

    for (int sf = 0; sf < p3; sf++) {
        int32_t s = 0;
        for (int n = sf * pos_per; n < (sf + 1) * pos_per; n++) {
            int32_t a = pulse[n];
            if (a < 0) a = -a;
            s += a;
        }
        pp->subfr[sf] = s;
    }
    pp->total = pp->subfr[0] + pp->subfr[1] + pp->subfr[2] + pp->subfr[3];

    /* Build mag_runs and signs */
    int32_t mag_runs[1024];
    int32_t signs[1024];
    int mag_count = 0, sign_count = 0;

    for (int sf = 0; sf < p3; sf++) {
        if (pp->subfr[sf] <= 0) continue;
        int base_pos = pos_per * sf;
        int32_t run_pos = (int32_t)base_pos;
        bool first = true;
        for (int n = base_pos; n < base_pos + pos_per; n++) {
            if (pulse[n] == 0) continue;
            int32_t magv = pulse[n];
            int32_t mag = magv < 0 ? -magv : magv;
            int32_t m;
            if (first) m = (int32_t)n - (int32_t)base_pos;
            else m = (int32_t)n - run_pos;
            mag_runs[mag_count++] = m;
            run_pos = (int32_t)n;
            if (mag > 1) {
                for (int32_t k = 0; k < mag - 1; k++) mag_runs[mag_count++] = 0;
            }
            signs[sign_count++] = magv < 0 ? -1 : 1;
            first = false;
        }
    }

    pp->mag_runs = (int32_t *)malloc(mag_count * sizeof(int32_t));
    memcpy(pp->mag_runs, mag_runs, mag_count * sizeof(int32_t));
    pp->mag_runs_len = mag_count;

    /* Build sign symbols */
    int num_pos = sign_count;
    smpl_raw_sym_t sign_syms[128];
    int sym_count = 0;
    int p = 0;
    while (p < num_pos) {
        int nbits = num_pos - p;
        if (nbits > 15) nbits = 15;
        uint32_t sym = 0;
        for (int q = 0; q < nbits; q++) {
            uint32_t bit = (signs[p + q] > 0) ? 1 : 0;
            sym |= bit << (nbits - 1 - q);
        }
        sign_syms[sym_count].sym = sym;
        sign_syms[sym_count].nbits = (uint32_t)nbits;
        sym_count++;
        p += nbits;
    }
    pp->sign_syms = (smpl_raw_sym_t *)malloc(sym_count * sizeof(smpl_raw_sym_t));
    memcpy(pp->sign_syms, sign_syms, sym_count * sizeof(smpl_raw_sym_t));
    pp->sign_syms_len = sym_count;
}

/* ══════════════════════════════════════════════════════════════════════════════
 * smplRateControlGains (smplRateControlGains)
 * ══════════════════════════════════════════════════════════════════════════════ */

void smpl_rate_control_gains(double target_linear, int32_t *gm_out, int32_t *gd_out, int32_t *gq_out) {
    uint32_t cfg_sel = 2;
    int32_t cb1 = (int32_t)smpl_mem_i16(0xf35e0 + cfg_sel * 2);
    uint32_t gain_tab_addr = 0xf35f0;
    double best_d = INFINITY;
    int32_t bgm = 0, bgd = 0, bgq = 0;
    for (int32_t gm = 0; gm < 84; gm++) {
        int32_t base7 = gm * cb1 - 0x154000;
        for (int32_t gd = 0; gd < 98; gd++) {
            int32_t cbv = (int32_t)smpl_mem_i16(gain_tab_addr + (uint32_t)(4 * gd) * 2);
            int32_t gq = base7 + (cbv << 4);
            double d = fabs(smpl_gain_lin(gq) - target_linear);
            if (d < best_d) { best_d = d; bgm = gm; bgd = gd; bgq = gq; }
        }
    }
    *gm_out = bgm; *gd_out = bgd; *gq_out = bgq;
}

/* ══════════════════════════════════════════════════════════════════════════════
 * percCorrsToWght (percCorrsToWght)
 * ══════════════════════════════════════════════════════════════════════════════ */

void perc_corrs_to_wght(const float *corrs[4], const float emph[2],
                        int resp_len, float *wght_out[4]) {
    int idx = 0;
    for (int i = 0; i < 4; i++) {
        smpl_perc_ac2a(corrs[i], SMPL_PERC_R_LEN, emph[idx], resp_len,
                       smpl_perc_reg, wght_out[i]);
    }
}

/* ══════════════════════════════════════════════════════════════════════════════
 * computePercCorrs (computePercCorrs)
 * ══════════════════════════════════════════════════════════════════════════════ */

void compute_perc_corrs(celp_frame_ctx_t *cs, float *corrs_out[4]) {
    const int frame_ms = 20;
    const int shorter = 32;

    for (int sf = 1; sf < SMPL_SUBFR_COUNT; sf += 2) {
        int start = cs->intf * SMPL_INTF_LEN + (sf - 1) * SMPL_SUBFR_LEN;
        int xlen = 2 * SMPL_SUBFR_LEN + shorter;
        float xsubfr[2*80+32]; /* max xlen */
        for (int i = 0; i < xlen; i++) {
            xsubfr[i] = cs->hp_n[start + i]; /* idx < len(cs.hpN) already guaranteed */
        }
        int is_last = (cs->intf == 2 && sf == SMPL_SUBFR_COUNT - 1) ? 1 : 0;
        float r[SMPL_PERC_R_LEN];
        smpl_perc_model(cs->perc, xsubfr, xlen, frame_ms, is_last, SMPL_PERC_R_LEN, r);

        /* even subframe = 0.5*(r + prev) */
        float even[SMPL_PERC_R_LEN];
        for (int i = 0; i < SMPL_PERC_R_LEN; i++) {
            even[i] = 0.5f * (r[i] + cs->perc_prev[i]);
        }
        /* Allocate and store */
        corrs_out[sf - 1] = (float *)malloc(SMPL_PERC_R_LEN * sizeof(float));
        memcpy(corrs_out[sf - 1], even, SMPL_PERC_R_LEN * sizeof(float));
        memcpy(cs->perc_prev, r, SMPL_PERC_R_LEN * sizeof(float));

        corrs_out[sf] = (float *)malloc(SMPL_PERC_R_LEN * sizeof(float));
        memcpy(corrs_out[sf], r, SMPL_PERC_R_LEN * sizeof(float));
    }
}

/* ══════════════════════════════════════════════════════════════════════════════
 * buildLtpBuf (buildLtpBuf)
 * ══════════════════════════════════════════════════════════════════════════════ */

void build_ltp_buf(celp_frame_ctx_t *cs, const float *corrs[4]) {
    /* percCorrsToWght for pitch */
    float resp_buf[4][SMPL_PITCH_PERC_RESP_LEN];
    float *resp_pitch[4];
    float emph[2] = {SMPL_PERC_EMPH_PITCH, SMPL_PERC_EMPH_PITCH};
    for (int i = 0; i < 4; i++) {
        resp_pitch[i] = resp_buf[i];
        smpl_perc_ac2a(corrs[i], SMPL_PERC_R_LEN, emph[0], SMPL_PITCH_PERC_RESP_LEN,
                       smpl_perc_reg, resp_pitch[i]);
    }

    int max_len = MAX_LTP_BUF_LEN;
    int look = SMPL_PITCH_LOOKAHEAD_LEN;
    int framelen = SMPL_INTF_LEN;
    float *ltp = cs->ltp_buf;
    int keep = max_len - framelen - look;
    memmove(ltp, ltp + framelen, keep * sizeof(float));

    int frame_start = cs->intf * SMPL_INTF_LEN - SMPL_WINNEXT_WB_LEN;

    /* sample(rel) inline helper */
    for (int i = 0; i < SMPL_SUBFR_COUNT; i++) {
        float *coef = resp_pitch[i];
        for (int n = 0; n < SMPL_SUBFR_LEN; n++) {
            int pos = i * SMPL_SUBFR_LEN + n;
            float res = 0.0f;
            for (int j = 0; j < SMPL_PITCH_PERC_RESP_LEN; j++) {
                int rel = pos - j;
                int idx = frame_start + rel;
                float v;
                if (idx >= 0) v = cs->hp_n[idx];
                else {
                    int k = idx + SMPL_PITCH_LAG_MAX;
                    v = (k >= 0) ? cs->hp_pitch_hist[k] : 0.0f;
                }
                if (j == 0) res = v;
                else res += coef[j] * v;
            }
            ltp[max_len - SMPL_SUBFR_COUNT * SMPL_SUBFR_LEN - look + i * SMPL_SUBFR_LEN + n] = res;
        }
    }
    /* lookahead */
    {
        float *coef = resp_pitch[SMPL_SUBFR_COUNT - 1];
        for (int n = 0; n < look; n++) {
            int pos = framelen + n;
            float res = 0.0f;
            for (int j = 0; j < SMPL_PITCH_PERC_RESP_LEN; j++) {
                int rel = pos - j;
                int idx = frame_start + rel;
                float v;
                if (idx >= 0) v = cs->hp_n[idx];
                else {
                    int k = idx + SMPL_PITCH_LAG_MAX;
                    v = (k >= 0) ? cs->hp_pitch_hist[k] : 0.0f;
                }
                if (j == 0) res = v;
                else res += coef[j] * v;
            }
            ltp[max_len - look + n] = res;
        }
    }
}

/* ══════════════════════════════════════════════════════════════════════════════
 * runCelpSubframes (runCelpSubframes)
 * ══════════════════════════════════════════════════════════════════════════════ */

void run_celp_subframes(celp_frame_ctx_t *cs, const float predcoefs[4][17],
                        const float *res_lpc, const float block_lags[4][2],
                        const float *corrs[4], const float emph[2],
                        int voiced, int16_t acb_idx_out[4], int16_t gain_idx_out[4],
                        int16_t pulses_out[4][40], int16_t n_pulses_out[4],
                        float *exc_lpc_out) {
    /* percCorrsToWght */
    float wght_buf[4][SMPL_CELP_PERC_RESP_LEN];
    float *perc_wght[4];
    for (int i = 0; i < 4; i++) {
        perc_wght[i] = wght_buf[i];
        smpl_perc_ac2a(corrs[i], SMPL_PERC_R_LEN, emph[0], SMPL_CELP_PERC_RESP_LEN,
                       smpl_perc_reg, perc_wght[i]);
    }

    /* Compute weighted energies per subframe */
    const float scale = 32768.0f;
    float wnrgs[4];
    for (int sf = 0; sf < SMPL_SUBFR_COUNT; sf++) {
        float s = 0.0f;
        for (int i = 0; i < SMPL_SUBFR_LEN; i++) {
            float v = res_lpc[sf * SMPL_SUBFR_LEN + i] * scale;
            s += v * v;
        }
        wnrgs[sf] = s;
    }

    float nonflatness = (voiced != 0) ? 0.0f : 2.0f;
    int tot_surv = (int32_t)(1000.0f * (float)(SMPL_FCB_TOT_SURV_20MS_MAX * SMPL_CELP_FCB_SUBFR_LEN) / (20.0f * 16000.0f));

    for (int sf = 0; sf < SMPL_SUBFR_COUNT; sf++) {
        float wnrg = wnrgs[sf];
        float wnrg_next = wnrgs[sf];
        if (sf + 1 < SMPL_SUBFR_COUNT) wnrg_next = wnrgs[sf + 1];

        int max_pulses_arr[2] = {0, 0};
        float importance_arr[2] = {0, 0};
        bitrate_ctrl_control(cs->bitrate, max_pulses_arr, importance_arr,
                             cs->coded_as_active_voice, cs->sp_act_prob,
                             nonflatness, cs->voicing_strength,
                             voiced, wnrg, wnrg_next);

        int16_t numsurv[SMPL_MAX_PULSES_PER_SF];
        for (int i = 0; i < SMPL_MAX_PULSES_PER_SF; i++) numsurv[i] = 1;
        smpl_distribute_fcb_surv(numsurv, (int32_t)max_pulses_arr[1], (int32_t)tot_surv);

        float lags[2] = {block_lags[sf][0], block_lags[sf][1]};
        int16_t fcb_max[2] = {(int16_t)max_pulses_arr[0], (int16_t)max_pulses_arr[1]};

        /* celp_encode_subframe writes [rate0, rate1] to each output;
         * we need rate 1 (main). Use temp arrays to avoid overlap. */
        int16_t tmp_pulses[2][40], tmp_np[2], tmp_acb[2], tmp_gain[2];
        celp_encode_subframe((CelpEncoder *)cs->celp, res_lpc + sf * SMPL_SUBFR_LEN,
                             predcoefs[sf], perc_wght[sf], lags,
                             fcb_max, numsurv, importance_arr,
                             tmp_pulses, tmp_np, tmp_acb, tmp_gain,
                             exc_lpc_out + sf * SMPL_SUBFR_LEN);
        /* Extract main rate (index 1) values */
        n_pulses_out[sf] = tmp_np[1];
        acb_idx_out[sf] = tmp_acb[1];
        gain_idx_out[sf] = tmp_gain[1];
        memcpy(pulses_out[sf], tmp_pulses[1], tmp_np[1] * sizeof(int16_t));
    }
}

/* ══════════════════════════════════════════════════════════════════════════════
 * smplSilentInternal (smplSilentInternal)
 * ══════════════════════════════════════════════════════════════════════════════ */

void smpl_silent_internal(candidate_t *cand) {
    memset(cand, 0, sizeof(*cand));
    /* stage2 = midpoint of codebook */
    for (int k = 0; k < 16; k++)
        cand->qsym[k] = g_smpl_synth.valtables_len[0][0][0][k] / 2;
    int32_t gm, gd, gq;
    smpl_rate_control_gains(0.0, &gm, &gd, &gq);
    cand->ip.lsf.stage1 = 0;
    cand->ip.lsf.grid = 0;
    cand->ip.lsf.extra = 0;
    for (int k = 0; k < 16; k++) cand->ip.lsf.stage2[k] = cand->qsym[k];
    cand->ip.pulses.total = 0;
    memset(cand->ip.pulses.subfr, 0, sizeof(cand->ip.pulses.subfr));
    cand->ip.pulses.mag_runs = NULL; cand->ip.pulses.mag_runs_len = 0;
    cand->ip.pulses.sign_syms = NULL; cand->ip.pulses.sign_syms_len = 0;
    cand->ip.has_pitch = false;
    cand->ip.gains.gain_main = gm; cand->ip.gains.gain_delta = gd;
    for (int k = 0; k < 4; k++) cand->ip.gains.nrg_res[k] = -1;
    cand->stage1 = 0; cand->grid = 0;
    cand->pulse_vec = (int32_t *)calloc(SMPL_INTF_LEN, sizeof(int32_t));
    cand->pitch.voiced = false;
    cand->silent = true;
}

/* ══════════════════════════════════════════════════════════════════════════════
 * frontEndLsf.quantize (fe.quantize)
 * ══════════════════════════════════════════════════════════════════════════════ */

static void front_end_quantize(front_end_lsf_t *fe, int voiced, const float *prev_nlsf,
                                int32_t *grid, int32_t stage2[16], float *committed,
                                float predcoef[17]) {
    bool cond = (fe->prev_voiced == (voiced != 0)) && fe->intf > 0;
    int32_t qi[17]; float qlsf[16];
    if (cond) {
        lsf_quant_cond(fe->a, fe->nlsf, fe->prev_lsfq, voiced,
                       0, SMPL_LSF_RDW_ADJ, SMPL_LSF_SURV, qi, qlsf);
    } else {
        lsf_quant(fe->a, fe->nlsf, voiced, 0, SMPL_LSF_RDW_ADJ, SMPL_LSF_SURV, qi, qlsf);
    }
    *grid = qi[0];
    for (int k = 0; k < 16; k++) {
        stage2[k] = qi[1 + k];
        if (stage2[k] < 0) stage2[k] = 0;
    }
    /* SmplReconstructNLSF */
    smpl_reconstruct_nlsf(committed, voiced, 0, (int)*grid, stage2, prev_nlsf);
    /* SmplNLSF2A �?predcoef */
    float a_vq[17];
    smpl_nlsf2a(a_vq, committed, SMPL_LPC_ORDER);
    for (int i = 0; i < 17; i++) predcoef[i] = a_vq[i];
    predcoef[0] = 1.0f;
}

/* ══════════════════════════════════════════════════════════════════════════════
 * commitCandidate (commitCandidate)
 * ══════════════════════════════════════════════════════════════════════════════ */

void commit_candidate(smpl_frame_synth_t *st, const candidate_t *cand,
                      const float *prev_nlsf, float *nlsf_out) {
    if (cand->silent) {
        smpl_reconstruct_nlsf(nlsf_out, 0, 0, (int)cand->ip.lsf.grid,
                              cand->ip.lsf.stage2, prev_nlsf);
        int32_t st2[16];
        memcpy(st2, cand->ip.lsf.stage2, 16 * sizeof(int32_t));
        float tmp_signal[320];
        synth_internal_frame(st, 0, 0, (int)cand->ip.lsf.grid, st2,
                             prev_nlsf, cand->pulse_vec, cand->gain_q,
                             &cand->pitch, tmp_signal, nlsf_out);
        return;
    }
    int32_t qsym[16];
    memcpy(qsym, cand->qsym, 16 * sizeof(int32_t));
    float signal[320];
    synth_internal_frame(st, (int)cand->stage1, 0, (int)cand->grid, qsym,
                         prev_nlsf, cand->pulse_vec, cand->gain_q,
                         &cand->pitch, signal, nlsf_out);
}

/* ══════════════════════════════════════════════════════════════════════════════
 * smplUnvoicedCandidate (smplUnvoicedCandidate)
 * ══════════════════════════════════════════════════════════════════════════════ */

void smpl_unvoiced_candidate(const double *win, const float *win_n,
                             const float *prev_nlsf, front_end_lsf_t *fe,
                             celp_frame_ctx_t *cs, candidate_t *cand) {
    memset(cand, 0, sizeof(*cand));

    /* frame = win[SmplOrder:] �?autocorr r0 */
    double r0_arr[1];
    smpl_autocorr(win + SMPL_ORDER, SMPL_INTF_LEN, 0, r0_arr);
    if (r0_arr[0] <= 0.0) {
        float flat[4][17];
        for (int sf = 0; sf < 4; sf++) { memset(flat[sf], 0, 17*sizeof(float)); flat[sf][0] = 1.0f; }
        float zero_res[320] = {0};
        float zero_bl[4][2] = {{0}};
        float *fresh_corrs[4] = {NULL, NULL, NULL, NULL};
        compute_perc_corrs(cs, fresh_corrs);
        int16_t acb[4] = {0}, gain_i[4] = {0}, pulses[4][40], np[4]; float exc[320];
        float emph_uv[2] = SMPL_PERC_EMPH_UV;
        run_celp_subframes(cs, flat, zero_res, zero_bl, (const float**)fresh_corrs,
                           emph_uv, 0, acb, gain_i, pulses, np, exc);
        for (int i = 0; i < 4; i++) free(fresh_corrs[i]);
        smpl_silent_internal(cand);
        return;
    }

    int32_t bgrid; int32_t bsym[16]; float brec[16]; float predcoef_q[17];
    front_end_quantize(fe, 0, prev_nlsf, &bgrid, bsym, brec, predcoef_q);

    float predcoefs[4][17]; float res_lpc[320];
    int interpol_idx = smpl_lsf_interpol_search_full(brec, fe->prev_lsfq, win_n, predcoefs, res_lpc);

    float block_lags[4][2] = {{0}};
    int16_t acb[4], gain_i[4], np[4], all_pulses[4][40];
    float exc_lpc[320];
    float emph_uv[2] = SMPL_PERC_EMPH_UV;
    run_celp_subframes(cs, predcoefs, res_lpc, block_lags, (const float**)cs->perc_corrs,
                       emph_uv, 0, acb, gain_i, all_pulses, np, exc_lpc);

    /* Build pulse vector */
    int32_t *pulse_vec = (int32_t *)calloc(SMPL_INTF_LEN, sizeof(int32_t));
    for (int sf = 0; sf < SMPL_SUBFR_COUNT; sf++) {
        for (int i = 0; i < (int)np[sf]; i++) {
            int16_t v = all_pulses[sf][i];
            int sign = (v > 0) ? 1 : -1;
            int pos = (v > 0) ? (int)v - 1 : -(int)v - 1;
            if (pos >= 0 && pos < SMPL_SUBFR_LEN)
                pulse_vec[sf * SMPL_SUBFR_LEN + pos] += sign;
        }
    }

    /* Quantize residual energy */
    float nrgres[4] = {0};
    for (int sf = 0; sf < 4; sf++) {
        float e = 0.0f;
        for (int i = 0; i < SMPL_SUBFR_LEN; i++) {
            float v = res_lpc[sf * SMPL_SUBFR_LEN + i];
            e += v * v;
        }
        nrgres[sf] = e / (float)SMPL_SUBFR_LEN;
    }
    int32_t gm, gd; int32_t nrg_res_out[4];
    smpl_quant_nrg_res4(nrgres, (int32_t[]){0,0,0,0}, &gm, &gd, nrg_res_out);

    /* Build params */
    smpl_pulse_params_t pp;
    smpl_build_pulse_params(pulse_vec, &pp);

    cand->ip.lsf.stage1 = 0;
    cand->ip.lsf.grid = bgrid;
    cand->ip.lsf.extra = interpol_idx;
    memcpy(cand->ip.lsf.stage2, bsym, 16 * sizeof(int32_t));
    cand->ip.pulses = pp;
    cand->ip.has_pitch = false;
    cand->ip.gains.gain_main = gm;
    cand->ip.gains.gain_delta = gd;
    for (int sf = 0; sf < 4; sf++) {
        cand->ip.gains.nrg_res[sf] = (pp.subfr[sf] > 0) ? (int32_t)gain_i[sf] : -1;
    }
    cand->stage1 = 0;
    cand->grid = bgrid;
    memcpy(cand->qsym, bsym, 16 * sizeof(int32_t));
    cand->pulse_vec = pulse_vec;
    memcpy(cand->gain_q, nrg_res_out, 4 * sizeof(int32_t));
    cand->pitch.voiced = false;
    cand->silent = false;
}

/* ══════════════════════════════════════════════════════════════════════════════
 * smplVoicedDecisionForLag (smplVoicedDecisionForLag)
 * ══════════════════════════════════════════════════════════════════════════════ */

void smpl_voiced_decision_for_lag(int blockseg_idx, const int32_t laginds[8],
                                   celp_frame_ctx_t *cs, float lags8_out[8],
                                   voiced_decision_t *vd) {
    float block_lags8[8];
    for (int b = 0; b < 8; b++) {
        float v = (float)laginds[b] * 0.5f + 32.0f;
        if (v > 320.0f) v = 320.0f;
        block_lags8[b] = v;
    }
    memcpy(lags8_out, block_lags8, 8 * sizeof(float));

    for (int sf = 0; sf < SMPL_SUBFR_COUNT; sf++) {
        cs->block_lags[sf][0] = block_lags8[2 * sf];
        cs->block_lags[sf][1] = block_lags8[2 * sf + 1];
    }

    float mean_lag = 0.0f;
    for (int i = 0; i < 8; i++) mean_lag += block_lags8[i];
    mean_lag /= 8.0f;

    memset(vd, 0, sizeof(*vd));
    for (int i = 0; i < 4; i++) { vd->pp.gain_idx[i] = 5; vd->pp.filt_idx[i] = -1; }
    vd->pp.blockseg_idx = blockseg_idx;
    memcpy(vd->pp.laginds, laginds, 8 * sizeof(int32_t));
    vd->pitch.voiced = true;
    for (int i = 0; i < 4; i++) vd->pitch.lag_subfr[i] = (double)mean_lag;
    vd->pitch.norm_gain = SMPL_VOICED_NORM_GAIN;
}

/* ══════════════════════════════════════════════════════════════════════════════
 * smplVoicedCandidate (smplVoicedCandidate)
 * ══════════════════════════════════════════════════════════════════════════════ */

void smpl_voiced_candidate(const double *win, const float *prev_nlsf,
                           front_end_lsf_t *fe, celp_frame_ctx_t *cs,
                           const voiced_decision_t *vd, candidate_t *cand) {
    memset(cand, 0, sizeof(*cand));

    /* winN = float32(win / 32768.0) */
    float win_n[320 + SMPL_ORDER];
    for (int i = 0; i < (int)(SMPL_ORDER + SMPL_INTF_LEN); i++)
        win_n[i] = (float)(win[i] / 32768.0);

    /* quantize(voiced=1) */
    int32_t bgrid; int32_t bsym[16]; float brec[16]; float predcoef_q[17];
    front_end_quantize(fe, 1, prev_nlsf, &bgrid, bsym, brec, predcoef_q);

    /* smplLPCInterpol(brec, prev_lsfq, SmplNLSF2A) at idx 0 */
    float predcoefs[4][17]; float ilsf_out[16];
    smpl_lpc_interpol(brec, fe->prev_lsfq, 0, predcoefs, ilsf_out);

    /* Analysis residual */
    float res_lpc[320];
    for (int sf = 0; sf < SMPL_SUBFR_COUNT; sf++)
        smpl_analysis_residual_subfr(predcoefs[sf], win_n, sf, res_lpc + sf * SMPL_SUBFR_LEN);

    float emph_v[2] = SMPL_PERC_EMPH_V;
    int16_t acb[4], gain_i[4], np[4], all_pulses[4][40];
    float exc_lpc[320];
    run_celp_subframes(cs, predcoefs, res_lpc, cs->block_lags, (const float**)cs->perc_corrs,
                       emph_v, 1, acb, gain_i, all_pulses, np, exc_lpc);

    /* Build pulse vector */
    int32_t *pulse_vec = (int32_t *)calloc(SMPL_INTF_LEN, sizeof(int32_t));
    int32_t acbg[4], fcbg[4];
    for (int sf = 0; sf < SMPL_SUBFR_COUNT; sf++) {
        for (int i = 0; i < (int)np[sf]; i++) {
            int16_t v = all_pulses[sf][i];
            int sign = (v > 0) ? 1 : -1;
            int pos = (v > 0) ? (int)v - 1 : -(int)v - 1;
            if (pos >= 0 && pos < SMPL_SUBFR_LEN)
                pulse_vec[sf * SMPL_SUBFR_LEN + pos] += sign;
        }
        int32_t ai = (int32_t)acb[sf];
        if (ai < 0) ai = 0; if (ai > 15) ai = 15;
        acbg[sf] = ai;
        int32_t fi = (int32_t)gain_i[sf];
        if (fi < 0) fi = 0;
        fcbg[sf] = fi;
    }

    smpl_pulse_params_t pp;
    smpl_build_pulse_params(pulse_vec, &pp);

    /* Build candidate params */
    cand->ip.lsf.stage1 = 1;
    cand->ip.lsf.grid = bgrid;
    cand->ip.lsf.extra = 0;
    memcpy(cand->ip.lsf.stage2, bsym, 16 * sizeof(int32_t));
    cand->ip.pulses = pp;
    cand->ip.has_pitch = true;
    cand->ip.pitch = vd->pp;
    for (int sf = 0; sf < 4; sf++) {
        cand->ip.pitch.gain_idx[sf] = acbg[sf];
        cand->ip.pitch.filt_idx[sf] = (pp.subfr[sf] > 0) ? fcbg[sf] : -1;
    }
    cand->stage1 = 1;
    cand->grid = bgrid;
    memcpy(cand->qsym, bsym, 16 * sizeof(int32_t));
    cand->pulse_vec = pulse_vec;
    memset(cand->gain_q, 0, sizeof(cand->gain_q));
    cand->pitch = vd->pitch;
    cand->silent = false;
}

/* ══════════════════════════════════════════════════════════════════════════════
 * smplReplayPitchState (smplReplayPitchState)
 * ══════════════════════════════════════════════════════════════════════════════ */

void smpl_replay_pitch_state(smpl_lsf_state_t *st, int32_t p3,
                              const int32_t subfr_counts[4],
                              const smpl_pitch_params_t *pp) {
    int take = (int)p3;
    if (take > 4) take = 4;
    for (int sf = 0; sf < take; sf++) {
        st->prev_gain_idx = pp->gain_idx[sf];
        if (subfr_counts[sf] > 0) st->prev_filt_idx = pp->filt_idx[sf];
    }
    /* smplLagsPredictorAfter: update PrevLagblk/PrevLagidx */
    int32_t nblk, nidx;
    smpl_lags_predictor_after(pp->blockseg_idx, pp->laginds, &nblk, &nidx);
    st->prev_lagblk = nblk;
    st->prev_lagidx = nidx;
}

/* ══════════════════════════════════════════════════════════════════════════════
 * synthInternalFrame (SynthInternalFrame)
 * ══════════════════════════════════════════════════════════════════════════════ */

void synth_internal_frame(smpl_frame_synth_t *st, int stage1, int config,
                          int grid, const int32_t stage2[16],
                          const float *prev_nlsf, const int32_t *pulses,
                          const int32_t gain_q[4], const smpl_pitch_synth_t *pitch,
                          float *signal_out, float *nlsf_out) {
    /* Reconstruct NLSF */
    smpl_reconstruct_nlsf(nlsf_out, stage1, config, grid, stage2, prev_nlsf);
    float a[17];
    smpl_nlsf2a(a, nlsf_out, SMPL_LPC_ORDER);
    a[0] = 1.0f;

    /* Build excitation */
    float ex[320];
    for (int n = 0; n < SMPL_INTF_LEN; n++) {
        double sub_gain = smpl_gain_lin(gain_q[n / SMPL_SUBFR_LEN]) * (double)SMPL_SUBFR_LEN;
        ex[n] = (float)((double)pulses[n] * sub_gain);
    }

    float *hist = st->ltp_hist;
    static const float g_ltp = 0.949999988079071f;

    if (pitch && pitch->voiced) {
        float gain_frac = smpl_ltp_frac_gain(pitch->norm_gain);
        smpl_exc_gain_state_t gst = {0, 0};
        for (int sf = 0; sf < SMPL_SUBFR_COUNT; sf++) {
            float lag_f = (float)pitch->lag_subfr[sf];
            int int_lag = (int)lag_f;
            if (int_lag <= 0) {
                int from = sf * SMPL_SUBFR_LEN;
                int to = (sf + 1) * SMPL_SUBFR_LEN;
                memcpy(hist + SMPL_LTP_HIST + from, ex + from,
                       (to - from) * sizeof(float));
                continue;
            }
            int ex_base = sf * SMPL_SUBFR_LEN;
            int hist_pos = SMPL_LTP_HIST + ex_base;
            if (int_lag > 0 && int_lag < SMPL_SUBFR_LEN) {
                for (int n = int_lag; n < SMPL_SUBFR_LEN; n++)
                    ex[ex_base + n] += g_ltp * ex[ex_base + n - int_lag];
            }
            float pred_out[80];
            smpl_ltp_subframe_pred(hist, hist_pos, lag_f, gain_frac, &gst, pred_out);
            for (int n = 0; n < SMPL_SUBFR_LEN; n++)
                ex[ex_base + n] += pred_out[n];
            memcpy(hist + hist_pos, ex + ex_base, SMPL_SUBFR_LEN * sizeof(float));
        }
    } else {
        memcpy(hist + SMPL_LTP_HIST, ex, SMPL_INTF_LEN * sizeof(float));
    }

    /* LPC synthesis */
    smpl_lpc_synthesis(ex, a, signal_out, st->lpc_state, SMPL_INTF_LEN);

    /* Roll LTP history forward */
    memmove(hist, hist + SMPL_INTF_LEN,
            (SMPL_LTP_HIST + SMPL_INTF_LEN - SMPL_INTF_LEN) * sizeof(float));
    int clear_start = SMPL_LTP_HIST + SMPL_INTF_LEN;
    if (clear_start < 0) clear_start = 0;
    int clear_end = LTP_HIST_LEN;
    if (clear_start < clear_end)
        memset(hist + clear_start, 0, (clear_end - clear_start) * sizeof(float));
}

/* ══════════════════════════════════════════════════════════════════════════════
 * smplAnalyzeInternal (smplAnalyzeInternal)
 * ══════════════════════════════════════════════════════════════════════════════ */

void smpl_analyze_internal(smpl_frame_synth_t *shadow, smpl_lsf_state_t *lstate,
                           int intf, const double *win, const float *win_n,
                           const float *prev_nlsf, front_end_lsf_t *fe,
                           celp_frame_ctx_t *cs, smpl_internal_params_t *ip_out,
                           float *nlsf_out, bool *voiced_out) {
    /* computePercCorrs */
    float *corrs[4] = {NULL, NULL, NULL, NULL};
    compute_perc_corrs(cs, corrs);
    /* Save to ctx so candidates can reuse */
    for (int i = 0; i < 4; i++) cs->perc_corrs[i] = corrs[i];

    /* buildLtpBuf */
    build_ltp_buf(cs, (const float**)corrs);

    /* SmplPitch */
    float pitchcorr, lags8[8], avg_lag, harm_strength;
    int blockseg_idx; int32_t laginds[8];
    smpl_pitch_run(cs->pitch_prev_lag, cs->pitch_prev_corr,
                   cs->pitch_prev_lagblk, cs->pitch_prev_lagidx,
                   cs->ltp_buf, cs->f2, cs->coded_as_active_voice,
                   &pitchcorr, lags8, &avg_lag, &harm_strength,
                   &blockseg_idx, laginds);

    /* SmplGetSignalMode */
    float vstr = smpl_get_signal_mode(pitchcorr, lags8, avg_lag, harm_strength,
                                       cs->f2, cs->sp_act_prob, cs->vuv);
    cs->voicing_strength = vstr;
    bool is_voiced = (vstr > 0.0f) && cs->coded_as_active_voice;

    if (is_voiced) lstate->prev_lag_samples = lags8[0];
    else lstate->prev_lag_samples = 0.0f;

    /* voiced LSF state */
    smpl_lsf_state_t voiced_lstate = *lstate;
    /* SmplAdvanceLsfState(&voicedLstate, intf, 1) */
    {
        bool m = (intf != 0 && 1 == voiced_lstate.prev_stage1);
        if (!m) {
            voiced_lstate.prev_gain_idx = -1; voiced_lstate.prev_filt_idx = -1;
            voiced_lstate.prev_lag = -1; voiced_lstate.prev_frac_lag = -1;
            voiced_lstate.prev_lagblk = -1; voiced_lstate.prev_lagidx = -1;
        }
        voiced_lstate.prev_stage1 = 1;
        voiced_lstate.prev_match = m;
        voiced_lstate.have_prev = true;
    }

    bool have_voiced = false;
    voiced_decision_t vd;
    if (is_voiced) {
        smpl_voiced_decision_for_lag(blockseg_idx, laginds, cs, lags8, &vd);
        have_voiced = true;
    }

    candidate_t chosen;
    bool chosen_voiced;
    if (have_voiced) {
        smpl_voiced_candidate(win, prev_nlsf, fe, cs, &vd, &chosen);
        chosen_voiced = true;
    } else {
        smpl_unvoiced_candidate(win, win_n, prev_nlsf, fe, cs, &chosen);
        chosen_voiced = false;
    }

    /* commitCandidate */
    float committed_nlsf[16];
    commit_candidate(shadow, &chosen, prev_nlsf, committed_nlsf);

    /* Update LSF state */
    if (chosen.stage1 == 1) {
        *lstate = voiced_lstate;
        smpl_replay_pitch_state(lstate, 4, chosen.ip.pulses.subfr, &chosen.ip.pitch);
    } else {
        /* SmplAdvanceLsfState(lstate, intf, chosen.stage1) */
        bool m = (intf != 0 && chosen.stage1 == lstate->prev_stage1);
        if (!m) {
            lstate->prev_gain_idx = -1; lstate->prev_filt_idx = -1;
            lstate->prev_lag = -1; lstate->prev_frac_lag = -1;
            lstate->prev_lagblk = -1; lstate->prev_lagidx = -1;
        }
        lstate->prev_stage1 = chosen.stage1;
        lstate->prev_match = m;
        lstate->have_prev = true;
    }

    *ip_out = chosen.ip;
    memcpy(nlsf_out, committed_nlsf, 16 * sizeof(float));
    *voiced_out = chosen_voiced;

    for (int i = 0; i < 4; i++) free(corrs[i]);
}

/* ══════════════════════════════════════════════════════════════════════════════
 * smplAnalyzeFrameSt (smplAnalyzeFrameSt)
 * ══════════════════════════════════════════════════════════════════════════════ */

void smpl_analyze_frame_st(smpl_encoder_state_t *es, const float *pcm, smpl_frame_params_t *fp) {
    memset(fp, 0, sizeof(*fp));
    fp->toc = 0x50; fp->config = 0;

    int need = SMPL_INTF_LEN * 3; /* 960 */

    /* ── VAD ── */
    int16_t pcm_i16[960];
    for (int i = 0; i < need; i++) {
        double v = round(pcm[i] * 32768.0);
        if (v > 32767.0) v = 32767.0;
        if (v < -32768.0) v = -32768.0;
        pcm_i16[i] = (int16_t)v;
    }
    if (!es->vad_state) es->vad_state = vad_state_new();
    float sp_act_prob_arr[3];
    bool coded_as_active_voice;
    vad_process_packet(es->vad_state, pcm_i16, SMPL_INTF_LEN,
                       sp_act_prob_arr, &coded_as_active_voice);

    /* ── HP filter ── */
    if (!es->hp_set) {
        /* Compute HP coeffs for fcorner=35Hz */
        float fc = 35.0f / 16000.0f; /* normalized frequency */
        float maf = 0.1f;
        float arf[2] = {0.728508218f, 0.476039848f};
        float arr[2] = {-4.363803713f, 8.441854006f};
        float maf_f = maf * fc;
        float cos_ma = 1.0f - 0.5f * (2.0f*3.141592653f*maf_f) * (2.0f*3.141592653f*maf_f);
        es->hp_ma[0] = 1.0f; es->hp_ma[1] = -2.0f * cos_ma; es->hp_ma[2] = 1.0f;
        float far = arf[0]*fc + arf[1]*fc*fc;
        float rar = arr[0]*fc + arr[1]*fc*fc;
        float cos_ar = 1.0f - 0.5f * (2.0f*3.141592653f*far) * (2.0f*3.141592653f*far);
        es->hp_ar[0] = 1.0f;
        es->hp_ar[1] = -2.0f * cos_ar * (1.0f + rar);
        es->hp_ar[2] = 1.0f + (2.0f*rar + rar*rar);
        float sc = (1.0f - es->hp_ar[1] + es->hp_ar[2]) / (1.0f - es->hp_ma[1] + es->hp_ma[2]);
        es->hp_ma[0] *= sc; es->hp_ma[1] *= sc; es->hp_ma[2] *= sc;
        es->hp_set = true;
    }
    float *hp = es->scratch_hp;
    { float s0=es->hp_state[0],s1=es->hp_state[1],s2=es->hp_state[2],s3=es->hp_state[3];
    for (int i=0;i<need;i++) { float in=pcm[i]; float out=es->hp_ma[0]*in+es->hp_ma[1]*s0+es->hp_ma[2]*s1-es->hp_ar[1]*s2-es->hp_ar[2]*s3; s1=s0;s0=in;s3=s2;s2=out; hp[i]=out; }
    es->hp_state[0]=s0;es->hp_state[1]=s1;es->hp_state[2]=s2;es->hp_state[3]=s3; }

    /* ── x = float64(hp) * 32768 ── */
    int xlen = SMPL_ORDER + need;
    double *x = es->scratch_x;
    if (es->hist && es->hist_len >= SMPL_ORDER)
        memcpy(x, es->hist + es->hist_len - SMPL_ORDER, SMPL_ORDER * sizeof(double));
    else
        memset(x, 0, SMPL_ORDER * sizeof(double));
    for (int i = 0; i < need; i++)
        x[SMPL_ORDER + i] = (double)hp[i] * 32768.0;

    /* ── Shadow synth ── */
    smpl_frame_synth_t shadow;
    memset(&shadow, 0, sizeof(shadow));
    memset(shadow.ltp_hist, 0, LTP_HIST_LEN * sizeof(float));

    /* ── Lazy init ── */
    if (!es->celp_enc)
        es->celp_enc = celp_encoder_new(false, SMPL_CELP_PERC_RESP_LEN, SMPL_SUBFR_LEN, 12);
    if (!es->perc_model)
        es->perc_model = perc_model_new();
    if (!es->bitrate_ctrl)
        es->bitrate_ctrl = bitrate_ctrl_new();

    /* ── xn (resampled history) ── */
    int res_lead = SMPL_ORDER + SMPL_WINNEXT_WB_LEN;
    float *xn = es->scratch_xn;
    memset(xn, 0, (res_lead + need) * sizeof(float));
    if (es->hist && es->hist_len >= res_lead) {
        for (int i = 0; i < res_lead; i++)
            xn[i] = (float)(es->hist[es->hist_len - res_lead + i] / 32768.0);
    }
    memcpy(xn + res_lead, hp, need * sizeof(float));

    /* ── hpFull = lpc_hist + hp ── */
    int hpFullLen = SMPL_LPC_HIST_LEN + need + SMPL_WINNEXT_WB_LEN;
    float *hpFull = es->scratch_hpFull;
    memcpy(hpFull, es->lpc_hist, SMPL_LPC_HIST_LEN * sizeof(float));
    memcpy(hpFull + SMPL_LPC_HIST_LEN, hp, need * sizeof(float));

    /* ── hpPitchHist ── */
    float hp_pitch_hist[SMPL_PITCH_LAG_MAX];
    memcpy(hp_pitch_hist, es->hp_pitch_hist, SMPL_PITCH_LAG_MAX * sizeof(float));
    memcpy(es->hp_pitch_hist, hp + need - SMPL_PITCH_LAG_MAX, SMPL_PITCH_LAG_MAX * sizeof(float));

    /* ── ltpBuf init ── */
    if (!es->ltp_buf) {
        es->ltp_buf = (float *)calloc(MAX_LTP_BUF_LEN, sizeof(float));
    }

    float prev_lsfq[16];
    memcpy(prev_lsfq, es->prev_lsfq, 16 * sizeof(float));
    bool prev_voiced = es->prev_voiced;

    /* ── LSF state for entropy predictor ── */
    smpl_lsf_state_t lstate;
    memset(&lstate, 0, sizeof(lstate));
    lstate.prev_stage1 = -1;
    lstate.prev_gain_idx = -1; lstate.prev_filt_idx = -1;
    lstate.prev_lag = -1; lstate.prev_frac_lag = -1;
    lstate.prev_lagblk = -1; lstate.prev_lagidx = -1;

    /* ── Per-frame loop ── */
    for (int f = 0; f < 3; f++) {
        int base = SMPL_ORDER + f * SMPL_INTF_LEN;
        int nbase = res_lead + f * SMPL_INTF_LEN;

        /* LPC analysis */
        int lpcStart = SMPL_LPC_HIST_LEN - SMPL_LPC_PRE + f * SMPL_INTF_LEN;
        float lpcbuf[SMPL_LPC_BUF_LEN];
        memcpy(lpcbuf, hpFull + lpcStart, SMPL_LPC_BUF_LEN * sizeof(float));
        float windowed[SMPL_LPC_BUF_LEN];
        smpl_window_lpc20(lpcbuf, f < 2, windowed);
        float a[17], f2[SMPL_F_LEN];
        smpl_lpc_analyze_with_f2(windowed, a, f2);
        float nlsf[16];
        smpl_a2nlsf16(a, nlsf);

        /* Build celpFrameCtx */
        celp_frame_ctx_t cs;
        memset(&cs, 0, sizeof(cs));
        cs.celp = es->celp_enc;
        cs.perc = es->perc_model;
        cs.perc_prev = es->perc_prev;  /* pointer — writes by compute_perc_corrs go to es */
        cs.bitrate = es->bitrate_ctrl;
        cs.hp_n = hp;
        cs.intf = f;
        cs.sp_act_prob = sp_act_prob_arr[f];
        cs.coded_as_active_voice = coded_as_active_voice;
        memcpy(cs.f2, f2, SMPL_F_LEN * sizeof(float));
        cs.vuv = &es->vuv;
        memcpy(cs.hp_pitch_hist, hp_pitch_hist, SMPL_PITCH_LAG_MAX * sizeof(float));
        cs.ltp_buf = es->ltp_buf;
        cs.pitch_prev_lag = &es->prev_lag_est;
        cs.pitch_prev_corr = &es->prev_pitch_corr_est;
        cs.pitch_prev_lagblk = &es->prev_lagblk_est;
        cs.pitch_prev_lagidx = &es->prev_lagidx_est;

        /* Build frontEndLsf */
        front_end_lsf_t fe;
        memcpy(fe.a, a, 17 * sizeof(float));
        memcpy(fe.nlsf, nlsf, 16 * sizeof(float));
        fe.prev_lsfq = prev_lsfq;
        fe.prev_voiced = prev_voiced;
        fe.intf = f;

        /* smplAnalyzeInternal */
        smpl_internal_params_t ip;
        float nlsf_out[16];
        bool voiced_out;
        smpl_analyze_internal(&shadow, &lstate, f,
                              x + base - SMPL_ORDER, xn + nbase - res_lead,
                              prev_lsfq, &fe, &cs, &ip, nlsf_out, &voiced_out);

        memcpy(prev_lsfq, nlsf_out, 16 * sizeof(float));
        prev_voiced = voiced_out;
        fp->internal[f] = ip;
    }


    /* ── Update encoder state ── */
    int tail_len = SMPL_ORDER + SMPL_WINNEXT_WB_LEN;
    if (!es->hist || es->hist_cap < tail_len) {
        es->hist = (double *)realloc(es->hist, tail_len * sizeof(double));
        es->hist_cap = tail_len;
    }
    memcpy(es->hist, x + xlen - tail_len, tail_len * sizeof(double));
    es->hist_len = tail_len;

    memcpy(es->lpc_hist, hp + need - SMPL_LPC_HIST_LEN, SMPL_LPC_HIST_LEN * sizeof(float));
    memcpy(es->prev_lsfq, prev_lsfq, 16 * sizeof(float));
    es->prev_voiced = prev_voiced;

    /* No frees needed �?all scratch pre-allocated */
}

/* ══════════════════════════════════════════════════════════════════════════════
 * State lifecycle
 * ══════════════════════════════════════════════════════════════════════════════ */

void smpl_encoder_state_init(smpl_encoder_state_t *es) {
    memset(es, 0, sizeof(*es));
    es->prev_lsfq = (float *)calloc(16, sizeof(float));
    es->ltp_buf = (float *)calloc(MAX_LTP_BUF_LEN, sizeof(float));
    es->hist = NULL; es->hist_len = 0; es->hist_cap = 0;
}

void smpl_encoder_state_reset(smpl_encoder_state_t *es) {
    if (es->prev_lsfq) memset(es->prev_lsfq, 0, 16 * sizeof(float));
    if (es->ltp_buf) memset(es->ltp_buf, 0, MAX_LTP_BUF_LEN * sizeof(float));
    es->prev_voiced = false;
    es->hp_set = false;
    memset(es->hp_state, 0, sizeof(es->hp_state));
    memset(es->lpc_hist, 0, sizeof(es->lpc_hist));
    memset(es->hp_pitch_hist, 0, sizeof(es->hp_pitch_hist));
    memset(&es->vuv, 0, sizeof(es->vuv));
    es->prev_lag_est = 0; es->prev_pitch_corr_est = 0;
    es->prev_lagblk_est = -1; es->prev_lagidx_est = -1;
}

void smpl_encoder_state_free(smpl_encoder_state_t *es) {
    if (es->prev_lsfq) { free(es->prev_lsfq); es->prev_lsfq = NULL; }
    if (es->ltp_buf) { free(es->ltp_buf); es->ltp_buf = NULL; }
    if (es->hist) { free(es->hist); es->hist = NULL; }
}
