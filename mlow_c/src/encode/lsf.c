/*
 * lsf.c — LSF state advance (encoder mirror).
 *
 * NOTE: The decode-side equivalent is inline in decode_smpl_lsf() in decoder.c.
 * This file provides the encoder-only LSF state mirror so the encoder's pitch
 * lag predictor stays in sync with what the entropy coder will produce.
 */
#include "encode.h"
#include "../decode/decode.h"
#include <string.h>

void smpl_advance_lsf_state(smpl_lsf_state_t *st, int intf, int32_t stage1) {
    bool m = (intf != 0) && (stage1 == st->prev_stage1);
    if (!m) {
        st->prev_gain_idx = -1;
        st->prev_filt_idx = -1;
        st->prev_lag = -1;
        st->prev_frac_lag = -1;
        st->prev_lagblk = -1;
        st->prev_lagidx = -1;
    }
    st->prev_stage1 = stage1;
    st->prev_match = m;
    st->have_prev = true;
}