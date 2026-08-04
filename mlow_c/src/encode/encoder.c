/*
 * encoder.c — Top-level encoder pipeline + entropy coder.
 */
#include "encode.h"
#include "../seed.h"
#include "../tables/lsf_seed.h"
#include "../tables/cc_tables.h"
#include "../tables/pitch_seed.h"
#include "../mem.h"
#include "../range_coder.h"
#include <math.h>
#include <string.h>
#include <stdlib.h>

/* ── smplPulseCountByte ────────────────────────────────────────────────────── */
static const uint8_t smpl_pulse_count_byte[8] = {80, 160, 160, 16, 32, 32, 0, 0};

static uint8_t mem8_static_enc(uint32_t addr) {
    if (addr >= 0xe8990 && addr < 0xe8998) return smpl_pulse_count_byte[addr - 0xe8990];
    return 0;
}

/* ── cdfWindow ────────────────────────────────────────────────────────────── */
static void cdf_window_enc(const uint16_t *base, int base_len, int start, int n, uint16_t *out) {
    for (int i = 0; i < n; i++) {
        int j = start + i;
        out[i] = (j >= 0 && j < base_len) ? base[j] : 0;
    }
}

/* ── encodeSmplLsf ────────────────────────────────────────────────────────── */
static void encode_smpl_lsf(RangeEncoder *enc, smpl_lsf_state_t *st, int config, int intf,
                            const smpl_lsf_params_t *lsf) {
    int sel = 0;
    if (intf != 0) sel = (st->prev_stage1 != 0) ? 2 : 1;
    int32_t stage1 = lsf->stage1;
    range_enc_encode_cdf(enc, stage1, g_smpl_tables.lsf_sel[sel], 3);

    bool m = (intf != 0) && (stage1 == st->prev_stage1);
    if (!m) {
        st->prev_gain_idx = -1; st->prev_filt_idx = -1;
        st->prev_lag = -1; st->prev_frac_lag = -1;
        st->prev_lagblk = -1; st->prev_lagidx = -1;
    }
    st->prev_stage1 = stage1;

    const uint16_t *grid_cdf; int grid_cdf_len;
    if (m && stage1 != 0) { grid_cdf = g_smpl_tables.match1; grid_cdf_len = 18; }
    else if (m) { grid_cdf = g_smpl_tables.match1_alt; grid_cdf_len = 18; }
    else if (stage1 != 0) { grid_cdf = g_smpl_tables.match0_alt; grid_cdf_len = 17; }
    else { grid_cdf = g_smpl_tables.match0; grid_cdf_len = 17; }
    range_enc_encode_cdf(enc, lsf->grid, grid_cdf, grid_cdf_len);
    st->prev_match = m; st->have_prev = true;

    for (int k = 0; k < 16; k++) {
        const uint16_t *cdf = g_smpl_tables.lsf_stage2_ptr[stage1][config][lsf->grid][k];
        int cdf_len = g_smpl_tables.lsf_stage2_len[stage1][config][lsf->grid][k];
        range_enc_encode_cdf(enc, lsf->stage2[k], cdf, cdf_len);
    }
    range_enc_encode_cdf(enc, lsf->extra, g_smpl_tables.lsf_extra, 3);
}

/* ── encodeSplit3537 ──────────────────────────────────────────────────────── */
static void encode_split_3537(RangeEncoder *enc, int32_t count, int32_t granularity, int32_t s0) {
    int32_t lo = count;
    if (granularity < lo) lo = granularity;
    int32_t min_split = count - granularity;
    if (min_split < 0) min_split = 0;
    if (lo < min_split || min_split == lo) return;
    int total_idx = count - 1;
    if (total_idx < 0 || total_idx >= g_cc_tables.num_split_cmfs) return;
    const uint16_t *split_cmf = &g_cc_tables.split_cmfs_data[g_cc_tables.split_cmfs_offsets[total_idx]];
    int split_cmf_len = g_cc_tables.split_cmfs_offsets[total_idx + 1] - g_cc_tables.split_cmfs_offsets[total_idx];
    uint16_t window[256];
    cdf_window_enc(split_cmf, split_cmf_len, (int)min_split, (int)(lo - min_split + 2), window);
    range_enc_encode_cdf(enc, s0 - min_split, window, (int)(lo - min_split + 2));
}

/* ── encodeSmplPulses ──────────────────────────────────────────────────────── */
static void encode_smpl_pulses(RangeEncoder *enc, int32_t p2, int32_t p3, int32_t p4,
                                int32_t p6, int32_t s1, const smpl_pulse_params_t *pp) {
    int idx = p4 + s1;
    int32_t b_byte = (int32_t)mem8_static_enc(0xe8990 + (uint32_t)(p6 * 3 + idx));
    int32_t frame_len4k = b_byte * p2 / 320;
    int32_t subfr_len16 = frame_len4k / p3;
    int32_t total = pp->total;

    /* pulse COUNT (NB triangular; config=0) */
    uint32_t l = (uint32_t)frame_len4k;
    /* triT(k) = ((k+2)*(l+1) - ((k-1)*(k+131070))>>1) & 0xffff */
    uint32_t ft = 0;
    {
        uint32_t a = (l + 2) * (l + 1);
        uint32_t b = ((l - 1) * (l + 131070)) >> 1;
        ft = (a - b) & 0xffff;
    }
    if (ft == 0) ft = 1;
    uint32_t fl = 0, fh = ft;
    if (total > 0) {
        uint32_t k = (uint32_t)(total - 1);
        uint32_t a = (k + 2) * (l + 1);
        uint32_t b = ((k - 1) * (k + 131070)) >> 1;
        fl = (a - b) & 0xffff;
    }
    {
        uint32_t k = (uint32_t)total;
        uint32_t a = (k + 2) * (l + 1);
        uint32_t b = ((k - 1) * (k + 131070)) >> 1;
        fh = (a - b) & 0xffff;
    }
    range_enc_encode(enc, fl, fh, ft);
    if (total == 0) return;

    /* recursive binary SPLIT */
    int32_t final_sum = pp->subfr[0] + pp->subfr[1];
    int32_t init_sum = total - subfr_len16 * 2;
    if (init_sum < 0) init_sum = 0;
    int32_t lo = total - 80;
    if (lo < 0) lo = 0;
    if (init_sum < lo) return;
    int32_t hi_bound = total - lo;
    if (init_sum < hi_bound) {
        int total_idx = total - 1;
        if (total_idx >= 0 && total_idx < g_cc_tables.num_split_cmfs) {
            const uint16_t *split_cmf = &g_cc_tables.split_cmfs_data[g_cc_tables.split_cmfs_offsets[total_idx]];
            int split_cmf_len = g_cc_tables.split_cmfs_offsets[total_idx + 1] - g_cc_tables.split_cmfs_offsets[total_idx];
            uint16_t window[256];
            cdf_window_enc(split_cmf, split_cmf_len, (int)(init_sum - lo), (int)(hi_bound - init_sum + 2), window);
            range_enc_encode_cdf(enc, final_sum - init_sum, window, (int)(hi_bound - init_sum + 2));
        }
    }
    if (final_sum > 0) encode_split_3537(enc, final_sum, subfr_len16, pp->subfr[0]);
    if (final_sum < total) encode_split_3537(enc, total - final_sum, subfr_len16, pp->subfr[2]);

    /* MAGNITUDE block: replay recorded run-length symbols */
    int pos_per = p2 / p3;
    int mag_idx = 0;
    for (int32_t subfr = 0; subfr < p3; subfr++) {
        int32_t cnt = pp->subfr[subfr];
        if (cnt <= 0) continue;
        int pos = pos_per;
        int32_t c = cnt;
        int32_t k = 0;
        while (k < cnt) {
            int oct = (pos + 7) / 8;
            int oct_idx = oct - 1;
            if (oct_idx < 0 || oct_idx >= g_cc_tables.num_runlen) break;
            int rl_offset = g_cc_tables.runlen_offsets[oct_idx];
            int ms = g_cc_tables.runlen_max_samples[oct_idx];
            int c_idx = c - 1;
            if (c_idx < 0 || c_idx >= 40) break;
            int rl_data_offset = rl_offset + c_idx * (ms + 1);
            int runlen_data_total = (int)(sizeof(g_cc_tables.runlen_data)/sizeof(uint16_t));
            if (rl_data_offset + (ms + 1) > runlen_data_total) break;
            const uint16_t *rl_cmf = &g_cc_tables.runlen_data[rl_data_offset];
            int start = ms - pos;
            int n_entries = pos + 1;
            if (start < 0 || n_entries > 256 || n_entries <= 0) break;
            if (mag_idx >= pp->mag_runs_len) break;
            int32_t m_val = pp->mag_runs[mag_idx++];
            uint16_t window[256];
            cdf_window_enc(rl_cmf, ms + 1, start, n_entries, window);
            range_enc_encode_cdf(enc, m_val, window, n_entries);
            if (m_val > 0 || k == 0) pos -= m_val;
            c--; k++;
        }
    }

    /* SIGN block: replay recorded raw sign symbols */
    for (int i = 0; i < pp->sign_syms_len; i++) {
        range_enc_encode_raw_symbol(enc, pp->sign_syms[i].sym, pp->sign_syms[i].nbits);
    }
}

/* ── encodeSmplGains ────────────────────────────────────────────────────────── */
static void encode_smpl_gains(RangeEncoder *enc, int32_t p3, const int32_t subfr_counts[4],
                               const smpl_gain_params_t *gp) {
    range_enc_encode_cdf(enc, gp->gain_main, g_cc_tables.nrgres_gain4, g_cc_tables.nrgres_gain4_len);
    range_enc_encode_cdf(enc, gp->gain_delta, g_cc_tables.nrgres_shape4, g_cc_tables.nrgres_shape4_len);
    int32_t cfg_sel = 2;

    int32_t off6 = p3 * gp->gain_delta;
    /* NrgStep */
    int32_t nrg_step = 0;
    uint32_t nrg_addr = g_cc_tables.gain_recon_base + (uint32_t)cfg_sel * 2;
    int off = (int)(nrg_addr - g_cc_tables.gain_recon_base);
    if (off >= 0 && off % 2 == 0 && off / 2 < g_cc_tables.gain_recon_len)
        nrg_step = (int32_t)g_cc_tables.gain_recon[off / 2];
    int32_t base7 = gp->gain_main * nrg_step - 0x154000;

    int32_t gain_q[4] = {0};
    int take = p3; if (take > 4) take = 4;
    for (int sf = 0; sf < take; sf++) {
        uint32_t gr_addr = (p3 == 4) ? 0xf35f0u : 0xf3970u;
        gr_addr += (uint32_t)(sf + off6) * 2;
        int gr_off = (int)(gr_addr - g_cc_tables.gain_recon_base);
        int32_t cbv = 0;
        if (gr_off >= 0 && gr_off % 2 == 0 && gr_off / 2 < g_cc_tables.gain_recon_len)
            cbv = (int32_t)g_cc_tables.gain_recon[gr_off / 2];
        gain_q[sf] = base7 + (cbv << 4);
    }

    for (int sf = 0; sf < take; sf++) {
        int32_t cnt = subfr_counts[sf];
        if (cnt <= 0) continue;
        int32_t bucket = (cnt >= 30) ? 3 : (cnt & 0xffff) / 10;
        int32_t g = (gain_q[sf] + 8192) >> 14;
        if (g < -85) g = -85;
        int32_t neg_part = (g >> 31) & g;
        int min_offset = (int)(-neg_part);
        int row = (int)cfg_sel * CC_FCBG_OFFSET_BUCKETS + (int)bucket;
        const uint16_t *offset_cmf = g_cc_tables.fcbg_offset[row];
        uint16_t window[128];
        cdf_window_enc(offset_cmf, 177, min_offset, 92, window);
        range_enc_encode_cdf(enc, gp->nrg_res[sf], window, 92);
    }
}

/* ── EncodeSmplFrame ────────────────────────────────────────────────────────── */
int encode_smpl_frame(const smpl_frame_params_t *fp, uint8_t *out, int max_out) {
    const int32_t p2 = 320, p3 = 4, p4 = 1;
    int32_t p6 = (int32_t)fp->config;

    uint8_t body[1 + 2048]; /* 1 + SmplEncodeBufBytes */
    RangeEncoder enc;
    range_enc_init(&enc, body, (int)sizeof(body));

    smpl_lsf_state_t st;
    memset(&st, 0, sizeof(st));
    st.prev_gain_idx = -1; st.prev_filt_idx = -1;
    st.prev_lag = -1; st.prev_frac_lag = -1;
    st.prev_lagblk = -1; st.prev_lagidx = -1;

    for (int f = 0; f < 3; f++) {
        const smpl_internal_params_t *ip = &fp->internal[f];
        encode_smpl_lsf(&enc, &st, fp->config, f, &ip->lsf);
        encode_smpl_pulses(&enc, p2, p3, p4, p6, ip->lsf.stage1, &ip->pulses);
        if (ip->lsf.stage1 == 1) {
            encode_smpl_pitch(&enc, &st, p3, p6, ip->pulses.subfr, &ip->pitch);
        } else {
            encode_smpl_gains(&enc, p3, ip->pulses.subfr, &ip->gains);
        }
    }
    range_enc_done(&enc);
    if (enc.err != 0) return -1;

    int n = range_enc_consumed_len(&enc);
    if (1 + n > max_out) return -1;
    out[0] = fp->toc;
    memcpy(out + 1, body, n);
    return 1 + n;
}