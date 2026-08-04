#ifndef MLOW_DECODE_H
#define MLOW_DECODE_H

#include <stdint.h>
#include <stdbool.h>
#include "range_coder.h"
#include "tables/lsf_seed.h"
#include "tables/cc_tables.h"
#include "tables/pitch_seed.h"
#include "mem.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ── Constants ─────────────────────────────────────────────────────────────── */
#define SMPL_ORDER       16
#define SMPL_SUBFR_LEN   80
#define SMPL_INTF_LEN    320
#define SMPL_SUBFR_COUNT 4
#define SMPL_LTP_HIST    728
#define LTP_HIST_LEN     (SMPL_LTP_HIST + SMPL_INTF_LEN + 64)
#define SMPL_FRAC_STATE_LEN 728
#define OPUS_FRAME_SAMPS 960

/* ── SmplLsfState ──────────────────────────────────────────────────────────── */
typedef struct {
    int32_t prev_stage1;
    bool    prev_match;
    bool    have_prev;
    int32_t prev_gain_idx;
    int32_t prev_filt_idx;
    int32_t prev_lag;
    int32_t prev_frac_lag;
    float   prev_lag_samples;
    int32_t prev_lagblk;
    int32_t prev_lagidx;
} smpl_lsf_state_t;

/* ── SmplLsfIndices ────────────────────────────────────────────────────────── */
typedef struct {
    int32_t stage1;
    int32_t grid;
    int32_t stage2[16];
    int32_t stage_nraw[16];
    int32_t extra;
} smpl_lsf_indices_t;

/* ── SmplPulseResult ───────────────────────────────────────────────────────── */
typedef struct {
    int32_t *pulses;     /* len = p2 (320) */
    int32_t  subfr[4];   /* per-subframe pulse counts */
} smpl_pulse_result_t;

/* ── SmplGainResult ────────────────────────────────────────────────────────── */
typedef struct {
    int32_t gain_q[4];
    int32_t nrg_res[4];
    int32_t gain_main;
    int32_t gain_delta;
} smpl_gain_result_t;

/* ── SmplPitchResult ───────────────────────────────────────────────────────── */
typedef struct {
    int32_t gain_idx[4];
    int32_t filt_idx[4];
    int32_t lag;
    int32_t contour;
    int32_t sample_lag_q6[8];
    int32_t num_seg;
    int32_t int_lag_q6[4];
    int32_t block_lags[8];
    int32_t num_subfr;
} smpl_pitch_result_t;

/* ── CelpDecParams ─────────────────────────────────────────────────────────── */
typedef struct {
    bool     voiced;
    int32_t  sf_pulses[4];
    int32_t  fcbg_idx[4];
    int32_t  nrgres_dbq_q14[4];
    int32_t  acbg_idx[4];
    float    block_lags[8];   /* per-40-block pitch lag */
    int32_t  total_pulses;
} celp_dec_params_t;

/* ── NoiseGenerator ────────────────────────────────────────────────────────── */
typedef struct {
    float   env_smth;
    float   env_last;
    float   out_state_uv[2];
    float   out_state_v[2];
    float   corr_smth[3];     /* smplNoiseCorrOrder + 1 = 3 */
    float   shape_state[2];   /* smplNoiseCorrOrder = 2 */
    bool    prev_voiced;
    int32_t since_unvoiced;
    int32_t rand_seed;
} noise_gen_t;

/* ── HpPostfilterState ─────────────────────────────────────────────────────── */
typedef struct {
    float   state_lo_emph1;
    float   state_lo_emph2;
    float   state_hp[4];
    float   lag_old;
    float  *x_old;            /* len = SMPL_INTF_LEN */
    float   coef_ma[3];
    float   coef_ar[3];
    /* Pre-allocated scratch (eliminates 6 malloc/free per frame) */
    float   scratch_x[SMPL_INTF_LEN];
    float   scratch_y_old[SMPL_INTF_LEN];
    float   scratch_y_tmp[SMPL_INTF_LEN];
    float   scratch_arma_tmp[SMPL_INTF_LEN];
    float   scratch_x_old_copy[SMPL_INTF_LEN];
    float   scratch_dummy[SMPL_INTF_LEN];
} hp_postfilter_state_t;

/* ── CelpDecState ───────────────────────────────────────────────────────────── */
typedef struct {
    noise_gen_t       noise;
    float            *acb_state;      /* len = acb_state_len */
    int               acb_state_len;
    float             lpc_synth_mem[SMPL_ORDER];
    float             lsf_prev[SMPL_ORDER];
    float             prev_nrgres;
    hp_postfilter_state_t hp;
    /* Pre-allocated scratch (eliminates 2 calloc/free per subframe) */
    float             acb_basis[SMPL_SUBFR_LEN * 2]; /* ACBG_M=2 */
    float             acb_out[SMPL_SUBFR_LEN];
} celp_dec_state_t;

/* ── SmplExcGainState ──────────────────────────────────────────────────────── */
typedef struct {
    float s0;
    float s1;
} smpl_exc_gain_state_t;

/* ── SmplFrameSynth ────────────────────────────────────────────────────────── */
typedef struct {
    float             lpc_state[SMPL_ORDER];
    float             ltp_hist[LTP_HIST_LEN];
    smpl_exc_gain_state_t gst;
} smpl_frame_synth_t;

/* ── SmplPitchSynth ────────────────────────────────────────────────────────── */
typedef struct {
    bool   voiced;
    double lag_subfr[4];
    double norm_gain;
} smpl_pitch_synth_t;

/* ── HarmPostfilterState ───────────────────────────────────────────────────── */
#define HARM_FB_DELAY      8
#define HARM_MAX_PITCH_LAG 320
#define HARM_DELAY          40
#define HARM_STATE_COMB_LEN (HARM_MAX_PITCH_LAG + SMPL_INTF_LEN*6 + HARM_DELAY)

typedef struct {
    float   state1[2 * HARM_FB_DELAY];
    float   lpcoefs[2 * HARM_FB_DELAY + 1];
    float  *state_comb;       /* len = HARM_STATE_COMB_LEN */
    int32_t prev_lag;
    int32_t prev_did_filter;
} harm_postfilter_state_t;

/* ── SmplDecoderState ──────────────────────────────────────────────────────── */
typedef struct {
    smpl_lsf_state_t    lstate;
    float               prev_nlsf[SMPL_ORDER];
    celp_dec_state_t   *celp;
    harm_postfilter_state_t *harm;
} smpl_decoder_state_t;

/* ── Decode functions ─────────────────────────────────────────────────────── */
smpl_lsf_indices_t decode_smpl_lsf(RangeDecoder *dec, smpl_lsf_state_t *st, int config, int intf);
smpl_pulse_result_t decode_smpl_pulses(RangeDecoder *dec, int32_t p2, int32_t p3, int32_t p4, int32_t p6, int32_t s1);
smpl_gain_result_t decode_smpl_gains(RangeDecoder *dec, int32_t p3, const int32_t subfr_counts[4]);
smpl_pitch_result_t decode_smpl_pitch(RangeDecoder *dec, smpl_lsf_state_t *st, int32_t p2, int32_t p3, int32_t p6, const int32_t subfr_counts[4]);

/* ── Synth functions ───────────────────────────────────────────────────────── */
void smpl_reconstruct_nlsf(float *out, int stage1, int config, int grid, const int32_t stage2[16], const float *prev_nlsf);
void smpl_nlsf2a(float *a, const float *nlsf, int order);
void celp_dec_synth_frame(celp_dec_state_t *s, const float *nlsf, int lsf_interpol_idx,
                           const int32_t *pulses, const celp_dec_params_t *params,
                           bool low_rate, int32_t frame_length16, float *out);

/* ── Synth helpers exposed for encoder shadow synth ────────────────────────── */
double smpl_gain_lin(int32_t gain_q);
float  smpl_ltp_frac_gain(double norm_gain);
void   smpl_ltp_subframe_pred(float *hist, int hist_pos, float lag_f, float gain_frac,
                               smpl_exc_gain_state_t *gst, float *pred_out);
void   smpl_lpc_synthesis(const float *ex, const float *a, float *out, float *state, int len);

/* ── Noise ─────────────────────────────────────────────────────────────────── */
void smpl_celp_gen_noise(noise_gen_t *ng, const float *exc_lpc, int l, bool voiced,
                         int32_t num_pulses, float nrgres, int32_t fcbg_idx,
                         const float *lsf, float normalized_bitrate,
                         const float *fcbgains_uv, float *noise);
float smpl_get_normalized_bitrate(int32_t num_pulses, int32_t frame_length16);
float smpl_decode_resnrg(int32_t nrgres_frame_dbq_q14, int32_t fcb_subfrlen);

/* ── HP postfilter ─────────────────────────────────────────────────────────── */
void smpl_hp_postfilter(hp_postfilter_state_t *st, const float *x_in, int n, float lag, float *out);
void hp_postfilter_state_init(hp_postfilter_state_t *st);

/* ── Harm postfilter ──────────────────────────────────────────────────────── */
void smpl_harm_postfilter(harm_postfilter_state_t *st, float *x, int x_len,
                          const float *lags, int n_lags, float normalized_bitrate);
void harm_postfilter_state_init(harm_postfilter_state_t *st);

/* ── FCB gains ─────────────────────────────────────────────────────────────── */
typedef struct {
    float uv[91];   /* uvGainIdxLen + 1 = 91 */
    float v[34];     /* fcbgVN = 34 */
} fcb_gains_t;

const fcb_gains_t *fcb_gains(void);

/* ── TOC ───────────────────────────────────────────────────────────────────── */
typedef struct {
    bool std_opus;
    bool sid;
    bool vad;
    int  sample_rate;
    int  frame_ms;
    bool voiced;
    bool active;
    bool flag2;
    bool flag0;
} smpl_toc_t;

smpl_toc_t parse_smpl_toc(uint8_t b);

/* ── RED ───────────────────────────────────────────────────────────────────── */
typedef struct {
    const uint8_t *data;
    int            len;
    uint8_t        time_code;
    bool           is_main;
} mlow_frame_t;

int depack_split_red(const uint8_t *p, int n, mlow_frame_t *frames, int max_frames);

/* ── State alloc/free ─────────────────────────────────────────────────────── */
celp_dec_state_t *celp_dec_state_new(void);
void celp_dec_state_free(celp_dec_state_t *s);
harm_postfilter_state_t *harm_postfilter_state_new(void);
void harm_postfilter_state_free(harm_postfilter_state_t *st);

#ifdef __cplusplus
}
#endif

#endif /* MLOW_DECODE_H */