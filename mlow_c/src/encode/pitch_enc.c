/*
 * pitch_enc.c — Pitch/LTP wire-format encoding.
 *
 * Inverse of DecodeSmplPitch: encodes LTP gains, filter indices, and
 * pitch lag contour to the range encoder.
 */
#include "encode.h"
#include "../tables/cc_tables.h"
#include "../tables/pitch_seed.h"
#include "../range_coder.h"
#include <string.h>

/* ── encode_lags_wire ──────────────────────────────────────────────────────── */

static void encode_lags_wire(pitch_tables_t *tab, RangeEncoder *enc,
                              int blocksegs_ix, const int32_t *laginds,
                              int32_t prev_lagblk, int32_t prev_lagidx, int mode) {
    int32_t ix_julia = (int32_t)tab->blocksegs2idx[blocksegs_ix];
    int32_t blocksize = 64; /* pePitchblockMs * peFsKhz * 2 */
    pitch_block_seg_t *pbs = &tab->blocksegs[blocksegs_ix];

    if (prev_lagblk < 0) {
        const uint32_t *cmf = tab->blockseg_idx_cmf;
        range_enc_encode(enc, cmf[ix_julia - 1], cmf[ix_julia], cmf[tab->num_blocksegs]);
    } else {
        const uint32_t *cmf = tab->block_transition_cmf[prev_lagblk];
        int32_t b0 = pbs->blocks[0];
        range_enc_encode(enc, cmf[b0], cmf[b0 + 1], cmf[PITCH_NUM_BLOCKS]);
        int32_t start_ix = tab->firstblock_range[b0][0];
        int32_t cmf_len = tab->firstblock_range[b0][1] - start_ix + 1;
        const uint32_t *cmf2 = tab->blockseg_idx_cmf + start_ix;
        uint32_t base = cmf2[0];
        range_enc_encode(enc,
            cmf2[ix_julia - start_ix - 1] - base,
            cmf2[ix_julia - start_ix] - base,
            cmf2[cmf_len] - base);
    }

    int32_t blk = pbs->blocks[0];
    int32_t delta_blk = blk - prev_lagblk;
    int start_seg = 0;
    int laginds_ix = 0;
    if (!(prev_lagblk > -1 && delta_blk >= -1 && delta_blk <= 2)) {
        uint32_t idx_mod = (uint32_t)(laginds[laginds_ix] - blk * blocksize);
        range_enc_encode(enc, idx_mod, idx_mod + 1, (uint32_t)blocksize);
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
        range_enc_encode(enc,
            delta_lag_cmf[cmf_base + ix] - p0,
            delta_lag_cmf[cmf_base + ix + 1] - p0,
            delta_lag_cmf[cmf_base + (int)blocksize] - p0);
        prev_lagblk = blk;
        prev_lagidx = idx;
    }
}

/* ── smpl_lags_predictor_after ──────────────────────────────────────────────── */

void smpl_lags_predictor_after(int blocksegs_ix, const int32_t *laginds,
                                int32_t *out_blk, int32_t *out_idx) {
    pitch_tables_t *tab = &g_pitch_tables;
    pitch_block_seg_t *pbs = &tab->blocksegs[blocksegs_ix];
    *out_blk = pbs->blocks[pbs->nblocks - 1];
    *out_idx = laginds[NUM_SUBFRAMES - 1];
}

/* ── Helpers for LTP gain CDF access ───────────────────────────────────────── */

static const uint16_t *acbgain_row(const cc_tables_t *cc, int32_t prev, int lr) {
    int32_t row = prev + 1;
    if (lr)
        return cc->acbgains_lr + row * (CC_ACBG_N + 1);
    else
        return cc->acbgains_hr + row * (CC_ACBG_N + 1);
}

static void acbgain_weights(const cc_tables_t *cc, int32_t gi, int lr, int32_t *w0, int32_t *w2) {
    const int16_t *w;
    if (lr)
        w = cc->acbgains_cb_lr_q14;
    else
        w = cc->acbgains_cb_hr_q14;
    *w0 = (int32_t)w[gi * 2];
    *w2 = (int32_t)w[gi * 2 + 1];
}

/* ── encode_smpl_pitch ─────────────────────────────────────────────────────── */

void encode_smpl_pitch(RangeEncoder *enc, smpl_lsf_state_t *st,
                       int32_t p3, int32_t p6,
                       const int32_t subfr_counts[4],
                       const smpl_pitch_params_t *pp) {
    const cc_tables_t *cc = &g_cc_tables;

    /* LTP gains loop */
    int32_t gain_accum = 0;
    int take = (int)p3;
    if (take > 4) take = 4;
    for (int sf = 0; sf < take; sf++) {
        int32_t cnt = subfr_counts[sf];
        int32_t gi = pp->gain_idx[sf];

        const uint16_t *cdf = acbgain_row(cc, st->prev_gain_idx, p6 != 0);
        range_enc_encode_cdf(enc, gi, cdf, CC_ACBG_N + 1);
        st->prev_gain_idx = gi;

        int32_t w0, w2;
        acbgain_weights(cc, gi, p6 != 0, &w0, &w2);
        gain_accum += w0 + 2 * w2;

        if (cnt > 0) {
            int32_t fi = pp->filt_idx[sf];
            if (st->prev_filt_idx == -1)
                range_enc_encode_cdf(enc, fi, cc->fcbgains_v, CC_FCBG_VN + 1);
            else {
                int start = CC_FCBG_VN - 1 - (int)st->prev_filt_idx;
                range_enc_encode_cdf(enc, fi, &cc->fcbgains_v_delta[start], 35);
            }
            st->prev_filt_idx = fi;
        }
    }

    int32_t avg_gain = gain_accum / p3;
    int mode = 0;
    if (avg_gain >= 10007) {
        if (avg_gain < 14085) mode = 1;
        else mode = 2;
    }

    pitch_tables_t *tab = &g_pitch_tables;
    encode_lags_wire(tab, enc, pp->blockseg_idx, pp->laginds,
                     st->prev_lagblk, st->prev_lagidx, mode);
    smpl_lags_predictor_after(pp->blockseg_idx, pp->laginds,
                               &st->prev_lagblk, &st->prev_lagidx);
}