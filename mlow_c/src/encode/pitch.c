/*
 * pitch.c — MLow pitch estimator (encoder analysis).
 *
 * HP-filters + 2x-downsamples the perceptually-weighted ltp_buf, runs an
 * open-loop block-track survivor search at coarse resolution, refines
 * per-block at full resolution, and folds in rate / prev-lag / spectral-
 * harmonicity biases. Only the 20ms / 8-subframe config is supported.
 */
#include "encode.h"
#include "../tables/pitch_seed.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>

/* ── Constants ──────────────────────────────────────────────────────────────── */
#define PE_FS_KHZ              16
#define PE_STAGE1_FS_KHZ        8
#define PE_TOT_INTERP_DELAY     6
#define PE_MINPITCH_MS          2
#define PE_MAXPITCH_MS         20
#define PE_MINPITCH_LEN        (PE_MINPITCH_MS * PE_FS_KHZ)               /* 32 */
#define PE_MAXPITCH_LEN        (PE_MAXPITCH_MS * PE_FS_KHZ)               /* 320 */
#define PE_MINPITCH_STAGE1     (PE_MINPITCH_MS*PE_STAGE1_FS_KHZ - PE_TOT_INTERP_DELAY) /* 10 */
#define PE_MAXPITCH_STAGE1     (PE_MAXPITCH_MS*PE_STAGE1_FS_KHZ + PE_TOT_INTERP_DELAY) /* 166 */

#define PE_PITCH_DELTAWGHT      0.1439f
#define PE_PITCH_SHORTWGHT1     0.04f
#define PE_SPEC_HARM_BIAS       2.5f
#define PE_PREVWGHT             0.7981f
#define PE_PREVWGHT_SPAN        0.15f
#define PE_RATEWGHT_HR          0.022f

#define PE_LAG_SUBFR_LEN       40
#define PE_LAG_SUBFR_LEN_STAGE1 (PE_STAGE1_FS_KHZ * PE_LAG_SUBFR_LEN / PE_FS_KHZ) /* 20 */
#define PE_PITCHBLOCK_MS        2
#define PE_PITCH_LOOKAHEAD_LEN  7
#define PE_DOWNSAMP_DELAY       7
#define PE_INTERPOL_DELAY_C     4
#define PE_PITCHBLOCK           (PE_PITCHBLOCK_MS * PE_FS_KHZ)            /* 32 */
#define PE_NUM_LAGS_STAGE1      (PE_MAXPITCH_STAGE1 - PE_MINPITCH_STAGE1 + 1) /* 157 */
#define PE_NUMLAGS_COARSE       (PE_FS_KHZ * (PE_MAXPITCH_MS - PE_MINPITCH_MS)) /* 288 */
#define PE_NUMLAGS_FS           PE_NUMLAGS_COARSE
#define PE_NUMSTATES1           24
#define PE_NUM_SUBFR            8
#define PE_PITCH_NUM_BLOCKS     9

/* ── Filter constants ──────────────────────────────────────────────────────── */
static const float pe_downsamp_filt[2 * PE_DOWNSAMP_DELAY + 1] = {
    -0.045472838f, 0.0f, 0.06366198f, 0.0f, -0.10610329f, 0.0f, 0.31830987f,
    0.5f, 0.31830987f, 0.0f, -0.10610329f, 0.0f, 0.06366198f, 0.0f, -0.045472838f,
};

static const float pe_interpol_filt_c[2 * PE_INTERPOL_DELAY_C] = {
    -0.0024414062f, 0.023925781f, -0.119628906f, 0.59814453f,
    0.59814453f, -0.119628906f, 0.023925783f, -0.0024414062f,
};

/* ── DSP helpers (local, not exported) ─────────────────────────────────────── */

static float maxF32(float a, float b) { return a > b ? a : b; }

/* pePitchHpFilter: MA(1) + AR(1) with b={1,-1}, a={1,-0.96} */
static void pe_hp_filter(const float *x, float *out, int n) {
    float state_ma = 0.0f;
    const float ar1 = 0.96f;
    for (int i = 0; i < n; i++) {
        out[i] = x[i] - state_ma;
        state_ma = x[i];
    }
    float ar12 = ar1 * ar1, ar13 = ar1 * ar12, ar14 = ar1 * ar13, ar15 = ar1 * ar14;
    float ytmp = 0.0f;
    int idx = 0;
    while (idx + 4 < n) {
        float x0 = out[idx], x1 = out[idx+1], x2 = out[idx+2], x3 = out[idx+3], x4 = out[idx+4];
        out[idx+4] = x4 + ar1*x3 + ar12*x2 + ar13*x1 + ar14*x0 + ar15*ytmp;
        out[idx]   = x0 + ar1*ytmp;
        out[idx+1] = x1 + ar1*x0 + ar12*ytmp;
        out[idx+2] = x2 + ar1*x1 + ar12*x0 + ar13*ytmp;
        out[idx+3] = x3 + ar1*x2 + ar12*x1 + ar13*x0 + ar14*ytmp;
        ytmp = out[idx+4];
        idx += 5;
    }
    for (; idx < n; idx++) {
        ytmp = out[idx] + ytmp * ar1;
        out[idx] = ytmp;
    }
}

/* 2x decimating FIR */
static int pe_downsample(const float *in, int l, float *out) {
    int d = PE_DOWNSAMP_DELAY;
    int n = (l - 2*d) / 2;
    for (int j = 0; j < n; j++) {
        float tmp = in[2*j + d] * pe_downsamp_filt[d];
        for (int i = 0; i < d; i += 2)
            tmp += (in[2*j + i] + in[2*j + 2*d - i]) * pe_downsamp_filt[i];
        out[j] = tmp;
    }
    return n;
}

/* Upsample E-core: backward write; even taps copy, odd taps average */
static void pe_upsamp_e_core(float *buf, int x_end, int y_end, int length) {
    int xi = x_end, yi = y_end;
    for (int k = 0; k < length; k++) {
        float v = (buf[xi] + buf[xi+1]) * 0.5f;
        buf[yi] = v; yi--;
        buf[yi] = buf[xi]; yi--;
        xi--;
    }
}

/* Upsample C-core: backward write with 8-tap interpolation filter */
static void pe_upsamp_c_core(float *buf, int x_end, int y_end, int length) {
    int xi = x_end, yi = y_end;
    for (int k = 0; k < length; k++) {
        float tmp = 0.0f;
        for (int j = 0; j < PE_INTERPOL_DELAY_C; j++) {
            float a = buf[xi + j - (PE_INTERPOL_DELAY_C - 1)];
            float b = buf[xi + PE_INTERPOL_DELAY_C - j];
            tmp += (a + b) * pe_interpol_filt_c[j];
        }
        buf[yi] = tmp; yi--;
        buf[yi] = buf[xi]; yi--;
        xi--;
    }
}

static float pe_nrg(const float *x, int n) {
    float s = 0.0f;
    for (int i = 0; i < n; i++) s += x[i] * x[i];
    return s;
}

static float pe_maximum(const float *x, int n) {
    float m = x[0];
    for (int i = 1; i < n; i++) if (x[i] > m) m = x[i];
    return m;
}

static int pe_get_maxi(const float *x, int n) {
    int bi = 0;
    float best = x[0];
    for (int i = 1; i < n; i++) {
        if (x[i] > best) { best = x[i]; bi = i; }
    }
    return bi;
}

static int pe_get_maxi_k(const float *x, int n, int k, int *out) {
    char *taken = (char *)calloc((size_t)n, 1);
    if (!taken) return 0;
    int count = 0;
    for (int c = 0; c < k; c++) {
        int bi = -1;
        float best = 0.0f;
        for (int i = 0; i < n; i++) {
            if (!taken[i] && (bi < 0 || x[i] > best)) {
                best = x[i]; bi = i;
            }
        }
        if (bi < 0) break;
        taken[bi] = 1;
        out[count++] = bi;
    }
    free(taken);
    return count;
}

static float pe_dot_prod(const float *a, const float *b, int n) {
    float r = 0.0f;
    for (int i = 0; i < n; i++) r += a[i] * b[i];
    return r;
}

static float pe_dot_prod40(const float *a, const float *b) {
    return pe_dot_prod(a, b, 40);
}

/* Running energy E1 per subframe */
static void pe_calc_e1_inner(float *e1, const float *ltpbuf, int t,
                              int minpitch, int maxpitch, int lag_subfrlen) {
    int numlags = maxpitch - minpitch + 1;
    int reg0 = t - minpitch;
    e1[0] = maxF32(pe_nrg(ltpbuf + reg0, lag_subfrlen), 1e-9f);
    for (int i = 1; i < numlags; i++) {
        float rm = ltpbuf[reg0 - i];
        float rs = ltpbuf[reg0 + lag_subfrlen - i];
        e1[i] = maxF32(e1[i-1] + rm*rm - rs*rs, 1e-9f);
    }
}

static void pe_calc_e1(float *e1, const float *ltpbuf, int ltpbuf_len,
                        int numsubfrs, int minpitch, int maxpitch, int lag_subfrlen) {
    int numlags = maxpitch - minpitch + 1;
    int maxpitch_ext = maxpitch + (numsubfrs - 1) * lag_subfrlen;
    int numlags_ext = maxpitch_ext - minpitch + 1;
    int t = ltpbuf_len - lag_subfrlen;
    float *e1_ext = (float *)malloc((size_t)numlags_ext * sizeof(float));
    if (!e1_ext) return;
    pe_calc_e1_inner(e1_ext, ltpbuf, t, minpitch, maxpitch_ext, lag_subfrlen);
    int offset = numlags_ext - numlags;
    for (int sf = 0; sf < numsubfrs; sf++) {
        for (int i = 0; i < numlags; i++)
            e1[sf * numlags + i] = e1_ext[offset + i];
        offset -= lag_subfrlen;
    }
    free(e1_ext);
}

static void pe_calc_ce2(float *c, float *e2, const float *ltpbuf, int ltpbuf_len, int numsubfrs) {
    int t = ltpbuf_len - PE_LAG_SUBFR_LEN_STAGE1 * numsubfrs;
    for (int sf = 0; sf < numsubfrs; sf++) {
        const float *tgt = ltpbuf + t;
        int reg0 = t - PE_MINPITCH_STAGE1;
        for (int i = 0; i < PE_NUM_LAGS_STAGE1; i++) {
            const float *r = ltpbuf + reg0 - i;
            c[sf * PE_NUM_LAGS_STAGE1 + i] = pe_dot_prod(tgt, r, 20);
        }
        t += PE_LAG_SUBFR_LEN_STAGE1;
        e2[sf] = maxF32(pe_dot_prod(tgt, tgt, 20), 1e-9f);
    }
}

static void pe_upsamp_e_fast(float *buf, int numsubfrs, int *minpitch, int *numlags) {
    int nin = *numlags;
    int nout = (nin - 1) * 2;
    for (int sf = numsubfrs - 1; sf >= 0; sf--) {
        int x_end = sf * nin + nin - 2;
        int y_end = sf * nout + nout - 1;
        pe_upsamp_e_core(buf, x_end, y_end, nin - 1);
    }
    *numlags = nout;
    *minpitch *= 2;
}

static void pe_upsamp_c_fast(float *buf, int numsubfrs, int *minpitch, int *numlags) {
    int nin = *numlags;
    int nout = (nin - PE_INTERPOL_DELAY_C) * 2;
    for (int sf = numsubfrs - 1; sf >= 0; sf--) {
        int x_end = sf * nin + nin - 1 - PE_INTERPOL_DELAY_C;
        int y_end = sf * nout + nout - 1;
        pe_upsamp_c_core(buf, x_end, y_end, nin - (PE_INTERPOL_DELAY_C * 2 - 1));
    }
    *numlags = nout;
    *minpitch *= 2;
}

static int32_t pe_sum_deltas(const int32_t *laginds, int numsubfrs) {
    int32_t ret = 0;
    for (int i = 1; i < numsubfrs; i++) {
        int32_t d = laginds[i] - laginds[i-1];
        if (d < 0) d = -d;
        ret += d;
    }
    return ret;
}

static float pe_ec_encode_bits(uint32_t fl, uint32_t fh, uint32_t ft) {
    float p = (float)(fh - fl) / (float)ft;
    if (p <= 0.0f) return 0.0f;
    return -(float)log2((double)p);
}

/* peEncodeLagsBits: bit cost of encoding laginds for a given blockseg */
static float pe_encode_lags_bits(const pitch_tables_t *tab, int blocksegs_ix,
                                  const int32_t *laginds, int32_t prev_lagblk,
                                  int32_t prev_lagidx, int mode) {
    float nbits = 0.0f;
    int32_t ix_julia = (int32_t)tab->blocksegs2idx[blocksegs_ix];
    int32_t blocksize = (int32_t)(PE_PITCHBLOCK_MS * PE_FS_KHZ * 2); /* 64 */
    const pitch_block_seg_t *pbs = &tab->blocksegs[blocksegs_ix];

    if (prev_lagblk < 0) {
        const uint32_t *cmf = tab->blockseg_idx_cmf;
        uint32_t top = cmf[tab->num_blocksegs];
        nbits += pe_ec_encode_bits(cmf[ix_julia - 1], cmf[ix_julia], top);
    } else {
        const uint32_t *cmf = tab->block_transition_cmf[prev_lagblk];
        int32_t b0 = pbs->blocks[0];
        nbits += pe_ec_encode_bits(cmf[b0], cmf[b0 + 1], cmf[PE_PITCH_NUM_BLOCKS]);
        int32_t start_ix = tab->firstblock_range[b0][0];
        int32_t cmf_len = tab->firstblock_range[b0][1] - start_ix + 1;
        const uint32_t *cmf2 = tab->blockseg_idx_cmf + start_ix;
        uint32_t lo = ix_julia - start_ix - 1;
        uint32_t hi = ix_julia - start_ix;
        nbits += pe_ec_encode_bits(cmf2[lo] - cmf2[0], cmf2[hi] - cmf2[0], cmf2[cmf_len] - cmf2[0]);
    }

    int32_t blk = pbs->blocks[0];
    int32_t delta_blk = blk - prev_lagblk;
    int start_seg = 0;
    int laginds_ix = 0;
    if (!(prev_lagblk > -1 && delta_blk >= -1 && delta_blk <= 2)) {
        nbits += 6.0f; /* uniform first-lag cost */
        prev_lagblk = blk;
        prev_lagidx = laginds[laginds_ix];
        laginds_ix += pbs->seglens[0];
        start_seg = 1;
    }
    const uint32_t *delta_lag_cmf = tab->delta_lag_cmfs[mode];
    for (int k = start_seg; k < pbs->nblocks; k++) {
        blk = pbs->blocks[k];
        int32_t idx = laginds[laginds_ix];
        laginds_ix += pbs->seglens[k];
        delta_blk = blk - prev_lagblk;
        int32_t delta_idx = idx - prev_lagidx;
        int32_t prev_lagidx_mod = prev_lagidx - prev_lagblk * blocksize;
        int32_t delta_range_start = -prev_lagidx_mod + delta_blk * blocksize;
        int cmf_base = (int)(delta_range_start + 2 * blocksize - 1);
        int ix = (int)(delta_idx - delta_range_start);
        uint32_t p0 = delta_lag_cmf[cmf_base];
        nbits += pe_ec_encode_bits(
            delta_lag_cmf[cmf_base + ix] - p0,
            delta_lag_cmf[cmf_base + ix + 1] - p0,
            delta_lag_cmf[cmf_base + (int)blocksize] - p0);
        prev_lagblk = blk;
        prev_lagidx = idx;
    }
    return nbits;
}

/* Spectral harmonicity with per-survivor cache */
static float pe_spectral_harm_cached(float avg_lag, const float *f2w, int f2w_len,
                                      float *cache, int cache_len, int reset) {
    const float harm_undef = -10000.0f;
    if (reset) {
        for (int i = 0; i < cache_len; i++) cache[i] = harm_undef;
    }
    float inv_f2_step_hz = 2.0f * (float)(f2w_len - 1) / 16000.0f;
    float harm_hz = 16000.0f / avg_lag;
    int harm_ix = (int)round((double)(harm_hz * 2.0f * inv_f2_step_hz));
    if (harm_ix < 0 || harm_ix >= cache_len)
        return smpl_harm_strength_at(avg_lag, f2w, f2w_len);
    if (cache[harm_ix] > harm_undef)
        return cache[harm_ix];
    float hs = smpl_harm_strength_at(avg_lag, f2w, f2w_len);
    cache[harm_ix] = hs;
    return hs;
}

static float pe_get_prev_lag_bias(float prev_lag, float prev_pitch_corr, float lag) {
    float lag_diff = (float)fabs((double)(lag - prev_lag));
    float diff_thres = PE_PREVWGHT_SPAN * prev_lag;
    if (lag_diff < diff_thres)
        return prev_pitch_corr * (1.0f - lag_diff / diff_thres) * PE_PREVWGHT;
    return 0.0f;
}

/* ── Track index survivors ────────────────────────────────────────────────── */

static int get_track_idx_survivors(pitch_tables_t *tab, const float hblk[PE_NUM_SUBFR][PE_PITCH_NUM_BLOCKS],
                                   const float *e2, const float *sf_wght, int *track_idx, int max_k) {
    float *utils = (float *)malloc((size_t)tab->num_blocktracks * sizeof(float));
    if (!utils) return 0;

    int blocksize_fs = PE_PITCHBLOCK * 2; /* 64 */
    float pitch_deltawght = PE_PITCH_DELTAWGHT / (float)blocksize_fs;

    for (int i = 0; i < tab->num_blocktracks; i++) {
        const pitch_block_track_t *bt = &tab->blocktracks[i];
        float corr = 0.0f;
        for (int sf = 0; sf < PE_NUM_SUBFR; sf++)
            corr += hblk[sf][bt->track[sf]] * sf_wght[sf];
        float shortlagbias1 = ((float)PE_MAXPITCH_LEN / ((bt->meanblock + 1.5f) * (float)PE_PITCHBLOCK) - 1.0f) * PE_PITCH_SHORTWGHT1;
        utils[i] = 1.0f / (1.1f - corr) - 0.7f * (float)PE_PITCHBLOCK * pitch_deltawght * bt->trackdeltas + shortlagbias1;
    }
    int count = pe_get_maxi_k(utils, tab->num_blocktracks, max_k, track_idx);
    free(utils);
    return count;
}

/* ── Public API ─────────────────────────────────────────────────────────────── */

void smpl_pitch_run(float *prev_lag, float *prev_pitch_corr,
                    int32_t *prev_lagblk, int32_t *prev_lagidx,
                    const float *ltp_buf, const float *f2,
                    bool coded_as_active,
                    float *pitchcorr, float *lags, float *avg_lag,
                    float *harm_strength, int *blockseg_idx, int32_t *laginds) {
    pitch_tables_t *tab = &g_pitch_tables;
    const int numsubfrs = PE_NUM_SUBFR;
    int l = SMPL_PITCH_LAG_MAX + 339; /* MaxLTPBufLen = 659 */
    int look = PE_PITCH_LOOKAHEAD_LEN;

    if (!coded_as_active) {
        float min_lag = (float)(PE_MINPITCH_MS * PE_FS_KHZ);
        *prev_lag = 0.0f;
        *prev_pitch_corr = 0.0f;
        *prev_lagblk = -1;
        *prev_lagidx = -1;
        *pitchcorr = 0.0f;
        *avg_lag = min_lag;
        *harm_strength = 0.0f;
        *blockseg_idx = 0;
        for (int i = 0; i < PE_NUM_SUBFR; i++) { lags[i] = min_lag; laginds[i] = 0; }
        return;
    }

    int offset = PE_DOWNSAMP_DELAY;
    float *stage1 = (float *)malloc((size_t)(l + offset + 64) * sizeof(float));
    float *ltp_buf_hp = (float *)malloc((size_t)(l - look) * sizeof(float));
    float *stage1_ds = (float *)malloc((size_t)((l + offset) / 2 + 8) * sizeof(float));
    if (!stage1 || !ltp_buf_hp || !stage1_ds) { free(stage1); free(ltp_buf_hp); free(stage1_ds); return; }

    pe_hp_filter(ltp_buf, stage1 + offset, l);
    memcpy(ltp_buf_hp, stage1 + offset, (size_t)(l - look) * sizeof(float));

    int stage1_len = pe_downsample(stage1, l + offset, stage1_ds);
    free(stage1); stage1 = NULL;

    int numlags0 = PE_NUM_LAGS_STAGE1;
    float *e1 = (float *)malloc((size_t)(numlags0 * numsubfrs + 16) * sizeof(float));
    float *e2 = (float *)malloc((size_t)(numsubfrs * 2) * sizeof(float)); /* extra space for later */
    int cap = (2 * PE_FS_KHZ / PE_STAGE1_FS_KHZ) * PE_NUM_LAGS_STAGE1 * numsubfrs + 64;
    float *c = (float *)calloc((size_t)cap, sizeof(float));
    float *e = (float *)calloc((size_t)cap, sizeof(float));
    if (!e1 || !e2 || !c || !e) goto cleanup;

    pe_calc_e1(e1, stage1_ds, stage1_len, numsubfrs, PE_MINPITCH_STAGE1, PE_MAXPITCH_STAGE1, PE_LAG_SUBFR_LEN_STAGE1);
    pe_calc_ce2(c, e2, stage1_ds, stage1_len, numsubfrs);
    free(stage1_ds); stage1_ds = NULL;

    int numlags = numlags0;
    for (int sf = 0; sf < numsubfrs; sf++) {
        float sqrtE2 = (float)sqrt((double)(e2[sf] + 1e-30f));
        for (int i = 0; i < numlags; i++) {
            float sqrtE1 = (float)sqrt((double)(e1[sf * numlags + i] + 1e-30f));
            float tmp = 0.5f * (sqrtE1 + sqrtE2);
            e[sf * numlags + i] = tmp * tmp;
        }
    }

    int minpitch_c = PE_MINPITCH_STAGE1, numlags_c = numlags;
    int minpitch_e = PE_MINPITCH_STAGE1, numlags_e = numlags;
    pe_upsamp_c_fast(c, numsubfrs, &minpitch_c, &numlags_c);
    pe_upsamp_e_fast(e, numsubfrs, &minpitch_e, &numlags_e);

    int minpitch_coarse = PE_FS_KHZ * PE_MINPITCH_MS;
    int numlags_coarse = PE_NUMLAGS_COARSE;
    int offset_c0 = minpitch_coarse - minpitch_c;
    int offset_e0 = minpitch_coarse - minpitch_e;

    float *h = (float *)malloc((size_t)(numlags_coarse * numsubfrs * 2 + 64) * sizeof(float));
    if (!h) goto cleanup;
    for (int sf = 0; sf < numsubfrs; sf++) {
        for (int i = 0; i < numlags_coarse; i++) {
            float cv = c[sf * numlags_c + offset_c0 + i];
            float ev = e[sf * numlags_e + offset_e0 + i];
            h[sf * numlags_coarse + i] = cv / ev;
        }
    }

    int pitchblock_coarse = PE_PITCHBLOCK_MS * PE_FS_KHZ; /* 32 */
    float hblk[PE_NUM_SUBFR][PE_PITCH_NUM_BLOCKS];
    for (int sf = 0; sf < numsubfrs; sf++) {
        for (int block = 0; block < PE_PITCH_NUM_BLOCKS; block++) {
            int base = sf * numlags_coarse + block * pitchblock_coarse;
            hblk[sf][block] = pe_maximum(h + base, pitchblock_coarse);
        }
    }

    float sum_e2 = 0.0f;
    float sf_wght[PE_NUM_SUBFR];
    for (int sf = 0; sf < numsubfrs; sf++) sum_e2 += e2[sf];
    for (int sf = 0; sf < numsubfrs; sf++) sf_wght[sf] = e2[sf] / sum_e2;

    int track_idx[PE_NUMSTATES1];
    int n_tracks = get_track_idx_survivors(tab, hblk, e2, sf_wght, track_idx, PE_NUMSTATES1);

    /* E1 at full rate */
    float *e1_fs = (float *)malloc((size_t)(numlags_e * numsubfrs + 16) * sizeof(float));
    if (!e1_fs) goto cleanup;
    pe_calc_e1(e1_fs, ltp_buf_hp, l - look, numsubfrs, minpitch_e, minpitch_e + numlags_e - 1, PE_LAG_SUBFR_LEN);

    /* Unique blocks from survivors */
    uint16_t uniqueblocks[PE_NUM_SUBFR];
    memset(uniqueblocks, 0, sizeof(uniqueblocks));
    for (int ti = 0; ti < n_tracks; ti++) {
        const pitch_block_track_t *track = &tab->blocktracks[track_idx[ti]];
        for (int sf = 0; sf < numsubfrs; sf++)
            uniqueblocks[sf] |= (uint16_t)(1u << (unsigned)track->track[sf]);
    }

    float h_thres = 0.25f;
    int offset_c = PE_MINPITCH_MS * PE_FS_KHZ - minpitch_c;
    int offset_e = PE_MINPITCH_MS * PE_FS_KHZ - minpitch_e;
    for (int sf = 0; sf < numsubfrs; sf++) {
        uint16_t mask = 1;
        int c_ptr = offset_c + sf * numlags_c;
        int e_ptr = offset_e + sf * numlags_e;
        int e1_ptr = offset_e + sf * numlags_e;
        int h_ptr = sf * PE_NUMLAGS_FS;
        int ltp_off = (l - look) + (sf - numsubfrs) * PE_LAG_SUBFR_LEN;
        float e2sf = maxF32(pe_dot_prod40(ltp_buf_hp + ltp_off, ltp_buf_hp + ltp_off), 1e-9f);
        e2[sf] = e2sf;
        float sqrtE2 = (float)sqrt((double)(e2sf + 1e-30f));
        for (int block = 0; block < PE_PITCH_NUM_BLOCKS; block++) {
            if (uniqueblocks[sf] & mask) {
                for (int i = 0; i < PE_PITCHBLOCK + 1; i++) {
                    float sqrtE1 = (float)sqrt((double)(e1_fs[e1_ptr + block * PE_PITCHBLOCK + i] + 1e-30f));
                    float tmp = 0.5f * (sqrtE1 + sqrtE2);
                    e[e_ptr + block * PE_PITCHBLOCK + i] = 0.5f * tmp * tmp;
                }
                for (int i = 0; i < PE_PITCHBLOCK; i++) {
                    if (h[h_ptr + block * PE_PITCHBLOCK + i] > h_thres) {
                        int lag = PE_MINPITCH_LEN + block * PE_PITCHBLOCK + i;
                        const float *a = ltp_buf_hp + ltp_off;
                        const float *b = ltp_buf_hp + ltp_off - lag;
                        c[c_ptr + block * PE_PITCHBLOCK + i] = 0.5f * pe_dot_prod40(a, b);
                    }
                }
            }
            mask <<= 1;
        }
    }

    /* Upsample unique blocks to full rate */
    int stride_c = PE_PITCH_NUM_BLOCKS * 2 * PE_PITCHBLOCK + offset_c;
    int stride_e = PE_PITCH_NUM_BLOCKS * 2 * PE_PITCHBLOCK + offset_e;
    for (int sf = numsubfrs - 1; sf >= 0; sf--) {
        int c_ptr = offset_c + sf * numlags_c;
        int c_ptr_frac = offset_c + sf * stride_c;
        int e_ptr = offset_e + sf * numlags_e;
        int e_ptr_frac = offset_e + sf * stride_e;
        int h_ptr = sf * 2 * PE_PITCHBLOCK * PE_PITCH_NUM_BLOCKS;
        uint16_t mask = (uint16_t)(1u << (unsigned)(PE_PITCH_NUM_BLOCKS - 1));
        for (int block = PE_PITCH_NUM_BLOCKS - 1; block >= 0; block--) {
            if (uniqueblocks[sf] & mask) {
                int ein = e_ptr + block * PE_PITCHBLOCK;
                int eout = e_ptr_frac + block * 2 * PE_PITCHBLOCK;
                pe_upsamp_e_core(e, ein + PE_PITCHBLOCK - 1, eout + 2 * PE_PITCHBLOCK - 1, PE_PITCHBLOCK);
                int cin = c_ptr + block * PE_PITCHBLOCK;
                int cout = c_ptr_frac + block * 2 * PE_PITCHBLOCK;
                pe_upsamp_c_core(c, cin + PE_PITCHBLOCK - 1, cout + 2 * PE_PITCHBLOCK - 1, PE_PITCHBLOCK);
                for (int i = 0; i < 2 * PE_PITCHBLOCK; i++)
                    h[h_ptr + block * 2 * PE_PITCHBLOCK + i] = c[cout + i] / e[eout + i];
            }
            mask >>= 1;
        }
    }

    /* Fine search */
    int blocksize_fs = PE_PITCHBLOCK * 2; /* 64 */
    /* Build survivors: for each track_idx, iterate blockseg_ix range */
    /* count survivors first, then allocate */
    int total_surv = 0;
    for (int ti = 0; ti < n_tracks; ti++) {
        int rng0 = tab->blocksegs_ix[track_idx[ti]][0];
        int rng1 = tab->blocksegs_ix[track_idx[ti]][1];
        total_surv += rng1;
    }
    if (total_surv == 0) goto cleanup;

    int32_t *laginds_surv = (int32_t *)malloc((size_t)total_surv * PE_NUM_SUBFR * sizeof(int32_t));
    int *bsx_list = (int *)malloc((size_t)total_surv * sizeof(int));
    if (!laginds_surv || !bsx_list) { free(laginds_surv); free(bsx_list); goto cleanup; }

    float *h_comb = (float *)calloc((size_t)(2 * PE_PITCHBLOCK), sizeof(float));
    if (!h_comb) { free(laginds_surv); free(bsx_list); goto cleanup; }

    int surv_idx = 0;
    for (int ti = 0; ti < n_tracks; ti++) {
        int rng0 = tab->blocksegs_ix[track_idx[ti]][0];
        int rng1 = tab->blocksegs_ix[track_idx[ti]][1];
        for (int j = 0; j < rng1; j++) {
            int bsx = rng0 + j;
            const pitch_block_seg_t *pbs = &tab->blocksegs[bsx];
            int32_t *row = laginds_surv + surv_idx * PE_NUM_SUBFR;
            int start_sf = 0;
            for (int n = 0; n < pbs->nblocks; n++) {
                /* Combine h across seg_subframes for this block */
                for (int v = 0; v < 2 * PE_PITCHBLOCK; v++) h_comb[v] = 0.0f;
                for (int sf = start_sf; sf < start_sf + pbs->seglens[n]; sf++) {
                    int h_ptr = sf * 2 * PE_PITCHBLOCK * PE_PITCH_NUM_BLOCKS + pbs->blocks[n] * 2 * PE_PITCHBLOCK;
                    for (int v = 0; v < 2 * PE_PITCHBLOCK; v++)
                        h_comb[v] += h[h_ptr + v] * e2[sf];
                }
                int best_i = pe_get_maxi(h_comb, 2 * PE_PITCHBLOCK);
                for (int sf = start_sf; sf < start_sf + pbs->seglens[n]; sf++)
                    row[sf] = (int32_t)(best_i + pbs->blocks[n] * 2 * PE_PITCHBLOCK);
                start_sf += pbs->seglens[n];
            }
            bsx_list[surv_idx] = bsx;
            surv_idx++;
        }
    }
    int n_surv = surv_idx;

    /* Evaluate survivors */
    int max_ix = pe_get_maxi(sf_wght, numsubfrs);
    float spectral_harm_cache[50];
    float best_util = 0.0f, best_pitchcorr = 0.0f;
    int best_surv = 0;
    float pitch_deltawght_fs = PE_PITCH_DELTAWGHT / (float)blocksize_fs;

    for (int surv = 0; surv < n_surv; surv++) {
        float sum_c = 0.0f, sum_e = 0.0f;
        for (int sf = 0; sf < numsubfrs; sf++) {
            int c_base = offset_c + sf * stride_c;
            int e_base = offset_e + sf * stride_e;
            int li = (int)laginds_surv[surv * PE_NUM_SUBFR + sf];
            sum_c += c[c_base + li];
            sum_e += e[e_base + li];
        }
        float rate_bias = pe_encode_lags_bits(tab, bsx_list[surv],
            laginds_surv + surv * PE_NUM_SUBFR, *prev_lagblk, *prev_lagidx, 1) * PE_RATEWGHT_HR;
        float mean_lag = (float)laginds_surv[surv * PE_NUM_SUBFR + max_ix] * 0.5f + (float)PE_MINPITCH_LEN;
        float pc_surv = sum_c / sum_e;
        float first_lag = 0.5f * (float)laginds_surv[surv * PE_NUM_SUBFR] + (float)PE_MINPITCH_LEN;
        float prev_lag_bias = pe_get_prev_lag_bias(*prev_lag, *prev_pitch_corr, first_lag);
        float spectral_harm_bias = PE_SPEC_HARM_BIAS * pe_spectral_harm_cached(
            mean_lag, f2, SMPL_F_LEN, spectral_harm_cache, 50, surv == 0);
        float util = 1.0f / (1.1f - pc_surv)
            - pitch_deltawght_fs * (float)pe_sum_deltas(laginds_surv + surv * PE_NUM_SUBFR, numsubfrs)
            + spectral_harm_bias + prev_lag_bias - rate_bias;
        if (surv == 0 || util > best_util) { best_util = util; best_surv = surv; }
        if (surv == 0 || pc_surv > best_pitchcorr) best_pitchcorr = pc_surv;
    }

    /* Output */
    for (int sf = 0; sf < numsubfrs; sf++) {
        lags[sf] = (float)laginds_surv[best_surv * PE_NUM_SUBFR + sf] * 0.5f + (float)PE_MINPITCH_LEN;
        laginds[sf] = laginds_surv[best_surv * PE_NUM_SUBFR + sf];
    }
    *avg_lag = (float)laginds_surv[best_surv * PE_NUM_SUBFR + max_ix] * 0.5f + (float)PE_MINPITCH_LEN;
    *harm_strength = pe_spectral_harm_cached(*avg_lag, f2, SMPL_F_LEN, spectral_harm_cache, 50, false);
    *pitchcorr = best_pitchcorr;
    *blockseg_idx = bsx_list[best_surv];

    *prev_lag = lags[numsubfrs - 1];
    *prev_pitch_corr = best_pitchcorr;
    *prev_lagidx = laginds_surv[best_surv * PE_NUM_SUBFR + numsubfrs - 1];
    *prev_lagblk = *prev_lagidx / (int32_t)(2 * PE_PITCHBLOCK);

    free(h_comb);
    free(laginds_surv);
    free(bsx_list);

cleanup:
    free(stage1);
    free(ltp_buf_hp);
    free(stage1_ds);
    free(e1);
    free(e2);
    free(c);
    free(e);
    free(h);
    free(e1_fs);
}