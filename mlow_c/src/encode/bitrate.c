/*
 * bitrate.c �?Bitrate controller for CELP encoding.
 */
#include "encode.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#define SMPL_E 2.718281828459045f

/* ── Table constants ────────────────────────────────────────────────────────── */
static const uint8_t smpl_max_pulses_per_frame[2][3] = {{80, 160, 160}, {16, 32, 32}};
#define FRAME_BG_NOISE  0
#define FRAME_UNVOICED  1
#define FRAME_VOICED    2
#define SMPL_RATE_CONT_SCALE 26.0f

static const float smpl_rate_control_model_comp5[4][2][8] = {
    {
        {5.166876656946171f, -8.981699804753452f, 0.07280811614105594f, 0.1301196310618402f, -0.01597680442864421f, 1.7601470147884113f, -3.8161195433141755f, 0.3038629198331684f},
        {-71.71229978402292f, 14.197572549553076f, -0.9863630205846172f, 0.032124893286072924f, -0.0003538411576874928f, 1.803705259861388e-11f, 10.0f, 1.2454667523627154f},
    },
    {
        {32.5371190670542f, -41.270234279452104f, 10.490270829170875f, -1.102121269442237f, 0.03848319274046071f, 3.405326741403831f, -5.102658181889428f, 0.2141935195026695f},
        {-177.10486363500775f, 43.952329593498376f, -3.7049735533247454f, 0.14239771116996938f, -0.001919963993993193f, 7.953695588409639e-6f, 5.220317075476664f, 0.6435364076926223f},
    },
    {
        {-79.2663194911617f, 45.00981883522089f, -10.063311543498518f, 1.2311531056576501f, -0.06023559069137118f, 0.059204788212259364f, 3.033961466462233f, 1.0111383197827808f},
        {-122.04861900525415f, 31.62096398905459f, -2.613237037423586f, 0.10050433143234094f, -0.0013233009240188039f, 2.14859438836692e-7f, 1.9077791307787761f, 0.7059420500333776f},
    },
    {
        {-182.64255084224325f, 122.90780796179816f, -31.308790671748525f, 3.7850563849431462f, -0.1750480676903051f, 0.05399618467364628f, 3.009451055091342f, 1.1243365512229038f},
        {-132.4565456943888f, 34.361297004632966f, -2.7956546289118887f, 0.10428149547078584f, -0.001322667891395693f, 2.678747426340249e-6f, 6.9940208056381925f, 0.7551244069345737f},
    },
};

static const uint16_t smpl_rate_control_thrs_comp5[4][2] = {
    {7500, 10000}, {4500, 5750}, {4000, 5000}, {4000, 4750}
};

/* ── BitrateController state ────────────────────────────────────────────────── */
typedef struct {
    int32_t prev_voiced;
    float   rate_cont_wnrg_smth;
    float   rate_cont_bitrate_scale[2];
    float   bitrate_delta_smth[2];
    float   rate_cont_bitrate[2];
    float   adjustment_factor[2];
} BitrateController;

/* ── Helpers ────────────────────────────────────────────────────────────────── */
static float max_f32(float a, float b) { return a > b ? a : b; }

static int32_t bool_to_int(bool b) { return b ? 1 : 0; }

static float smpl_sigmoid_bc(float x) {
    return 1.0f / (1.0f + expf(-x));
}

static float bitrate2pulses(float rate_kbps, const float coeff[8]) {
    float rx = rate_kbps;
    return coeff[0] +
        coeff[1]*rx +
        coeff[2]*rx*rx +
        coeff[3]*rx*rx*rx +
        coeff[4]*rx*rx*rx*rx +
        coeff[5]*powf(SMPL_E, (rx-coeff[6])*coeff[7]);
}

static float bitrate2pulses_hr_fec(float rate_kbps, const float coeff[8], float one_pulse_rate_bps) {
    const float rate_thres_kbps = 9.0f;
    if (rate_kbps >= rate_thres_kbps) {
        return bitrate2pulses(rate_kbps, coeff);
    } else if (one_pulse_rate_bps >= rate_thres_kbps*1000.0f) {
        return 1.0f;
    }
    float pulses_thres = bitrate2pulses(rate_thres_kbps, coeff);
    float sc = (rate_thres_kbps - rate_kbps) / (rate_thres_kbps - one_pulse_rate_bps/1000.0f);
    return pulses_thres - sc*(pulses_thres - 1.0f);
}

/* ── smplDistributeFcbSurv ──────────────────────────────────────────────────── */
void smpl_distribute_fcb_surv(int16_t *numsurv, int32_t max_pulses, int32_t tot_surv) {
    if (max_pulses <= 1) { numsurv[0] = 1; return; }
    for (int i = 0; i < (int)max_pulses; i++) numsurv[i] = 1;
    int32_t sum_surv = max_pulses;
    int32_t extra_surv = tot_surv - max_pulses;
    int32_t extra = extra_surv / (max_pulses - 1);
    if (extra > FCB_SRV_MAX - 1) extra = FCB_SRV_MAX - 1;
    for (int i = 0; i < (int)(max_pulses - 1); i++) numsurv[i] += (int16_t)extra;
    sum_surv += extra * (max_pulses - 1);
    int32_t ix = max_pulses - 2;
    while (sum_surv < tot_surv) {
        if ((int32_t)numsurv[ix] < FCB_SRV_MAX) { numsurv[ix]++; sum_surv++; }
        ix--;
        if (ix < 0) break;
    }
}

/* ── Public API ─────────────────────────────────────────────────────────────── */

void *bitrate_ctrl_new(void) {
    BitrateController *bc = calloc(1, sizeof(BitrateController));
    if (!bc) return NULL;
    for (int i = 0; i < 2; i++) bc->adjustment_factor[i] = 1.0f;
    /* rate_cont_bitrate initialized to 0 so first comparison triggers scale update */
    return bc;
}

void bitrate_ctrl_free(void *bc) { free(bc); }

void bitrate_ctrl_control(void *bc, int max_pulses[2], float *importance,
                          bool coded_as_active, float sp_act_prob,
                          float nonflatness, float voicing_strength,
                          int voiced, float wnrg, float wnrg_next) {
    BitrateController *b = (BitrateController *)bc;
    if (!b) { max_pulses[0] = max_pulses[1] = 5; *importance = 1.0f; return; }

    /* Fixed inputs matching enc struct */
    int32_t internal_sample_rate = 16000;
    int32_t payload_size_ms = 60;
    int32_t fec_bit_rate = 0;
    int32_t main_bit_rate = SMPL_MAIN_BIT_RATE;
    int32_t complexity = SMPL_COMPLEXITY;
    int32_t use_fec_rate_compensation = 0;
    int32_t use_dtx = 0;
    float subframe_importance_factor = 1.0f;
    int32_t dtx_sid_frame = 0;
    int32_t low_rate = 0;
    int32_t framelen = 320;
    int32_t subfrlen = SMPL_SUBFR_LEN;

    int32_t bwe_bitrate = 0;
    if (internal_sample_rate > 16000) {
        if (low_rate != 0) bwe_bitrate += 450;
        else bwe_bitrate += 750;
        if (payload_size_ms == 10) bwe_bitrate += 450;
    }

    b->rate_cont_wnrg_smth += 0.6f * (wnrg - b->rate_cont_wnrg_smth);

    int framelen_idx = 2; /* 60ms */
    int start_r = 0;
    if ((SMPL_CELP_IDX_FEC + bool_to_int(fec_bit_rate == 0)) != 0 || fec_bit_rate == main_bit_rate)
        start_r = 1;

    int lr_idx = 1; /* not low_rate */

    for (int r = start_r; r <= SMPL_CELP_IDX_MAIN; r++) {
        float bit_rate = (float)main_bit_rate;
        if (r == SMPL_CELP_IDX_FEC) bit_rate = (float)fec_bit_rate;
        if (bit_rate > 30000.0f) bit_rate = 30000.0f;

        float rate_kbps = (bit_rate - (float)bwe_bitrate) / 1000.0f;
        if (low_rate == 0) {
            if (complexity == 1 || complexity == 2) rate_kbps *= 0.9900990f;
            else if (complexity == 3 || complexity == 4) rate_kbps *= 1.0101010f;
        }

        float pulses_per_20ms_target_max;
        float rate_control_thrs = (float)smpl_rate_control_thrs_comp5[framelen_idx][lr_idx];
        if ((bit_rate - (float)bwe_bitrate) < rate_control_thrs) {
            pulses_per_20ms_target_max = 1.0f;
        } else {
            const float *coeff = smpl_rate_control_model_comp5[framelen_idx][lr_idx];
            if (r == SMPL_CELP_IDX_FEC && low_rate == 0 && use_fec_rate_compensation != 0) {
                pulses_per_20ms_target_max = max_f32(bitrate2pulses_hr_fec(rate_kbps, coeff, rate_control_thrs), 1.0f);
            } else {
                pulses_per_20ms_target_max = max_f32(bitrate2pulses(rate_kbps, coeff), 1.0f);
            }
        }

        float rel_pulserate = pulses_per_20ms_target_max / 16.0f * (320.0f / (float)framelen);
        float rel_pulserate_log = logf(rel_pulserate);
        if (b->rate_cont_bitrate[r] != bit_rate) {
            float bitrate_scale = SMPL_RATE_CONT_SCALE * rel_pulserate * (1.0f + 0.4f*rel_pulserate_log*rel_pulserate_log);
            b->rate_cont_bitrate_scale[r] = bitrate_scale;
            b->rate_cont_bitrate[r] = bit_rate;
        }

        int32_t numsubfrs = framelen / subfrlen;
        int32_t mpps = 1 + (int32_t)roundf(pulses_per_20ms_target_max * (1.0f + 0.5f) / (float)numsubfrs);
        if (use_dtx != 0 && dtx_sid_frame != 0) {
            mpps = 0;
        } else {
            mpps = (int32_t)roundf((float)mpps * (0.5f + 0.5f*sqrtf(sp_act_prob + 1e-12f)));
            int frame_type = FRAME_BG_NOISE;
            if (coded_as_active) {
                if (voiced == 1) frame_type = FRAME_VOICED;
                else frame_type = FRAME_UNVOICED;
            }
            int32_t max_pulses_frame = (int32_t)smpl_max_pulses_per_frame[low_rate][frame_type] * framelen / 320;
            int32_t m = max_pulses_frame / numsubfrs;
            if (mpps > m) mpps = m;
        }
        max_pulses[r] = (int)mpps;

        float imp = (wnrg + 0.01f*wnrg_next) / (b->rate_cont_wnrg_smth + 0.02f*wnrg_next + 1e-12f);
        if (voiced != 0) {
            if (bit_rate <= 9000.0f)
                imp = sqrtf(imp + 1e-12f);
        } else {
            imp *= 0.9f + 0.3f*smpl_sigmoid_bc(nonflatness - 2.0f);
            imp *= 0.8f;
        }
        if ((int32_t)voiced != b->prev_voiced) imp *= 1.1f;
        imp *= 0.9f + 0.3f*1.0f/(1.0f + 25.0f*voicing_strength*voicing_strength);

        float imp_factor = subframe_importance_factor;
        if (imp_factor <= 1.0f) {
            imp *= (1.0f - imp_factor) + imp_factor*sqrtf(sp_act_prob + 1e-12f);
        } else if (imp_factor <= 2.0f) {
            imp_factor -= 1.0f;
            imp *= (1.0f - imp_factor) + imp_factor*sp_act_prob;
        } else {
            imp_factor -= 2.0f;
            imp *= (1.0f - imp_factor) + imp_factor*sp_act_prob*sp_act_prob;
        }
        imp *= b->adjustment_factor[r] * b->rate_cont_bitrate_scale[r];
        importance[r] = imp;
        b->prev_voiced = (int32_t)voiced;
    }
}
