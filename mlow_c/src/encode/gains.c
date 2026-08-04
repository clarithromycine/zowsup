/*
 * gains.c — Encoder-side gain quantization for unvoiced mode.
 */
#include "encode.h"
#include "../seed.h"
#include <math.h>
#include <string.h>

#define UV_GAIN_MIN_DB   -90.0f
#define UV_GAIN_MAX_DB     0.0f
#define UV_GAIN_STEP_DB    1.0f
#define UV_GAIN_IDX_LEN    90

static int32_t celp_quant_gain_uv(float gain_linear) {
    double gain_db = 20.0 * log10((double)gain_linear + 1e-16);
    if (gain_db < (double)UV_GAIN_MIN_DB) gain_db = (double)UV_GAIN_MIN_DB;
    if (gain_db > (double)UV_GAIN_MAX_DB) gain_db = (double)UV_GAIN_MAX_DB;
    int32_t idx = (int32_t)round((gain_db - (double)UV_GAIN_MIN_DB) / (double)UV_GAIN_STEP_DB);
    if (idx < 0) idx = 0;
    if (idx > UV_GAIN_IDX_LEN) idx = UV_GAIN_IDX_LEN;
    return idx;
}

void smpl_quant_nrg_res4(const float subfr_energy[4], const int32_t subfr_counts[4],
                         int32_t *gain_main, int32_t *gain_delta,
                         int32_t nrg_res[4]) {
    float e_db[4];
    for (int sf = 0; sf < 4; sf++) {
        if (subfr_counts[sf] > 0 && subfr_energy[sf] > 0.0f)
            e_db[sf] = (float)(10.0 * log10((double)subfr_energy[sf] + 1e-16));
        else
            e_db[sf] = UV_GAIN_MIN_DB;
    }

    float avg_db = 0.0f;
    int n_active = 0;
    for (int sf = 0; sf < 4; sf++) {
        if (subfr_counts[sf] > 0) { avg_db += e_db[sf]; n_active++; }
    }
    if (n_active > 0) avg_db /= (float)n_active; else avg_db = UV_GAIN_MIN_DB;

    *gain_main = celp_quant_gain_uv((float)pow(10.0, (double)avg_db / 20.0));
    if (*gain_main < 0) *gain_main = 0;
    *gain_delta = 0;

    for (int sf = 0; sf < 4; sf++) {
        if (subfr_counts[sf] > 0 && e_db[sf] > UV_GAIN_MIN_DB) {
            nrg_res[sf] = celp_quant_gain_uv((float)pow(10.0, (double)e_db[sf] / 20.0));
            if (nrg_res[sf] > UV_GAIN_IDX_LEN) nrg_res[sf] = UV_GAIN_IDX_LEN;
        } else {
            nrg_res[sf] = -1;
        }
    }
}