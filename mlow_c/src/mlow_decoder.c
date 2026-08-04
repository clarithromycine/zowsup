/*
 * mlow_decoder.c — Decoder instance lifecycle + dispatch.
 */

#include "mlow_internal.h"
#include "decode/decode.h"
#include <stdlib.h>
#include <string.h>
#include <math.h>

struct MlowDecoder {
    int                 redundancy;
    smpl_decoder_state_t state;
    celp_dec_state_t   *celp;
    harm_postfilter_state_t *harm;
};

MlowDecoder *mlow_decoder_new(void) {
    MlowDecoder *d = (MlowDecoder *)calloc(1, sizeof(MlowDecoder));
    if (!d) return NULL;
    d->celp = celp_dec_state_new();
    d->harm = harm_postfilter_state_new();
    d->state.celp = d->celp;
    d->state.harm = d->harm;
    return d;
}

void mlow_decoder_free(MlowDecoder *d) {
    if (!d) return;
    celp_dec_state_free(d->celp);
    harm_postfilter_state_free(d->harm);
    free(d);
}

void mlow_decoder_reset_impl(MlowDecoder *d) {
    if (!d) return;
    d->redundancy = 0;
    memset(&d->state.lstate, 0, sizeof(d->state.lstate));
    d->state.lstate.prev_gain_idx = -1;
    d->state.lstate.prev_filt_idx = -1;
    d->state.lstate.prev_lag = -1;
    d->state.lstate.prev_frac_lag = -1;
    d->state.lstate.prev_lagblk = -1;
    d->state.lstate.prev_lagidx = -1;
    memset(d->state.prev_nlsf, 0, sizeof(d->state.prev_nlsf));
    celp_dec_state_free(d->celp);
    harm_postfilter_state_free(d->harm);
    d->celp = celp_dec_state_new();
    d->harm = harm_postfilter_state_new();
    d->state.celp = d->celp;
    d->state.harm = d->harm;
}

void mlow_decoder_set_redundancy(MlowDecoder *d, int n) {
    if (!d) return;
    d->redundancy = n;
}

static void decode_frame(MlowDecoder *d, const uint8_t *frame, int frame_len, float *pcm_out, int *pcm_len, int max_samples);

int mlow_decoder_decode(MlowDecoder *d,
                        const uint8_t *payload, int length,
                        float *pcm_out, int max_samples) {
    if (!d || !pcm_out) return -1;

    if (length == 0) {
        int n = OPUS_FRAME_SAMPS;
        if (n > max_samples) n = max_samples;
        memset(pcm_out, 0, (size_t)n * sizeof(float));
        return n;
    }

    /* Try RED depack */
    mlow_frame_t frames[16];
    int nframes = depack_split_red(payload, length, frames, 16);
    bool red_ok = (nframes >= 2);

    if (d->redundancy > 0) {
        if (!red_ok) {
            int n = OPUS_FRAME_SAMPS;
            if (n > max_samples) n = max_samples;
            memset(pcm_out, 0, (size_t)n * sizeof(float));
            return n;
        }
        /* Decode main frame only */
        int pcm_len = 0;
        decode_frame(d, frames[nframes - 1].data, frames[nframes - 1].len, pcm_out, &pcm_len, max_samples);
        if (pcm_len > max_samples) pcm_len = max_samples;
        return pcm_len;
    }

    if (red_ok) {
        int pcm_len = 0;
        decode_frame(d, frames[nframes - 1].data, frames[nframes - 1].len, pcm_out, &pcm_len, max_samples);
        if (pcm_len > max_samples) pcm_len = max_samples;
        return pcm_len;
    }

    int pcm_len = 0;
    decode_frame(d, payload, length, pcm_out, &pcm_len, max_samples);
    if (pcm_len > max_samples) pcm_len = max_samples;
    return pcm_len;
}

/* ── decodeFrame ───────────────────────────────────────────────────────────── */
static void decode_frame(MlowDecoder *d, const uint8_t *frame, int frame_len,
                          float *pcm_out, int *pcm_len, int max_samples) {
    *pcm_len = 0;
    if (frame_len == 0) {
        int n = OPUS_FRAME_SAMPS;
        if (n > max_samples) n = max_samples;
        *pcm_len = n;
        memset(pcm_out, 0, n * sizeof(float));
        return;
    }

    smpl_toc_t toc = parse_smpl_toc(frame[0]);
    int out_len;
    if (toc.std_opus) out_len = 16000 / 1000 * toc.frame_ms;
    else out_len = toc.sample_rate / 1000 * toc.frame_ms;
    /* Cap out_len to the caller's buffer size */
    if (out_len > max_samples) out_len = max_samples;

    if (toc.std_opus) {
        *pcm_len = out_len;
        memset(pcm_out, 0, out_len * sizeof(float));
        return;
    }
    if (toc.sid || !toc.active) {
        *pcm_len = out_len;
        memset(pcm_out, 0, out_len * sizeof(float));
        return;
    }

    /* decodeActiveFrame */
    int config = (frame[0] >> 2) & 1;
    bool low_rate = ((frame[0] >> 2) & 1) != 0;

    RangeDecoder dec;
    range_dec_init(&dec, frame + 1, frame_len - 1);

    float out[3 * SMPL_INTF_LEN];
    int out_pos = 0;
    float packet_lags[24];  /* 3 * 8 */
    int packet_lags_count = 0;
    float avg_norm_br = 0.0f;

    for (int f = 0; f < 3; f++) {
        smpl_lsf_indices_t lsf = decode_smpl_lsf(&dec, &d->state.lstate, config, f);
        if (dec.Err) break;
        smpl_pulse_result_t pulses = decode_smpl_pulses(&dec, SMPL_INTF_LEN, 4, 1, config, lsf.stage1);
        if (dec.Err) { free(pulses.pulses); break; }
        bool voiced = (lsf.stage1 == 1);

        int32_t total = 0;
        for (int i = 0; i < 4; i++) total += pulses.subfr[i];

        celp_dec_params_t params;
        memset(&params, 0, sizeof(params));
        params.voiced = voiced;
        params.total_pulses = total;
        for (int i = 0; i < 4; i++) params.sf_pulses[i] = pulses.subfr[i];

        if (voiced) {
            smpl_pitch_result_t pr = decode_smpl_pitch(&dec, &d->state.lstate, SMPL_INTF_LEN, 4, config, pulses.subfr);
            if (dec.Err) { free(pulses.pulses); break; }
            for (int b = 0; b < 8; b++) {
                double v = (double)pr.block_lags[b] * 0.5 + 32.0;
                if (v < 0.0) v = 0.0;
                if (v > 320.0) v = 320.0;
                params.block_lags[b] = (float)v;
            }
            for (int sf = 0; sf < 4; sf++) {
                params.acbg_idx[sf] = pr.gain_idx[sf];
                if (pr.filt_idx[sf] > 0) params.fcbg_idx[sf] = pr.filt_idx[sf];
            }
        } else {
            smpl_gain_result_t g = decode_smpl_gains(&dec, 4, pulses.subfr);
            if (dec.Err) { free(pulses.pulses); break; }
            for (int sf = 0; sf < 4; sf++) params.nrgres_dbq_q14[sf] = g.gain_q[sf];
            for (int sf = 0; sf < 4; sf++) params.fcbg_idx[sf] = g.nrg_res[sf];
        }

        for (int i = 0; i < 8; i++) packet_lags[packet_lags_count++] = params.block_lags[i];
        avg_norm_br += smpl_get_normalized_bitrate(total, SMPL_INTF_LEN);

        float nlsf[SMPL_ORDER];
        smpl_reconstruct_nlsf(nlsf, (int)lsf.stage1, config, (int)lsf.grid, lsf.stage2, d->state.prev_nlsf);

        float sig[SMPL_INTF_LEN];
        celp_dec_synth_frame(d->celp, nlsf, (int)lsf.extra, pulses.pulses, &params, low_rate, SMPL_INTF_LEN, sig);

        memcpy(d->state.prev_nlsf, nlsf, SMPL_ORDER * sizeof(float));
        memcpy(out + out_pos, sig, SMPL_INTF_LEN * sizeof(float));
        out_pos += SMPL_INTF_LEN;

        free(pulses.pulses);
    }

    /* Per-packet harmonic postfilter */
    int plen = out_pos;
    if (plen > max_samples) plen = max_samples;
    smpl_harm_postfilter(d->harm, out, plen, packet_lags, packet_lags_count, avg_norm_br / 3.0f);

    /* Clamp + resize */
    for (int i = 0; i < plen; i++) {
        float v = out[i];
        if (v > 1.0f) v = 1.0f;
        else if (v < -1.0f) v = -1.0f;
        pcm_out[i] = v;
    }
    (void)packet_lags; (void)packet_lags_count; (void)avg_norm_br;

    if (out_len > 0 && out_len != plen) {
        if (out_len <= plen) {
            *pcm_len = out_len;
        } else {
            memset(pcm_out + plen, 0, (out_len - plen) * sizeof(float));
            *pcm_len = out_len;
        }
    } else {
        *pcm_len = plen;
    }
}