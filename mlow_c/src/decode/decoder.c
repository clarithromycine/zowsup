/*
 * decoder.c — Top-level decoder pipeline.
 */

#include "decode.h"
#include "../seed.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>

/* ── smplPulseCountByte (static rodata at 0xe8990) ─────────────────────────── */
static const uint8_t smpl_pulse_count_byte[8] = {80, 160, 160, 16, 32, 32, 0, 0};

static uint8_t mem8_static(uint32_t addr) {
    if (addr >= 0xe8990 && addr < 0xe8998) return smpl_pulse_count_byte[addr - 0xe8990];
    return 0;
}

/* ── cdfWindow ─────────────────────────────────────────────────────────────── */
static void cdf_window(const uint16_t *base, int base_len, int start, int n, uint16_t *out) {
    for (int i = 0; i < n; i++) {
        int j = start + i;
        out[i] = (j >= 0 && j < base_len) ? base[j] : 0;
    }
}

/* ── DecodeSmplLsf ─────────────────────────────────────────────────────────── */
smpl_lsf_indices_t decode_smpl_lsf(RangeDecoder *dec, smpl_lsf_state_t *st, int config, int intf) {
    smpl_lsf_indices_t idx;
    memset(&idx, 0, sizeof(idx));

    /* Read 1 — stage-1 selector */
    int sel = 0;
    if (intf != 0) sel = (st->prev_stage1 != 0) ? 2 : 1;
    int32_t stage1 = range_dec_decode_cdf(dec, g_smpl_tables.lsf_sel[sel], 3);
    idx.stage1 = stage1;

    /* match := (not first frame) && stage1 == prev */
    bool m = (intf != 0) && (stage1 == st->prev_stage1);
    if (!m) {
        st->prev_gain_idx = -1;
        st->prev_filt_idx = -1;
        st->prev_lag = -1;
        st->prev_frac_lag = -1;
    }
    st->prev_stage1 = stage1;

    /* Read 2 — stage-1 grid */
    const uint16_t *grid_cdf;
    int grid_cdf_len;
    if (m && stage1 != 0) { grid_cdf = g_smpl_tables.match1; grid_cdf_len = 18; }
    else if (m) { grid_cdf = g_smpl_tables.match1_alt; grid_cdf_len = 18; }
    else if (stage1 != 0) { grid_cdf = g_smpl_tables.match0_alt; grid_cdf_len = 17; }
    else { grid_cdf = g_smpl_tables.match0; grid_cdf_len = 17; }
    int32_t grid = range_dec_decode_cdf(dec, grid_cdf, grid_cdf_len);
    idx.grid = grid;
    st->prev_match = m;
    st->have_prev = true;

    /* Read 3 — 16 stage-2 residuals */
    for (int k = 0; k < 16; k++) {
        const uint16_t *cdf = g_smpl_tables.lsf_stage2_ptr[stage1][config][grid][k];
        int cdf_len = g_smpl_tables.lsf_stage2_len[stage1][config][grid][k];
        idx.stage2[k] = range_dec_decode_cdf(dec, cdf, cdf_len);
        idx.stage_nraw[k] = cdf_len - 2;
    }

    /* Read 4 — extra LSF CDF */
    idx.extra = range_dec_decode_cdf(dec, g_smpl_tables.lsf_extra, 3);
    return idx;
}

/* ── smplSplit3537 ──────────────────────────────────────────────────────────── */
static int32_t smpl_split_3537(RangeDecoder *dec, int32_t count, int32_t granularity) {
    int32_t lo = count;
    if (granularity < lo) lo = granularity;
    int32_t min_split = count - granularity;
    if (min_split < 0) min_split = 0;
    if (lo < min_split) return -1;
    if (min_split == lo) return min_split;
    int n = (lo - min_split) + 2;

    /* Get split CDF for this count */
    int total = count - 1;
    if (total < 0 || total >= g_cc_tables.num_split_cmfs) return -1;
    const uint16_t *split_cmf = &g_cc_tables.split_cmfs_data[g_cc_tables.split_cmfs_offsets[total]];
    int split_cmf_len = g_cc_tables.split_cmfs_offsets[total + 1] - g_cc_tables.split_cmfs_offsets[total];

    uint16_t window[256];
    cdf_window(split_cmf, split_cmf_len, (int)min_split, n, window);
    return range_dec_decode_cdf(dec, window, n) + min_split;
}

/* ── DecodeSmplPulses ──────────────────────────────────────────────────────── */
smpl_pulse_result_t decode_smpl_pulses(RangeDecoder *dec, int32_t p2, int32_t p3,
                                         int32_t p4, int32_t p6, int32_t s1) {
    int n = p2;
    if (n < 0) n = 0;
    smpl_pulse_result_t res;
    memset(&res, 0, sizeof(res));
    res.pulses = (int32_t *)calloc(n, sizeof(int32_t));

    int idx = p4 + s1;
    int32_t b_byte = (int32_t)mem8_static(0xe8990 + (uint32_t)(p6 * 3 + idx));
    int32_t frame_len4k = b_byte * p2 / 320;
    int32_t subfr_len16 = frame_len4k / p3;
    int32_t pos_per_subfr = p2 / p3;

    /* --- pulse COUNT --- */
    int32_t total = 0;
    if (p6 != 0) {
        const uint16_t *cdf = g_cc_tables.n_pulse_cmfs[idx];
        int cdf_len = g_cc_tables.n_pulse_cmfs_len[idx];
        total = range_dec_decode_cdf(dec, cdf, cdf_len);
    } else {
        /* Triangular prior */
        uint32_t l = (uint32_t)frame_len4k;
        /* triT(k) = ((k+2)*(l+1) - ((k-1)*(k+131070))>>1) & 0xffff */
        uint32_t ft;
        {
            uint32_t a = (l + 2) * (l + 1);
            uint32_t b = ((l - 1) * (l + 131070)) >> 1;
            ft = (a - b) & 0xffff;
        }
        if (ft == 0) ft = 1;
        uint32_t val = range_dec_decode(dec, ft);
        uint32_t limit = (uint32_t)frame_len4k + 1;
        uint32_t prev_cum = 0;
        uint32_t k;
        for (k = 0; k < limit; k++) {
            uint32_t a = (k + 2) * (l + 1);
            uint32_t b = ((k - 1) * (k + 131070)) >> 1;
            uint32_t cum = (a - b) & 0xffff;
            if (prev_cum <= val && val < cum) {
                range_dec_update(dec, prev_cum, cum, ft);
                break;
            }
            prev_cum = cum;
        }
        total = (int32_t)k;
    }

    /* --- recursive binary SPLIT --- */
    int32_t split[8] = {0};
    if (total != 0) {
        int32_t sum = total - subfr_len16 * 2;
        if (sum < 0) sum = 0;
        int32_t lo = total - 80;
        if (lo < 0) lo = 0;
        if (sum < lo) {
            /* Invalid split: set error and let caller clean up */
            dec->Err = 1;
            return res;
        }
        int32_t hi_bound = total - lo;
        if (sum < hi_bound) {
            int total_idx = total - 1;
            if (total_idx >= 0 && total_idx < g_cc_tables.num_split_cmfs) {
                const uint16_t *split_cmf = &g_cc_tables.split_cmfs_data[g_cc_tables.split_cmfs_offsets[total_idx]];
                int split_cmf_len = g_cc_tables.split_cmfs_offsets[total_idx + 1] - g_cc_tables.split_cmfs_offsets[total_idx];
                uint16_t window[256];
                cdf_window(split_cmf, split_cmf_len, (int)(sum - lo), (int)(hi_bound - sum + 2), window);
                sum += range_dec_decode_cdf(dec, window, (int)(hi_bound - sum + 2));
            }
        }
        if (sum > 0) {
            split[0] = smpl_split_3537(dec, sum, subfr_len16);
            split[1] = sum - split[0];
        }
        if (sum < total) {
            split[2] = smpl_split_3537(dec, total - sum, subfr_len16);
            split[3] = (total - sum) - split[2];
        }
        if (split[0] == -1 || split[2] == -1) {
            memset(split, 0, sizeof(split));
        }
    }

    int take = p3;
    if (take < 0) take = 0;
    if (take > 4) take = 4;
    for (int i = 0; i < take; i++) res.subfr[i] = split[i];

    /* --- MAGNITUDE block --- */
    /* Sentinel: allocate extra 16 bytes for overflow detection */
    #define SENTINEL 0xDEADBEEF
    int *pos_list_raw = (int *)malloc(1024 * sizeof(int) + 16);
    int *mag_list_raw = (int *)malloc(1024 * sizeof(int) + 16);
    int *pos_list = pos_list_raw;
    int *mag_list = mag_list_raw;
    ((uint32_t*)(pos_list + 1024))[0] = SENTINEL;
    ((uint32_t*)(pos_list + 1024))[1] = SENTINEL;
    ((uint32_t*)(pos_list + 1024))[2] = SENTINEL;
    ((uint32_t*)(pos_list + 1024))[3] = SENTINEL;
    ((uint32_t*)(mag_list + 1024))[0] = SENTINEL;
    ((uint32_t*)(mag_list + 1024))[1] = SENTINEL;
    ((uint32_t*)(mag_list + 1024))[2] = SENTINEL;
    ((uint32_t*)(mag_list + 1024))[3] = SENTINEL;
    int num_pos = 0;
    int32_t pulse_idx = -1;
    int pos_per = pos_per_subfr;

    for (int32_t subfr = 0; subfr < p3; subfr++) {
        int32_t cnt = split[subfr];
        if (cnt <= 0) continue;
        int base_pos = pos_per * subfr;
        int run_pos = base_pos;
        int pos = pos_per;
        int32_t c = cnt;
        int32_t k = 0;
        while (k < cnt) {
            if (pos < 0) break;
            int oct = (pos + 7) / 8;
            /* Get runlen CDF */
            int oct_idx = oct - 1;
            if (oct_idx < 0 || oct_idx >= g_cc_tables.num_runlen) { dec->Err = 1; break; }
            int rl_offset = g_cc_tables.runlen_offsets[oct_idx];
            int ms = g_cc_tables.runlen_max_samples[oct_idx];
            int c_idx = c - 1;
            if (c_idx < 0 || c_idx >= 40) { dec->Err = 1; break; }
            int rl_data_offset = rl_offset + c_idx * (ms + 1);
            int runlen_data_total = (int)(sizeof(g_cc_tables.runlen_data)/sizeof(uint16_t));
            if (rl_data_offset + (ms + 1) > runlen_data_total) { dec->Err = 1; break; }
            const uint16_t *rl_cmf = &g_cc_tables.runlen_data[rl_data_offset];
            int start = ms - pos;
            int n_entries = pos + 1;
            if (start < 0 || n_entries > 256 || n_entries <= 0) { dec->Err = 1; break; }
            uint16_t window[256];
            cdf_window(rl_cmf, ms + 1, start, n_entries, window);
            int32_t m_val = range_dec_decode_cdf(dec, window, n_entries);
            if (m_val > 0 || k == 0) {
                pulse_idx++;
                if (pulse_idx >= 1024) { dec->Err = 1; pulse_idx = 1023; break; }
                run_pos += m_val;
                pos_list[pulse_idx] = run_pos;
                mag_list[pulse_idx] = 1;
                pos -= m_val;
            } else if (pulse_idx >= 0) {
                mag_list[pulse_idx]++;
            }
            c--;
            k++;
        }
    }

    num_pos = pulse_idx + 1;

    /* --- SIGN block --- */
    if (num_pos > 0) {
        int32_t p = 0;
        while (p <= pulse_idx) {
            int nbits = num_pos - p;
            if (nbits >= 15) nbits = 15;
            if (nbits <= 0) break;
            uint32_t sym = range_dec_decode_raw_symbol(dec, (uint32_t)nbits);
            uint32_t bitfield = sym << (16 - nbits);
            int end = p + nbits;
            for (int q = p; q < end; q++) {
                int32_t sign = (int32_t)((bitfield >> 14) & 2) - 1;
                mag_list[q] *= sign;
                bitfield <<= 1;
            }
            p = end;
        }
    }

    /* scatter */
    for (int i = 0; i < num_pos; i++) {
        int pp = pos_list[i];
        if (pp >= 0 && pp < n) res.pulses[pp] = mag_list[i];
    }
    /* Check sentinels before freeing */
    if (((uint32_t*)(pos_list + 1024))[0] != SENTINEL ||
        ((uint32_t*)(pos_list + 1024))[1] != SENTINEL ||
        ((uint32_t*)(pos_list + 1024))[2] != SENTINEL ||
        ((uint32_t*)(pos_list + 1024))[3] != SENTINEL) {
        fprintf(stderr, "CORRUPTED pos_list sentinel! pulse_idx=%d num_pos=%d\n", (int)pulse_idx, num_pos);
        abort();
    }
    if (((uint32_t*)(mag_list + 1024))[0] != SENTINEL ||
        ((uint32_t*)(mag_list + 1024))[1] != SENTINEL ||
        ((uint32_t*)(mag_list + 1024))[2] != SENTINEL ||
        ((uint32_t*)(mag_list + 1024))[3] != SENTINEL) {
        fprintf(stderr, "CORRUPTED mag_list sentinel! pulse_idx=%d num_pos=%d\n", (int)pulse_idx, num_pos);
        abort();
    }
    free(pos_list_raw);
    free(mag_list_raw);
    return res;
}

/* ── DecodeSmplGains ───────────────────────────────────────────────────────── */
smpl_gain_result_t decode_smpl_gains(RangeDecoder *dec, int32_t p3, const int32_t subfr_counts[4]) {
    smpl_gain_result_t res;
    memset(&res, 0, sizeof(res));

    int32_t gain_main = range_dec_decode_cdf(dec, g_cc_tables.nrgres_gain4, g_cc_tables.nrgres_gain4_len);
    int32_t gain_delta = range_dec_decode_cdf(dec, g_cc_tables.nrgres_shape4, g_cc_tables.nrgres_shape4_len);
    if (gain_main < 0) gain_main = 0;
    if (gain_delta < 0) gain_delta = 0;
    res.gain_main = gain_main;
    res.gain_delta = gain_delta;
    int32_t cfg_sel = 2;

    int32_t off6 = p3 * gain_delta;
    /* NrgStep: gain_recon_at(gain_recon_base + cfg*2) */
    int32_t nrg_step = 0;
    uint32_t nrg_addr = g_cc_tables.gain_recon_base + (uint32_t)cfg_sel * 2;
    int off = (int)(nrg_addr - g_cc_tables.gain_recon_base);
    if (off >= 0 && off % 2 == 0 && off / 2 < g_cc_tables.gain_recon_len) {
        nrg_step = (int32_t)g_cc_tables.gain_recon[off / 2];
    }
    int32_t base7 = gain_main * nrg_step - 0x154000;

    int take = p3;
    if (take > 4) take = 4;
    for (int sf = 0; sf < take; sf++) {
        /* GainRecon: gain_recon_at(base + (sf + off6)*2) */
        uint32_t gr_addr;
        if (p3 == 4) gr_addr = 0xf35f0u;
        else gr_addr = 0xf3970u;
        gr_addr += (uint32_t)(sf + off6) * 2;
        int gr_off = (int)(gr_addr - g_cc_tables.gain_recon_base);
        int32_t cbv = 0;
        if (gr_off >= 0 && gr_off % 2 == 0 && gr_off / 2 < g_cc_tables.gain_recon_len) {
            cbv = (int32_t)g_cc_tables.gain_recon[gr_off / 2];
        }
        res.gain_q[sf] = base7 + (cbv << 4);
    }

    /* nrgres */
    for (int sf = 0; sf < take; sf++) {
        int32_t cnt = subfr_counts[sf];
        if (cnt <= 0) continue;
        int32_t bucket;
        if (cnt >= 30) bucket = 3;
        else bucket = (cnt & 0xffff) / 10;
        int32_t g = (res.gain_q[sf] + 8192) >> 14;
        if (g < -85) g = -85;
        int32_t neg_part = (g >> 31) & g;
        int min_offset = (int)(-neg_part);
        if (min_offset < 0) min_offset = 0;
        if (min_offset > 85) min_offset = 85;

        /* FcbgOffset: fcbg_offset[tableIx * BUCKETS + bucket], 92 entries from min_offset */
        int row = (int)cfg_sel * CC_FCBG_OFFSET_BUCKETS + (int)bucket;
        const uint16_t *offset_cmf = g_cc_tables.fcbg_offset[row];
        uint16_t window[128];
        cdf_window(offset_cmf, 177, min_offset, 92, window);
        res.nrg_res[sf] = range_dec_decode_cdf(dec, window, 92);
    }
    return res;
}

/* ── DecodeSmplPitch ───────────────────────────────────────────────────────── */
smpl_pitch_result_t decode_smpl_pitch(RangeDecoder *dec, smpl_lsf_state_t *st,
                                       int32_t p2, int32_t p3, int32_t p6,
                                       const int32_t subfr_counts[4]) {
    smpl_pitch_result_t res;
    memset(&res, 0, sizeof(res));
    res.filt_idx[0] = -1; res.filt_idx[1] = -1; res.filt_idx[2] = -1; res.filt_idx[3] = -1;

    /* --- LTP gains loop --- */
    int32_t gain_accum = 0;
    int take = p3;
    if (take > 4) take = 4;
    for (int sf = 0; sf < take; sf++) {
        int32_t cnt = subfr_counts[sf];
        int32_t gi;
        int pg = st->prev_gain_idx; if (pg < -1) pg = -1; if (pg > 15) pg = 15;
        int base = (pg + 1) * (CC_ACBG_N + 1);
        if (base < 0) base = 0;
        if (base + CC_ACBG_N + 1 > (int)(sizeof(g_cc_tables.acbgains_hr)/sizeof(uint16_t))) base = 0;
        if (p6 != 0) {
            gi = range_dec_decode_cdf(dec, &g_cc_tables.acbgains_lr[base], CC_ACBG_N + 1);
        } else {
            gi = range_dec_decode_cdf(dec, &g_cc_tables.acbgains_hr[base], CC_ACBG_N + 1);
        }
        if (gi < 0) gi = 0; if (gi > 15) gi = 15;
        res.gain_idx[sf] = gi;
        st->prev_gain_idx = gi;

        int32_t w0, w2;
        if (p6 != 0) {
            w0 = (int32_t)g_cc_tables.acbgains_cb_lr_q14[gi * 2];
            w2 = (int32_t)g_cc_tables.acbgains_cb_lr_q14[gi * 2 + 1];
        } else {
            w0 = (int32_t)g_cc_tables.acbgains_cb_hr_q14[gi * 2];
            w2 = (int32_t)g_cc_tables.acbgains_cb_hr_q14[gi * 2 + 1];
        }
        gain_accum += w0 + 2 * w2;

        if (cnt > 0) {
            int32_t fi;
            int pfi = st->prev_filt_idx; if (pfi < -1) pfi = -1; if (pfi > 33) pfi = 33;
            if (pfi == -1) {
                fi = range_dec_decode_cdf(dec, g_cc_tables.fcbgains_v, CC_FCBG_VN + 1);
            } else {
                int start = CC_FCBG_VN - 1 - pfi;
                if (start < 0) start = 0;
                fi = range_dec_decode_cdf(dec, &g_cc_tables.fcbgains_v_delta[start], 35);
            }
            if (fi < 0) fi = 0; if (fi > 33) fi = 33;
            res.filt_idx[sf] = fi;
            st->prev_filt_idx = fi;
        }
    }
    int32_t avg_gain = gain_accum / p3;

    /* --- Lag block --- */
    uint32_t pcfg = g_smpl_mem.GClk + 0x5704;
    int32_t num_contours = (int32_t)smpl_mem_u32(pcfg + 22240);
    uint32_t lag_cdf = smpl_mem_u32(pcfg + 22248);
    uint32_t contour_map = smpl_mem_u32(pcfg + 22244);
    uint32_t frac_base = smpl_mem_u32(pcfg + 22252);
    uint32_t delta_cdf = smpl_mem_u32(pcfg + 22268);

    int32_t lag;
    if (st->prev_lag < 0) {
        int cnt = num_contours + 1;
        if (cnt < 0) cnt = 0;
        uint16_t *cdf = (uint16_t *)malloc(cnt * sizeof(uint16_t));
        smpl_mem_cdf_at(lag_cdf, cnt, cdf);
        lag = range_dec_decode_cdf(dec, cdf, cnt);
        free(cdf);
    } else {
        uint16_t cdf[10];
        smpl_mem_cdf_at(delta_cdf + (uint32_t)st->prev_lag * 20, 10, cdf);
        int32_t di = range_dec_decode_cdf(dec, cdf, 10);
        int32_t lo = (int32_t)smpl_mem_u8(0xe7ef0 + (uint32_t)di * 2);
        int32_t hi = (int32_t)smpl_mem_u8(0xe7ef0 + (uint32_t)di * 2 + 1);
        int32_t r_n = (hi - lo) + 2;
        if (r_n < 2) { res.lag = -1; return res; }
        uint16_t *cdf2 = (uint16_t *)malloc(r_n * sizeof(uint16_t));
        smpl_mem_cdf_at(lag_cdf + (uint32_t)lo * 2, r_n, cdf2);
        int32_t sym = range_dec_decode_cdf(dec, cdf2, r_n);
        free(cdf2);
        lag = sym + lo;
    }

    /* contour-map search */
    int32_t target = lag + 1;
    int32_t contour = -1;
    for (int i = 0; i < 217; i++) {
        if ((int32_t)smpl_mem_u8(contour_map + (uint32_t)i) == target) {
            contour = i; break;
        }
    }
    res.lag = lag;
    res.contour = contour;
    if (contour < 0 || contour >= num_contours) return res;

    uint32_t ctr_base = pcfg + (uint32_t)contour * 0x44;
    int32_t base_lag = smpl_mem_i32(ctr_base + 0x1d38);

    /* (a) 64-symbol fine lag */
    int32_t cur_lag2 = base_lag;
    bool read_fine = true;
    if (st->prev_lag >= 0) {
        int32_t delta = base_lag - st->prev_lag;
        if (delta >= -1 && delta < 3) read_fine = false;
    }
    int32_t subfr_w = 0;
    if (read_fine) {
        int32_t sym = range_dec_decode64_fine_sym(dec);
        cur_lag2 = (base_lag << 6) + sym;
        st->prev_frac_lag = cur_lag2;
        st->prev_lag = base_lag;
        int32_t seg_len0 = smpl_mem_i32(ctr_base + 0x1d58);
        for (int i = 0; i < seg_len0; i++) {
            if (subfr_w < 4) res.int_lag_q6[subfr_w] = cur_lag2;
            if (subfr_w < 8) res.block_lags[subfr_w] = cur_lag2;
            subfr_w++;
        }
        if (subfr_w < 4) res.int_lag_q6[subfr_w] = cur_lag2;
        if (subfr_w < 8) res.block_lags[subfr_w] = cur_lag2;
    }

    /* (b) fractional per-segment loop */
    int32_t cnt2 = smpl_mem_i32(ctr_base + 0x1d78);
    int32_t seg_sel = 0;
    if (avg_gain >= 10007) {
        if (avg_gain < 14085) seg_sel = 1;
        else seg_sel = 2;
    }
    uint32_t frac_seg_base = frac_base + (uint32_t)seg_sel * 0x280;
    int32_t l3 = st->prev_frac_lag;
    int32_t l2 = cur_lag2;
    int start_seg = 0;
    if (read_fine) start_seg = 1;
    res.num_seg = cnt2;
    for (int seg = start_seg; seg < cnt2; seg++) {
        int32_t seg_lag = smpl_mem_i32(ctr_base + 0x1d38 + (uint32_t)seg * 4);
        if (l2 < 0) l2 = 0;  /* guard against garbage pitch data */
        int32_t nl2 = (int32_t)(((uint32_t)l2 << 6) - (uint32_t)l3) + (int32_t)(((uint32_t)(seg_lag - l2)) << 6);
        uint32_t off = frac_seg_base + (uint32_t)(nl2 * 2) + 0xfe;
        uint16_t cdf3[65];
        smpl_mem_cdf_at(off, 65, cdf3);
        int32_t sym = range_dec_decode_cdf(dec, cdf3, 65);
        l3 = sym + st->prev_frac_lag + nl2;
        if (seg < 8) res.sample_lag_q6[seg] = l3;
        int32_t seg_len = smpl_mem_i32(ctr_base + 0x1d58 + (uint32_t)seg * 4);
        for (int i = 0; i < seg_len; i++) {
            if (subfr_w < 4) res.int_lag_q6[subfr_w] = l3;
            if (subfr_w < 8) res.block_lags[subfr_w] = l3;
            subfr_w++;
        }
        l2 = seg_lag;
        st->prev_frac_lag = l3;
        st->prev_lag = seg_lag;
    }
    res.num_subfr = subfr_w;
    return res;
}