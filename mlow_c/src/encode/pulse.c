/*
 * pulse.c — Pulse parameter utilities.
 *
 * smpl_build_pulse_params is in analysis.c (used by the encoder analysis pipeline).
 * smpl_free_pulse_params is provided here for cleanup.
 */
#include "encode.h"
#include <stdlib.h>

/* ── smpl_free_pulse_params ────────────────────────────────────────────────── */

void smpl_free_pulse_params(smpl_pulse_params_t *pp) {
    free(pp->mag_runs);
    free(pp->sign_syms);
    pp->mag_runs = NULL;
    pp->mag_runs_len = 0;
    pp->sign_syms = NULL;
    pp->sign_syms_len = 0;
}