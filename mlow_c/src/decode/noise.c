/*
 * noise.c — CELP decoder-side noise generator.
 */

#include "decode.h"
#include "../seed.h"
#include <math.h>
#include <string.h>
#include <stdlib.h>

/* ── Constants ──────────────────────────────────────────────────────────────── */
#define SMPL_MAX_SF_LEN      160
#define SMPL_NOISE_CORR_ORDER 2
#define SMPL_NOISE_DCT_ORDER  16
#define SMPL_CELP_FS_KHZ     16
#define SMPL_PI_NOISE        3.1415926535897f

static const float DEC_NOISE_V_NOISE_GAIN  = 0.35f;
static const float DEC_NOISE_UV_NOISE_GAIN = 0.8f;
static const float DEC_NOISE_UV_FCORNER_HZ = 800.0f;
static const float ENV_SMTH_COEF_V         = 0.95f;
static const float ENV_SMTH_COEF_UV        = 0.995f;
static const float ENV_SMTH_COEF_UVV       = 0.99f;
static const float SMPL_RES_NRG_BIAS      = 3.1622776e-9f;
static const float SMPL_RES_NRG_MIN_DB    = -85.0f;
static const float SMPL_RES_NRG_MAX_DB    = 0.0f;
static const int32_t SMPL_NRG_STEP_DB_Q14_4 = 16686;

static const float COEF_MA_V[3] = {0.25f, -0.496f, 0.25f};

/* nrgresShapeCB4Q10: 98 vectors x 4 subframes */
static const int16_t nrgres_shape_cb4_q10[98 * 4] = {
    -2515, -2238, 2632, 2121, 790, 3973, -2872, -1891, -533, 2847, 1453, -3767, -6174, -402, 2668, 3908,
    -1623, -1458, 153, 2928, -1254, 3197, -476, -1467, 1803, -1086, 270, -987, 1952, -66, -1257, -629,
    161, 19, -85, -96, 4833, 3147, -105, -7875, -1320, 1377, -1156, 1099, 3398, -2247, 1485, -2637,
    -3031, 2756, 1841, -1566, -1487, 2202, -2668, 1954, 5518, -5344, 522, -696, 8400, -3123, -6235, 958,
    5152, -2444, -2811, 102, 2513, -82, 1181, -3612, -561, -197, -1074, 1832, -294, -1250, -1839, 3383,
    5126, 522, -782, -4866, -7760, -5178, -1840, 14779, -1119, 6007, -1489, -3399, -4567, -2543, 1855, 5255,
    53, -1626, 67, 1506, -12256, -7706, -1982, 21943, 3549, -969, -1096, -1484, -10824, 2981, 2204, 5639,
    -229, 1106, 945, -1821, -9237, 10157, 1616, -2537, 4916, -199, -2177, -2540, 6673, 984, -3355, -4302,
    -7130, -4677, 8925, 2882, 445, 2762, -348, -2859, -196, -1859, 1761, 294, 2725, -2093, -966, 334,
    -3908, -308, 3675, 541, 735, 890, -2516, 891, 504, 1631, -1157, -977, -17817, 2119, 7104, 8594,
    -2056, 1897, -198, 356, 292, -4544, -287, 4538, -1455, -304, 603, 1156, -18259, -12643, 15247, 15655,
    4177, 1778, -1815, -4140, 1425, 576, -294, -1707, -1301, 5132, 2838, -6669, -4727, -3148, -905, 8781,
    -650, 152, -4654, 5152, 13746, 2320, -6259, -9807, -1356, 396, 3789, -2829, 2337, 1947, -29, -4256,
    6033, 820, -5730, -1123, -1795, 1091, 1080, -377, 2208, -1921, -3314, 3027, 9688, 5218, -3754, -11152,
    3814, -3941, -6183, 6310, -1017, -2391, 4393, -984, 10944, -1182, -5011, -4751, -4640, 7201, -218, -2343,
    -1278, 4720, -4212, 770, 2777, 1333, -5944, 1833, -16066, 8107, 5165, 2795, 2530, -5020, 6073, -3582,
    -2111, -7534, 4575, 5070, -8702, -3762, 4050, 8414, 1335, -997, -1567, 1229, 9348, 1534, -3959, -6922,
    2440, 1153, -2175, -1418, -2715, -4538, -4478, 11730, 569, -885, 2032, -1716, 3529, -91, -3218, -219,
    2157, -4121, 191, 1772, -2123, -1968, -1355, 5446, 1475, -354, 3651, -4772, 1654, -3521, 2726, -859,
    2393, 6820, -2958, -6255, -3861, 1365, 1177, 1319, 7614, -1638, -2789, -3187, -3628, -2635, 6902, -639,
    1925, 2295, -1451, -2769, -3683, 4517, -981, 147, -1260, -529, 2339, -550, 3013, 639, -1050, -2602,
    3651, 1959, -3218, -2391, 6267, 3124, -2926, -6464, -8180, 3900, 4191, 89, -3372, -611, 1042, 2941,
    -2510, 856, -925, 2579, -11667, -8436, 10605, 9498, 6427, -2733, 1887, -5581, 1581, -1722, -328, 469,
    2011, 1989, -3606, -394, -1014, 2197, -1200, 17, 1544, -2555, 765, 247, 1188, -183, 1966, -2972,
    -6057, 3480, -2284, 4860, -25659, 8466, 8891, 8303,
};

/* ── DCT matrix ────────────────────────────────────────────────────────────── */
static float noise_dct_mat[SMPL_NOISE_CORR_ORDER + 1][SMPL_NOISE_DCT_ORDER];
static int noise_dct_built = 0;

static void build_noise_dct(void) {
    if (noise_dct_built) return;
    float sc = 1.0f / mlow_sqrtf32((float)SMPL_NOISE_DCT_ORDER);
    for (int i = 0; i < SMPL_NOISE_DCT_ORDER; i++) {
        float d_omega = ((0.5f + (float)i) * SMPL_PI_NOISE) / (float)SMPL_NOISE_DCT_ORDER;
        float omega = 0.0f;
        for (int j = 0; j < SMPL_NOISE_CORR_ORDER + 1; j++) {
            noise_dct_mat[j][i] = mlow_cosf32(omega) * sc;
            omega += d_omega;
        }
    }
    noise_dct_built = 1;
}

/* ── smplRand: LCG ──────────────────────────────────────────────────────────── */
static int32_t smpl_rand(int32_t seed) {
    return (int32_t)(907633515u + (uint32_t)seed * 196314165u);
}

/* ── smplSigmoid ────────────────────────────────────────────────────────────── */
static float smpl_sigmoid(float x) {
    if (x > 80.0f) return 1.0f;
    if (x < -80.0f) return 0.0f;
    return 1.0f / (1.0f + (float)exp((double)(-x)));
}

/* ── Helpers ────────────────────────────────────────────────────────────────── */
static float smpl_nrg(const float *x, int l) {
    float nrg = 0.0f;
    for (int i = 0; i < l; i++) nrg += x[i] * x[i];
    return nrg;
}

static float smpl_sum(const float *x, int l) {
    float s = 0.0f;
    for (int i = 0; i < l; i++) s += x[i];
    return s;
}

static float smpl_maximum(const float *x, int l) {
    float m = x[0];
    for (int i = 1; i < l; i++) if (x[i] > m) m = x[i];
    return m;
}

static float min_f32(float a, float b) { return a < b ? a : b; }

/* ── smplGenRandPulses ──────────────────────────────────────────────────────── */
static void smpl_gen_rand_pulses(float *noise, int l, int32_t *seed) {
    const float sc = 8.1e-10f;
    int i = 0;
    for (; i + 3 < l; i += 4) {
        *seed = smpl_rand(*seed);
        uint32_t s = (uint32_t)*seed;
        noise[i]     = sc * (float)*seed;
        noise[i + 1] = sc * (float)(int32_t)(s << 8);
        noise[i + 2] = sc * (float)(int32_t)(s << 16);
        noise[i + 3] = sc * (float)(int32_t)(s << 24);
    }
    for (; i < l; i++) {
        *seed = smpl_rand(*seed);
        noise[i] = sc * (float)*seed;
    }
}

/* ── smplGetEnv ─────────────────────────────────────────────────────────────── */
static void smpl_get_env(const float *exc, int length, float smth_coef, float *smth_state, float *env) {
    smth_coef *= smth_coef;
    float state = *smth_state + 1e-8f;
    state *= state;
    float gain_coef = 1.0f - smth_coef;
    float smth_coef2 = smth_coef * smth_coef;
    float gain_smth_coef = gain_coef * smth_coef;
    int i = 0;
    for (; i + 3 < length; i += 4) {
        float tmp0 = exc[i] * exc[i] + exc[i + 1] * exc[i + 1];
        float tmp1 = exc[i + 2] * exc[i + 2] + exc[i + 3] * exc[i + 3];
        float y1 = gain_coef * tmp1 + gain_smth_coef * tmp0 + smth_coef2 * state;
        float y0 = gain_coef * tmp0 + smth_coef * state;
        env[i] = mlow_sqrtf32(y0);
        env[i + 1] = env[i];
        env[i + 2] = mlow_sqrtf32(y1);
        env[i + 3] = env[i + 2];
        state = y1;
    }
    *smth_state = env[length - 1];
}

/* ── smplGetEnv0 ────────────────────────────────────────────────────────────── */
static void smpl_get_env0(int length, float smth_coef, float *smth_state, float *env) {
    float smth_coef2 = smth_coef * smth_coef;
    env[0] = (*smth_state + 1e-8f) * smth_coef;
    env[1] = env[0];
    int i = 2;
    for (; i + 2 < length; i += 4) {
        env[i + 2] = env[i - 1] * smth_coef2;
        env[i + 3] = env[i + 2];
        env[i] = env[i - 1] * smth_coef;
        env[i + 1] = env[i];
    }
    env[length - 2] = env[length - 3] * smth_coef;
    env[length - 1] = env[length - 2];
    *smth_state = env[length - 1];
}

/* ── Filter helpers ─────────────────────────────────────────────────────────── */
static void smpl_filt_ma1(const float *x, int n, const float coef[2], float *state, float *y) {
    if (coef[0] == 1.0f) {
        for (int k = 1; k < n; k++) y[k] = x[k] + coef[1] * x[k - 1];
    } else {
        for (int k = 0; k < n; k++) y[k] = coef[0] * x[k];
        for (int k = 1; k < n; k++) y[k] += coef[1] * x[k - 1];
    }
    y[0] = coef[0] * x[0] + coef[1] * *state;
    *state = x[n - 1];
}

static void smpl_filt_ar1(const float *x, int n, const float coef[2], float *state, float *y) {
    float ar1 = -coef[1];
    float ytmp = *state;
    for (int nn = 0; nn < n; nn++) {
        ytmp = x[nn] + ytmp * ar1;
        y[nn] = ytmp;
    }
    *state = ytmp;
}

static void smpl_filt_arma1(const float *x, int n, const float coef_ma[2], const float coef_ar[2], float state[2], float *y) {
    float tmp[SMPL_MAX_SF_LEN];
    float ma_state = state[0];
    smpl_filt_ma1(x, n, coef_ma, &ma_state, tmp);
    state[0] = ma_state;
    float ar_state = state[1];
    smpl_filt_ar1(tmp, n, coef_ar, &ar_state, y);
    state[1] = ar_state;
}

static void smpl_filt_ma2(const float *x, int n, const float coef[3], float state[2], float *y) {
    if (coef[0] == 1.0f) {
        for (int i = 1; i < n; i++) y[i] = x[i] + coef[1] * x[i - 1];
    } else {
        for (int i = 0; i < n; i++) y[i] = coef[0] * x[i];
        for (int i = 1; i < n; i++) y[i] += coef[1] * x[i - 1];
    }
    for (int i = 2; i < n; i++) y[i] += coef[2] * x[i - 2];
    y[0] = coef[0] * x[0] + coef[1] * state[0] + coef[2] * state[1];
    y[1] += coef[2] * state[0];
    state[0] = x[n - 1];
    state[1] = x[n - 2];
}

/* ── smplSpecFact2 ──────────────────────────────────────────────────────────── */
static void smpl_spec_fact2(const float c_in[3], float a[3]) {
    float c[3] = {c_in[0], c_in[1], c_in[2]};
    c[0] += 1e-30f;
    float inv_c0 = 1.0f / c[0];
    float r2 = c[2] * inv_c0;
    float r1 = c[1] / (c[0] * (1.0f + r2));
    for (int iter = 0; iter < 2; iter++) {
        float v0 = 1.0f + r1 * r1 + r2 * r2;
        float v1 = r1 + r1 * r2;
        float s = -2.0f / v0;
        float da0 = s * r1;
        float da1 = s * r2;
        s = v0 * inv_c0;
        float e1 = s * c[1] - v1;
        float e2 = s * c[2] - r2;
        float r0 = 2.0f * r1 + v0 * da0;
        float r3 = 2.0f * r2 + v0 * da1;
        float rr00 = r0 * r0;
        float rr01 = r0 * r3;
        float rr11 = r3 * r3;
        float rcap1 = 1.0f + r2 + v1 * da0;
        float r4 = r1 + v1 * da1;
        rr00 += rcap1 * rcap1;
        rr01 += rcap1 * r4;
        rr11 += r4 * r4;
        float re0 = rcap1 * e1;
        float re1 = r4 * e1;
        float r2c = r2 * da0;
        float r5 = 1.0f + r2 * da1;
        rr00 += r2c * r2c;
        rr01 += r2c * r5;
        rr11 += r5 * r5;
        re0 += r2c * e2;
        re1 += r5 * e2;
        s = rr00 * rr11 - rr01 * rr01;
        if (s < 1e-4f) break;
        s = 1.0f / s;
        r1 += (rr11 * re0 - rr01 * re1) * s;
        r2 += (-rr01 * re0 + rr00 * re1) * s;
    }
    float sc = mlow_sqrtf32(c[0] / (1.0f + r1 * r1 + r2 * r2));
    a[0] = sc;
    a[1] = sc * r1;
    a[2] = sc * r2;
}

/* ── noiseMatMultTransp16 ───────────────────────────────────────────────────── */
static void noise_mat_mult_transp16(const float c[SMPL_NOISE_CORR_ORDER + 1][SMPL_NOISE_DCT_ORDER],
                                      const float *x, float *y, int len_x) {
    float yt[SMPL_NOISE_DCT_ORDER];
    float xtmp = x[0];
    for (int i = 0; i < SMPL_NOISE_DCT_ORDER; i++) yt[i] = c[0][i] * xtmp;
    for (int j = 1; j < len_x; j++) {
        float xt = x[j];
        for (int i = 0; i < SMPL_NOISE_DCT_ORDER; i++) yt[i] += c[j][i] * xt;
    }
    for (int i = 0; i < SMPL_NOISE_DCT_ORDER; i++) y[i] = yt[i];
}

static void noise_mat_mult(const float c[SMPL_NOISE_CORR_ORDER + 1][SMPL_NOISE_DCT_ORDER],
                            const float *x, float *y) {
    for (int i = 0; i < SMPL_NOISE_CORR_ORDER + 1; i++) {
        float acc = 0.0f;
        for (int k = 0; k < SMPL_NOISE_DCT_ORDER; k++) acc += c[i][k] * x[k];
        y[i] = acc;
    }
}

/* ── SmplGetNormalizedBitrate ───────────────────────────────────────────────── */
float smpl_get_normalized_bitrate(int32_t num_pulses, int32_t frame_length16) {
    float pulses_per_20ms = (float)(num_pulses * frame_length16) / (20.0f * 16.0f);
    return smpl_sigmoid(1.4f * (float)log2((double)(pulses_per_20ms + 1.0f)) - 6.5f);
}

/* ── SmplDecodeResnrg ───────────────────────────────────────────────────────── */
float smpl_decode_resnrg(int32_t nrgres_frame_dbq_q14, int32_t fcb_subfrlen) {
    float exp_val = 0.1f * ((float)nrgres_frame_dbq_q14 / (float)(1 << 14));
    float resnrg = (float)pow(10.0, (double)exp_val) - SMPL_RES_NRG_BIAS;
    if (resnrg < 0.0f) resnrg = 0.0f;
    return resnrg * (float)fcb_subfrlen;
}

/* ── addNoiseUV ─────────────────────────────────────────────────────────────── */
static void add_noise_uv(noise_gen_t *ng, float *exc_noise_uv, int l, const float *lsf,
                         float nrg_ratio, float *noise) {
    float lsf_hz = 16000.0f * (lsf[0] + lsf[1]) / (4.0f * SMPL_PI_NOISE);
    float min_uv_fcorner_hz = lsf_hz * 3.0f * smpl_sigmoid(0.2f / (lsf[1] - lsf[0] + 1e-30f) - 3.0f);
    float uv_fcorner_hz = DEC_NOISE_UV_FCORNER_HZ * min_f32(0.6f + 0.4f * nrg_ratio, 1.0f);
    uv_fcorner_hz = mlow_maxf32(uv_fcorner_hz, min_uv_fcorner_hz);
    uv_fcorner_hz = min_f32(uv_fcorner_hz, 1500.0f);
    float coef_tmp = 6.0f * uv_fcorner_hz / 16000.0f;
    float g = (1.0f - 0.5f * coef_tmp) * DEC_NOISE_UV_NOISE_GAIN;
    float coef_ma_uv[2] = {g, -g};
    float coef_ar_uv[2] = {1.0f, -1.0f + coef_tmp};
    float filtered[SMPL_MAX_SF_LEN];
    smpl_filt_arma1(exc_noise_uv, l, coef_ma_uv, coef_ar_uv, ng->out_state_uv, filtered);
    memcpy(exc_noise_uv, filtered, l * sizeof(float));
    for (int i = 0; i < l; i++) noise[i] += exc_noise_uv[i];
}

/* ── SmplCelpGenNoise ───────────────────────────────────────────────────────── */
void smpl_celp_gen_noise(noise_gen_t *ng, const float *exc_lpc, int l, bool voiced,
                         int32_t num_pulses, float nrgres, int32_t fcbg_idx,
                         const float *lsf, float normalized_bitrate,
                         const float *fcbgains_uv, float *noise) {
    float nrg_ratio = 1.0f;
    float noise_uv[SMPL_MAX_SF_LEN], noise_v[SMPL_MAX_SF_LEN], noise_v2[SMPL_MAX_SF_LEN], env[SMPL_MAX_SF_LEN];
    memset(noise_uv, 0, sizeof(noise_uv));
    memset(noise_v, 0, sizeof(noise_v));
    memset(noise_v2, 0, sizeof(noise_v2));

    if (voiced) {
        float corrs[3], c[3], ctgt[3];
        for (int i = 0; i < 3; i++) {
            float acc = 0.0f;
            for (int k = 0; k < l - i; k++) acc += exc_lpc[k] * exc_lpc[k + i];
            corrs[i] = acc;
        }
        corrs[0] += 1e-12f;
        float corr_smth_coef = 0.16f;
        if (l == SMPL_CELP_FS_KHZ * 10) corr_smth_coef = 0.4f;
        for (int i = 0; i < 3; i++) {
            ng->corr_smth[i] += corr_smth_coef * (corrs[i] - ng->corr_smth[i]);
        }
        float scale = DEC_NOISE_V_NOISE_GAIN * DEC_NOISE_V_NOISE_GAIN * corrs[0] / ng->corr_smth[0];
        for (int i = 0; i < 3; i++) c[i] = ng->corr_smth[i] * scale;
        c[1] *= 2.0f;
        c[2] *= 2.0f;

        build_noise_dct();
        float f2[SMPL_NOISE_DCT_ORDER], f2_tgt[SMPL_NOISE_DCT_ORDER];
        noise_mat_mult_transp16(noise_dct_mat, c, f2, 3);
        float m = smpl_maximum(f2, SMPL_NOISE_DCT_ORDER) * 1.5f;
        for (int i = 0; i < SMPL_NOISE_DCT_ORDER; i++) f2_tgt[i] = m - f2[i];
        noise_mat_mult(noise_dct_mat, f2_tgt, ctgt);
        smpl_gen_rand_pulses(noise_v, l, &ng->rand_seed);
        if (!ng->prev_voiced) ng->env_smth = ng->env_last;
        smpl_get_env(exc_lpc, l, ENV_SMTH_COEF_V, &ng->env_smth, env);
        for (int i = 0; i < l; i++) noise_v[i] *= env[i];
        float nrg_noise = smpl_nrg(noise_v, l);
        float inv = 1.0f / (nrg_noise + 1e-12f);
        for (int i = 0; i < 3; i++) ctgt[i] *= inv;
        float coef_ma[3];
        smpl_spec_fact2(ctgt, coef_ma);
        smpl_filt_ma2(noise_v, l, coef_ma, ng->shape_state, noise_v2);

        if (!ng->prev_voiced) {
            smpl_gen_rand_pulses(noise_uv, l, &ng->rand_seed);
            float env_val = ng->env_last * ENV_SMTH_COEF_UVV;
            for (int i = 0; i < l; i += 2) {
                noise_uv[i] *= env_val;
                noise_uv[i + 1] *= env_val * ENV_SMTH_COEF_UVV;
                env_val *= ENV_SMTH_COEF_UVV * ENV_SMTH_COEF_UVV;
            }
        } else if (ng->since_unvoiced < 2) {
            for (int i = 0; i < l; i++) noise_uv[i] = 0.0f;
        }
        ng->env_last = env[l - 1];
    } else {
        for (int i = 0; i < 3; i++) ng->corr_smth[i] = 0.0f;
        for (int i = 0; i < 2; i++) ng->shape_state[i] = 0.0f;
        for (int i = 0; i < l; i++) noise_v2[i] = 0.0f;

        float nrg_tgt;
        if (num_pulses > 0) {
            nrg_ratio = smpl_nrg(exc_lpc, l) / (nrgres + 1e-20f);
            float hardness = 10.0f + 20.0f * normalized_bitrate;
            nrg_tgt = nrgres * (float)log((double)((float)exp((double)(hardness * (1.0f - nrg_ratio))) + 1.0f)) / hardness;
            smpl_get_env(exc_lpc, l, ENV_SMTH_COEF_UV, &ng->env_smth, env);
        } else {
            nrg_ratio = 0.0f;
            nrg_tgt = nrgres;
            smpl_get_env0(l, ENV_SMTH_COEF_UV, &ng->env_smth, env);
        }

        float scale = 1.0f / (float)l;
        nrg_tgt = nrg_tgt * scale + 1e-30f;
        float nrg_env = smpl_nrg(env, l) * scale;
        float f = mlow_sqrtf32(nrg_tgt);
        float gg = mlow_sqrtf32(nrg_tgt / nrg_env);
        float ge = gg * env[0];
        float env_last = ng->env_last;
        if (env_last < min_f32(f, ge)) {
            if (f < ge) gg = 0.0f; else f = 0.0f;
        } else if (env_last > mlow_maxf32(f, ge)) {
            if (f > ge) gg = 0.0f; else f = 0.0f;
        } else {
            float sum_env = smpl_sum(env, l) * scale;
            float a = nrg_env + env[0] * env[0] - 2.0f * sum_env * env[0];
            float b = 2.0f * env_last * (sum_env - env[0]);
            float cc = env_last * env_last - nrg_tgt;
            float tmp = b * b - 4.0f * a * cc;
            if (tmp < 1e-35f || a < 1e-25f) {
                f = 0.0f; gg = 0.0f;
            } else {
                tmp = mlow_sqrtf32(tmp);
                scale = 0.5f / a;
                gg = (-b + tmp) * scale;
                f = env_last - env[0] * gg;
                if (f < 0.0f) {
                    gg = (-b - tmp) * scale;
                    f = env_last - env[0] * gg;
                }
            }
        }

        smpl_gen_rand_pulses(noise_uv, l, &ng->rand_seed);
        if (num_pulses > 0) {
            float max_val = fcbgains_uv[fcbg_idx] * 0.5f;
            for (int i = 0; i < l; i++) {
                if (exc_lpc[i] == 0.0f) {
                    noise_uv[i] *= min_f32(f + gg * env[i], max_val);
                } else {
                    noise_uv[i] = 0.0f;
                }
            }
            ng->env_last = min_f32(f + gg * env[l - 1], max_val);
        } else {
            for (int i = 0; i < l; i++) noise_uv[i] *= f + gg * env[i];
            ng->env_last = f + gg * env[l - 1];
        }
    }

    if (ng->prev_voiced || voiced) {
        smpl_filt_ma2(noise_v2, l, COEF_MA_V, ng->out_state_v, noise);
    } else {
        for (int i = 0; i < l; i++) noise[i] = 0.0f;
    }
    if (ng->since_unvoiced < 2 || !voiced) {
        add_noise_uv(ng, noise_uv, l, lsf, nrg_ratio, noise);
    } else {
        ng->out_state_uv[0] = 0.0f;
        ng->out_state_uv[1] = 0.0f;
    }
    ng->prev_voiced = voiced;
    if (voiced) ng->since_unvoiced++;
    else ng->since_unvoiced = 0;
}