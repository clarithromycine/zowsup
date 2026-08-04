/*
 * mlow_encoder.c — Encoder instance lifecycle + dispatch.
 */

#include "mlow_internal.h"
#include "encode/encode.h"
#include <stdlib.h>
#include <string.h>
#include <math.h>

struct MlowEncoder {
    smpl_encoder_state_t state;
};

MlowEncoder *mlow_encoder_new(void) {
    MlowEncoder *e = (MlowEncoder *)calloc(1, sizeof(MlowEncoder));
    if (!e) return NULL;
    smpl_encoder_state_init(&e->state);
    return e;
}

void mlow_encoder_free(MlowEncoder *e) {
    if (!e) return;
    smpl_encoder_state_free(&e->state);
    free(e);
}

void mlow_encoder_reset_impl(MlowEncoder *e) {
    if (!e) return;
    smpl_encoder_state_reset(&e->state);
}

int mlow_encoder_encode(MlowEncoder *e,
                        const float *pcm_in, int pcm_len,
                        uint8_t *enc_out, int max_enc) {
    if (!e || !enc_out) return -1;
    if (pcm_len != 960) return -1;

    /* Sanitize: NaN→0, clamp [-1,1] */
    float clean[960];
    for (int i = 0; i < 960; i++) {
        float s = pcm_in[i];
        if (isnan((double)s)) s = 0.0f;
        else if (s < -1.0f) s = -1.0f;
        else if (s > 1.0f) s = 1.0f;
        clean[i] = s;
    }

    /* Analyze */
    smpl_frame_params_t fp;
    smpl_analyze_frame_st(&e->state, clean, &fp);

    /* Entropy encode */
    int n = encode_smpl_frame(&fp, enc_out, max_enc);
    return n;
}