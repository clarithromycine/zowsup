#ifndef MLOW_ENCODE_H
#define MLOW_ENCODE_H

#include <stdint.h>
#include <stdbool.h>
#include "range_coder.h"
#include "tables/lsf_seed.h"
#include "tables/cc_tables.h"
#include "tables/pitch_seed.h"
#include "mem.h"
#include "decode/decode.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ── Constants ─────────────────────────────────────────────────────────────── */
#define SMPL_MAIN_BIT_RATE    20000
#define SMPL_COMPLEXITY       8
#define SMPL_ENC_HP_FCORNER_HZ 35.0f
#define SMPL_LPC_HIST_LEN      144
#define SMPL_WINNEXT_WB_LEN    32
#define SMPL_LPC_PRE           96
#define SMPL_LSF_SURV          6
#define SMPL_LSF_RDW_ADJ       1.1952286f
#define SMPL_CELP_PERC_RESP_LEN 32
#define SMPL_CELP_FCB_SUBFR_LEN 80
#define SMPL_CELP_SUBFR_PER_PACKET 12
#define SMPL_PERC_R_LEN        33
#define SMPL_FCB_TOT_SURV_20MS_MAX 100
#define SMPL_PERC_EMPH_PITCH   -0.82f
#define SMPL_PITCH_PERC_RESP_LEN 17
#define SMPL_PITCH_LAG_MAX     320
#define SMPL_PITCH_LOOKAHEAD_LEN 7
#define SMPL_VOICED_NORM_GAIN  1.0
#define SMPL_MAX_PULSES_PER_SF 40
#define SMPL_MAX_PULSES_PER_SF_E 40
#define FCB_SRV_MAX              4
#define SMPL_CELP_MAX_RATES       2
#define SMPL_CELP_IDX_FEC         0
#define SMPL_CELP_IDX_MAIN        1

#define SMPL_LPC_ORDER     16
#define SMPL_LPC_BUF_LEN    448
#define SMPL_LPC_NFFT       512
#define SMPL_F_LEN          (SMPL_LPC_NFFT/2 + 1) /* 257 */
#define NFFT4              (SMPL_LPC_NFFT / 4)    /* 128 */

/* ── VuvMode ───────────────────────────────────────────────────────────────── */
typedef struct {
    float nrg_lo_bgn;
    float nrg_hi_bgn;
    float voicing_prev;
    float last_lag_prev;
} vuv_mode_t;

/* ── SmplEncoderState ──────────────────────────────────────────────────────── */
typedef struct {
    double *hist;          /* dynamic, kept as SmplOrder + smplWinnextWbLen tail */
    int    hist_len;
    int    hist_cap;
    float  hp_ma[3];
    float  hp_ar[3];
    bool   hp_set;
    float  hp_state[4];
    /* celp/perc/bitrate/vad �?opaque pointers to heap-allocated state */
    void  *celp_enc;
    void  *perc_model;
    void  *bitrate_ctrl;
    float  perc_prev[SMPL_PERC_R_LEN];
    float  lpc_hist[SMPL_LPC_HIST_LEN];
    float *prev_lsfq;      /* 16 entries */
    bool   prev_voiced;
    void  *vad_state;
    vuv_mode_t vuv;
    float  hp_pitch_hist[SMPL_PITCH_LAG_MAX];
    float *ltp_buf;        /* MaxLTPBufLen = 659 */
    /* pitchEst: cross-frame lag predictor */
    float  prev_lag_est;
    float  prev_pitch_corr_est;
    int32_t prev_lagblk_est;
    int32_t prev_lagidx_est;
    /* Pre-allocated scratch (eliminates 4 malloc/free per frame) */
    float  scratch_hp[960];           /* need = 3*SMPL_INTF_LEN */
    double scratch_x[976];           /* SMPL_ORDER + need */
    float  scratch_xn[1008];         /* res_lead + need */
    float  scratch_hpFull[1136];    /* SMPL_LPC_HIST_LEN + need + SMPL_WINNEXT_WB_LEN */
} smpl_encoder_state_t;

/* ── SmplLsfParams ─────────────────────────────────────────────────────────── */
typedef struct {
    int32_t stage1;
    int32_t grid;
    int32_t stage2[16];
    int32_t extra;
} smpl_lsf_params_t;

/* ── SmplRawSym ────────────────────────────────────────────────────────────── */
typedef struct {
    uint32_t sym;
    uint32_t nbits;
} smpl_raw_sym_t;

/* ── SmplPulseParams ───────────────────────────────────────────────────────── */
typedef struct {
    int32_t total;
    int32_t subfr[4];
    int32_t *mag_runs;     /* dynamic */
    int      mag_runs_len;
    smpl_raw_sym_t *sign_syms;
    int      sign_syms_len;
} smpl_pulse_params_t;

/* ── SmplPitchParams ────────────────────────────────────────────────────────── */
typedef struct {
    int32_t gain_idx[4];
    int32_t filt_idx[4];
    int32_t blockseg_idx;
    int32_t laginds[8];
} smpl_pitch_params_t;

/* ── SmplGainParams ─────────────────────────────────────────────────────────── */
typedef struct {
    int32_t gain_main;
    int32_t gain_delta;
    int32_t nrg_res[4];
} smpl_gain_params_t;

/* ── SmplInternalParams ────────────────────────────────────────────────────── */
typedef struct {
    smpl_lsf_params_t    lsf;
    smpl_pulse_params_t  pulses;
    bool                 has_pitch;
    smpl_pitch_params_t  pitch;
    smpl_gain_params_t   gains;
} smpl_internal_params_t;

/* ── SmplFrameParams ───────────────────────────────────────────────────────── */
typedef struct {
    uint8_t toc;
    int     config;
    smpl_internal_params_t internal[3];
} smpl_frame_params_t;

/* ── Voiced decision ───────────────────────────────────────────────────────── */
typedef struct {
    smpl_pitch_params_t pp;
    smpl_pitch_synth_t  pitch;
} voiced_decision_t;

/* ── CELP frame context ─────────────────────────────────── */
typedef struct {
    void        *celp;
    void        *perc;
    float       *perc_prev;       /* pointer to es->perc_prev (shared across frames) */
    void        *bitrate;
    const float *hp_n;
    int          intf;
    float        sp_act_prob;
    bool         coded_as_active_voice;
    float        f2[SMPL_F_LEN];
    float        voicing_strength;
    vuv_mode_t  *vuv;
    float        hp_pitch_hist[SMPL_PITCH_LAG_MAX];
    float       *ltp_buf;
    float        block_lags[SMPL_SUBFR_COUNT][2];
    float       *perc_corrs[4];   /* computed once per internal frame, reused by candidates */
    /* Pitch estimator state pointers */
    float       *pitch_prev_lag;
    float       *pitch_prev_corr;
    int32_t     *pitch_prev_lagblk;
    int32_t     *pitch_prev_lagidx;
} celp_frame_ctx_t;

/* ── Front-end LSF ────────────────────────────────────────── */
typedef struct {
    float  a[SMPL_LPC_ORDER + 1];
    float  nlsf[SMPL_LPC_ORDER];
    float *prev_lsfq;
    bool   prev_voiced;
    int    intf;
} front_end_lsf_t;

/* ── Candidate ─────────────────────────────────────────────── */
typedef struct {
    smpl_internal_params_t ip;
    int32_t   stage1;
    int32_t   grid;
    int32_t   qsym[16];
    int32_t  *pulse_vec;
    int32_t   gain_q[4];
    smpl_pitch_synth_t pitch;
    bool      silent;
} candidate_t;

/* ── Encode functions ──────────────────────────────────────────────────────── */

/* Analyze one 60ms PCM frame �?frame params */
void smpl_analyze_frame_st(smpl_encoder_state_t *es, const float *pcm, smpl_frame_params_t *fp);

/* Voiced/unvoiced classifier */
float smpl_get_signal_mode(float pitchcorr, const float *lags, float avg_lag,
                           float harm_strength, const float *f2, float sp_act_prob,
                           vuv_mode_t *vuv);

/* LPC front-end: window �?FFT-autocorr �?A/NLSF */
void smpl_window_lpc20(const float *input, bool use_long_win, float *out);
void smpl_lpc_analyze_with_f2(const float *windowed, float *a, float *f2);
void smpl_a2nlsf16(const float *a, float *nlsf);

/* LSF quantizer */
int  lsf_quant(const float *a, const float *nlsf, int voiced, int config,
               float rdw_adj, int surv, int32_t qi[17], float qlsf[16]);
int  lsf_quant_cond(const float *a, const float *nlsf, const float *prev_lsfq,
                    int voiced, int config, float rdw_adj, int surv,
                    int32_t qi[17], float qlsf[16]);

/* LSF interpol search */
int  smpl_lsf_interpol_search(const float *brec, const float *prev_lsfq,
                               const float *win_n, float predcoefs[4][17],
                               float *res_lpc);

/* FFT */
void rfft_forward_ordered(const float *time, int n, float *f);
void rfft_backward_ordered(const float *f, int n, float *time);

/* Pitch estimator */
void smpl_pitch_run(float *prev_lag, float *prev_pitch_corr,
                    int32_t *prev_lagblk, int32_t *prev_lagidx,
                    const float *ltp_buf, const float *f2,
                    bool coded_as_active_voice,
                    float *pitchcorr, float *lags, float *avg_lag,
                    float *harm_strength, int *blockseg_idx, int32_t *laginds);
float smpl_harm_strength_at(float avg_lag, const float *f2w, int f2w_len);

/* CELP encoder */
struct CelpEncoder;
typedef struct CelpEncoder CelpEncoder;
CelpEncoder *celp_encoder_new(bool low_rate, int perc_resp_len, int fcb_subfr_len, int subfr_per_packet);
void celp_encoder_free(CelpEncoder *enc);
void celp_encode_subframe(CelpEncoder *e, const float *res_lpc, const float predcoef[17],
                          const float *perc_wght_resp, const float lags[2],
                          int16_t fcb_pulses_max[2], int16_t surv_in[4],
                          const float subfr_importance[2],
                          int16_t pulses_out[2][SMPL_MAX_PULSES_PER_SF_E],
                          int16_t n_pulses[2], int16_t acb_idx[2], int16_t gain_idx[2],
                          float *exc_lpc_out);

/* LPC */
void smpl_lpc_interpol(const float *lsf, const float *prev_lsf, int interpol_idx,
                       float predcoefs[4][17], float *ilsf_out);

/* Gains */
void smpl_quant_nrg_res4(const float subfr_energy[4], const int32_t subfr_counts[4],
                         int32_t *gain_main, int32_t *gain_delta,
                         int32_t nrg_res[4]);

/* Perc model */
void *perc_model_new(void);
void perc_model_free(void *pm);
void smpl_perc_model(void *pm, const float *x, int xlen, int frame_ms,
                     int is_last, int rlen, float *r);
void smpl_perc_ac2a(const float *r, int len_r, float perc_emph, int perc_resp_len,
                    float reg, float *a_out);

/* VAD */
void *vad_state_new(void);
void vad_state_free(void *vs);
void vad_process_packet(void *vs, const int16_t *pcm, int subfr_len,
                        float *vad_results, bool *coded_as_active);

/* Bitrate controller */
void *bitrate_ctrl_new(void);
void bitrate_ctrl_free(void *bc);
void bitrate_ctrl_control(void *bc, int max_pulses[2], float *importance,
                          bool coded_as_active, float sp_act_prob,
                          float nonflatness, float voicing_strength,
                          int voiced, float wnrg, float wnrg_next);
void smpl_distribute_fcb_surv(int16_t *numsurv, int32_t max_pulses, int32_t tot_surv);

/* Encode frame to wire bytes */
int  encode_smpl_frame(const smpl_frame_params_t *fp, uint8_t *out, int max_out);

/* Pitch encode (defined in pitch_enc.c, called from encoder.c) */
void encode_smpl_pitch(RangeEncoder *enc, smpl_lsf_state_t *st, int32_t p3, int32_t p6, const int32_t subfr_counts[4], const smpl_pitch_params_t *pp);
void smpl_lags_predictor_after(int blocksegs_ix, const int32_t *laginds,
                               int32_t *out_blk, int32_t *out_idx);

/* State lifecycle */
void smpl_encoder_state_init(smpl_encoder_state_t *es);
void smpl_encoder_state_reset(smpl_encoder_state_t *es);
void smpl_encoder_state_free(smpl_encoder_state_t *es);

/* Build pulse params from pulse vector */
void smpl_build_pulse_params(const int32_t *pulse, smpl_pulse_params_t *pp);

/* Rate control gains */
void smpl_rate_control_gains(double target_linear, int32_t *gm, int32_t *gd, int32_t *gq);

/* Voiced/unvoiced helpers */
#define SMPL_PERC_EMPH_UV {-0.55f, -0.60f}
#define SMPL_PERC_EMPH_V  {-0.72f, -0.77f}

/* ── Analysis internal functions ──────────────────────────────────────────── */

/* smplAutocorr: autocorrelation of float64 data */
void smpl_autocorr(const double *x, int n, int order, double *r);

/* smplAnalysisResidualSubfr: analysis residual for one subframe */
void smpl_analysis_residual_subfr(const float a_syn[17], const float *win_n, int sf, float *res);

/* smplLsfInterpolSearch: picks best LSF interpolation index */
int smpl_lsf_interpol_search_full(const float *brec, const float *prev_lsfq,
                                   const float *win_n, float predcoefs[4][17],
                                   float *res_lpc);

/* percCorrsToWght: convert perc correlations to weighted AR coefficients */
void perc_corrs_to_wght(const float *corrs[4], const float emph[2],
                        int resp_len, float *wght_out[4]);

/* computePercCorrs: per-subframe perceptual autocorrelation */
void compute_perc_corrs(celp_frame_ctx_t *cs, float *corrs_out[4]);

/* buildLtpBuf: assemble LTP buffer from perc-weighted speech */
void build_ltp_buf(celp_frame_ctx_t *cs, const float *corrs[4]);

/* runCelpSubframes: CELP encode across subframes with bitrate control */
void run_celp_subframes(celp_frame_ctx_t *cs, const float predcoefs[4][17],
                        const float *res_lpc, const float block_lags[4][2],
                        const float *corrs[4], const float emph[2],
                        int voiced, int16_t acb_idx_out[4], int16_t gain_idx_out[4],
                        int16_t pulses_out[4][40], int16_t n_pulses_out[4],
                        float *exc_lpc_out);

/* smplSilentInternal: build silent-frame candidate */
void smpl_silent_internal(candidate_t *cand);

/* smplVoicedDecisionForLag: convert pitch lag indices to sample-domain lags */
void smpl_voiced_decision_for_lag(int blockseg_idx, const int32_t laginds[8],
                                   celp_frame_ctx_t *cs, float lags8_out[8],
                                   voiced_decision_t *vd);

/* smplVoicedCandidate: full voiced-mode candidate */
void smpl_voiced_candidate(const double *win, const float *prev_nlsf,
                           front_end_lsf_t *fe, celp_frame_ctx_t *cs,
                           const voiced_decision_t *vd, candidate_t *cand);

/* smplUnvoicedCandidate: full unvoiced-mode candidate */
void smpl_unvoiced_candidate(const double *win, const float *win_n,
                             const float *prev_nlsf, front_end_lsf_t *fe,
                             celp_frame_ctx_t *cs, candidate_t *cand);

/* commitCandidate: commit winning candidate to shadow synth */
void commit_candidate(smpl_frame_synth_t *st, const candidate_t *cand,
                      const float *prev_nlsf, float *nlsf_out);

/* smplReplayPitchState: update LSF state after voiced frame */
void smpl_replay_pitch_state(smpl_lsf_state_t *st, int32_t p3,
                              const int32_t subfr_counts[4],
                              const smpl_pitch_params_t *pp);

/* smplAnalyzeInternal: per-internal-frame decision engine */
void smpl_analyze_internal(smpl_frame_synth_t *shadow, smpl_lsf_state_t *lstate,
                           int intf, const double *win, const float *win_n,
                           const float *prev_nlsf, front_end_lsf_t *fe,
                           celp_frame_ctx_t *cs, smpl_internal_params_t *ip_out,
                           float *nlsf_out, bool *voiced_out);

/* SynthInternalFrame: shadow synth for encoder analysis */
void synth_internal_frame(smpl_frame_synth_t *st, int stage1, int config,
                          int grid, const int32_t stage2[16],
                          const float *prev_nlsf, const int32_t *pulses,
                          const int32_t gain_q[4], const smpl_pitch_synth_t *pitch,
                          float *signal_out, float *nlsf_out);

#ifdef __cplusplus
}
#endif

#endif /* MLOW_ENCODE_H */